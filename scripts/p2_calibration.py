#!/usr/bin/env python3
"""Study P2 (experiments/PREREGISTRATION_P2.md): site calibration of the hazard threshold on real photographs.

  <python with pyarrow> scripts/p2_calibration.py --sample                 # write experiments/results/p2_sample.json (CPU)
  <python with pyarrow> scripts/p2_calibration.py --run --wording h36      # score via :8765 (resumable); server must be h36 + tiles
  <python with pyarrow> scripts/p2_calibration.py --run --wording h35
  python3 scripts/p2_calibration.py --analyse                              # -> experiments/results/p2_summary.json

Images stay outside the repository; only file names, labels' box areas and scores are written.
"""
from __future__ import annotations
import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RES = ROOT / 'experiments/results'
SAMPLE = RES / 'p2_sample.json'
P_SAMPLE = RES / 'p_sample.json'
SUMMARY = RES / 'p2_summary.json'
DATA = Path('~/.cache/rescuemind/dfire').expanduser()
MODEL = 'Qwen/Qwen3.5-9B'
WORDINGS = ('h36', 'h35')                       # h36 first: ties go to the deployed wording
GRID = [0.01, 0.02, 0.05] + [round(0.05 * k, 2) for k in range(2, 20)]   # 0.01, 0.02, 0.05, 0.1, 0.15, ..., 0.95
FROZEN_TAU = 0.05
CAL_RECALL_MIN = 0.95
TEST_RECALL_MIN = 0.90
TEST_FA_MAX = 0.20
CAL_COUNTS = (('none', 200), ('smoke', 67), ('fire', 67), ('both', 66))
CAL_SHARDS = tuple(f'train-{i}.parquet' for i in range(9))   # Amendment 1: all nine shards


def scores_path(wording: str) -> Path:
    return RES / f'p2_scores_{wording}.jsonl'


# ---------------------------------------------------------------- sampling
def category(label: str):
    cls = {x.split()[0] for x in label.strip().splitlines() if x.strip()}
    return {(): 'none', ('0',): 'smoke', ('1',): 'fire', ('0', '1'): 'both'}[tuple(sorted(cls))]


def max_box(label: str) -> float:
    return max([float(x.split()[3]) * float(x.split()[4]) for x in label.strip().splitlines() if x.strip()] or [0.0])


def pools(data: Path, glob_names, split_tag: str):
    import pyarrow.parquet as pq
    by = {}
    for name in glob_names:
        t = pq.read_table(data / name, columns=['label', 'filename']).to_pydict()
        for i, (lab, fn) in enumerate(zip(t['label'], t['filename'])):
            c = category(lab)
            by.setdefault(c, []).append({'set': split_tag, 'file': name, 'row': i, 'filename': fn, 'category': c,
                                         'max_box_area': round(max_box(lab), 5)})
    return by


def draw(by, seed: str, counts, exclude=frozenset()):
    rng = random.Random(seed)
    out = []
    for c, n in counts:
        pool = sorted((r for r in by.get(c, []) if r['filename'] not in exclude), key=lambda r: r['filename'])
        if len(pool) < n:
            sys.exit(f'cannot draw {n} {c!r} images with seed {seed}: only {len(pool)} available in the registered source')
        out += rng.sample(pool, n)
    return out


def sample(data: Path):
    p_names = {r['filename'] for r in json.loads(P_SAMPLE.read_text())['images']}
    cal = draw(pools(data, CAL_SHARDS, 'cal'), 'P2-cal', CAL_COUNTS)
    test_files = sorted(f.name for f in data.glob('test-*.parquet'))
    test = draw(pools(data, test_files, 'test'), 'P2-test', tuple((c, 100) for c in ('none', 'smoke', 'fire', 'both')),
                exclude=p_names)
    names = [r['filename'] for r in cal + test]
    assert len(set(names)) == len(names) == 800, 'duplicate file names inside P2 samples'
    assert not (set(names) & p_names), 'P2 samples overlap with the sample of study P'
    SAMPLE.write_text(json.dumps({
        'registered': 'experiments/PREREGISTRATION_P2.md', 'source': 'huggingface badsaarow/d-fire (D-Fire, CC0)',
        'seeds': {'cal': 'P2-cal', 'test': 'P2-test'}, 'cal_shards': list(CAL_SHARDS),
        'n': len(cal) + len(test), 'images': cal + test}, indent=1) + '\n')
    print('calibration', len(cal), 'test', len(test), 'disjoint from P:', not (set(names) & p_names))


# ---------------------------------------------------------------- scoring
def run(data: Path, wording: str, port: int):
    import pyarrow.parquet as pq
    from rescuemind.local_vision import _client_call
    out = scores_path(wording)
    done = {json.loads(x)['filename'] for x in out.read_text().splitlines()} if out.is_file() else set()
    todo = [r for r in json.loads(SAMPLE.read_text())['images'] if r['filename'] not in done]
    tables = {}
    for r in todo:
        if r['file'] not in tables:
            tables[r['file']] = pq.read_table(data / r['file'], columns=['image']).to_pydict()['image']
        blob = tables[r['file']][r['row']]['bytes']
        resp = _client_call(f'http://127.0.0.1:{port}/v1/classify', MODEL, blob, 1, timeout=180)
        sc = resp.get('scores') or {}
        if sc.get('hazard_prompt') != wording or sc.get('hazard_views') != 'tiles':
            sys.exit(f'server is not configured as {wording} + tiles: {sc}')
        with out.open('a') as f:
            f.write(json.dumps({**r, 'wording': wording, 'hazard_prob': sc.get('hazard_prob'),
                                'hazard_view_probs': sc.get('hazard_view_probs')}) + '\n')
    print('scored', len(todo), 'to', out)


# ---------------------------------------------------------------- calibration rule (pure functions)
def prob(r) -> float:
    return r['hazard_prob'] or 0.0


def flagged(r, tau: float) -> bool:
    return prob(r) >= tau


def recall_fa(recs, tau: float):
    """(k_recall, n_hazard, k_false_alarm, n_none) at threshold tau."""
    hz = [r for r in recs if r['category'] != 'none']
    nn = [r for r in recs if r['category'] == 'none']
    return sum(flagged(r, tau) for r in hz), len(hz), sum(flagged(r, tau) for r in nn), len(nn)


def choose_tau(cal_recs, grid=GRID, min_recall=CAL_RECALL_MIN):
    """Largest tau in the grid whose calibration recall is >= min_recall; None if no tau qualifies."""
    ok = []
    for tau in grid:
        kh, nh, _, _ = recall_fa(cal_recs, tau)
        if nh and kh / nh >= min_recall:
            ok.append(tau)
    return max(ok) if ok else None


def choose_wording(cal_by_wording, grid=GRID, min_recall=CAL_RECALL_MIN, order=WORDINGS):
    """Per wording the calibrated tau; then the wording with the lower calibration false-alarm rate (ties -> first in
    `order`, i.e. h36). A wording with no feasible tau is excluded. Returns (wording|None, {wording: {...}})."""
    info = {}
    for w in order:
        tau = choose_tau(cal_by_wording[w], grid, min_recall)
        if tau is None:
            info[w] = {'tau': None}
            continue
        kh, nh, kf, nn = recall_fa(cal_by_wording[w], tau)
        info[w] = {'tau': tau, 'cal_recall': kh / nh, 'cal_fa': kf / nn, 'cal_recall_k': kh, 'cal_recall_n': nh,
                   'cal_fa_k': kf, 'cal_fa_n': nn}
    feasible = [w for w in order if info[w]['tau'] is not None]
    if not feasible:
        return None, info
    best = feasible[0]
    for w in feasible[1:]:
        if info[w]['cal_fa'] < info[best]['cal_fa']:      # strict: ties keep the earlier (h36)
            best = w
    return best, info


def claim(test_recall: float, test_fa: float):
    return test_recall >= TEST_RECALL_MIN and test_fa <= TEST_FA_MAX


def endpoint(recs, tau: float):
    from scripts.t1_analysis import wilson
    kh, nh, kf, nn = recall_fa(recs, tau)
    return {'tau': tau,
            'recall': {'k': kh, 'n': nh, 'rate': kh / nh if nh else None, 'ci95': wilson(kh, nh)},
            'false_alarm': {'k': kf, 'n': nn, 'rate': kf / nn if nn else None, 'ci95': wilson(kf, nn)}}


def load(wording: str):
    p = scores_path(wording)
    recs = [json.loads(x) for x in p.read_text().splitlines()] if p.is_file() else []
    return [r for r in recs if r['set'] == 'cal'], [r for r in recs if r['set'] == 'test']


def analyse():
    cal, test = {}, {}
    for w in WORDINGS:
        cal[w], test[w] = load(w)
    expect = {'cal': 400, 'test': 400}
    for w in WORDINGS:
        if len(cal[w]) != expect['cal'] or len(test[w]) != expect['test']:
            sys.exit(f'incomplete scores for {w}: cal {len(cal[w])}/400, test {len(test[w])}/400 (run --run --wording {w})')
    chosen, info = choose_wording(cal)
    out = {'registered': 'experiments/PREREGISTRATION_P2.md', 'grid': GRID, 'calibration': info,
           'chosen_wording': chosen, 'chosen_tau': info[chosen]['tau'] if chosen else None}
    out['test_at_own_tau'] = {w: endpoint(test[w], info[w]['tau']) for w in WORDINGS if info[w]['tau'] is not None}
    out['test_at_frozen_tau_0.05'] = {w: endpoint(test[w], FROZEN_TAU) for w in WORDINGS}
    if chosen is None:
        out['claim_supported'] = False
        out['failed'] = ['calibration: no tau in the grid reaches calibration recall >= 0.95 for either wording']
    else:
        ep = out['test_at_own_tau'][chosen]
        out['chosen_test'] = ep
        out['claim_supported'] = claim(ep['recall']['rate'], ep['false_alarm']['rate'])
        out['failed'] = ([] if ep['recall']['rate'] >= TEST_RECALL_MIN else [f"test recall {ep['recall']['rate']:.3f} < 0.90"]) + \
                        ([] if ep['false_alarm']['rate'] <= TEST_FA_MAX else [f"test false-alarm rate {ep['false_alarm']['rate']:.3f} > 0.20"])
    SUMMARY.write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data', type=Path, default=DATA)
    ap.add_argument('--sample', action='store_true'); ap.add_argument('--run', action='store_true')
    ap.add_argument('--analyse', action='store_true')
    ap.add_argument('--wording', choices=WORDINGS)
    ap.add_argument('--port', type=int, default=8765)
    a = ap.parse_args()
    if a.sample:
        sample(a.data.expanduser())
    if a.run:
        if not a.wording:
            ap.error('--run needs --wording')
        run(a.data.expanduser(), a.wording, a.port)
    if a.analyse:
        analyse()


if __name__ == '__main__':
    main()
