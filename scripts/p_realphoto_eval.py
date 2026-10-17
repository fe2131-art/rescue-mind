#!/usr/bin/env python3
"""Study P (experiments/PREREGISTRATION_P.md): the v3.6 hazard question on real photographs (D-Fire test split, CC0).

  <python with pyarrow> scripts/p_realphoto_eval.py --data ~/.cache/rescuemind/dfire --sample   # write the sample list
  <python with pyarrow> scripts/p_realphoto_eval.py --data ~/.cache/rescuemind/dfire --run      # score via :8765 (resumable)
  python3 scripts/p_realphoto_eval.py --analyse

Images stay outside the repository; only file names, labels, box areas and scores are written.
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
SAMPLE = RES / 'p_sample.json'
OUT = RES / 'p_scores_qwen9b_h36_tiles.jsonl'


def category(label: str):
    cls = {x.split()[0] for x in label.strip().splitlines() if x.strip()}
    return {(): 'none', ('0',): 'smoke', ('1',): 'fire', ('0', '1'): 'both'}[tuple(sorted(cls))]


def max_box(label: str) -> float:
    return max([float(x.split()[3]) * float(x.split()[4]) for x in label.strip().splitlines() if x.strip()] or [0.0])


def rows(data: Path):
    import pyarrow.parquet as pq
    for f in sorted(data.glob('test-*.parquet')):
        t = pq.read_table(f, columns=['label', 'filename']).to_pydict()
        for i, (lab, fn) in enumerate(zip(t['label'], t['filename'])):
            yield f.name, i, fn, lab


def sample(data: Path):
    by = {}
    for f, i, fn, lab in rows(data):
        by.setdefault(category(lab), []).append({'file': f, 'row': i, 'filename': fn, 'category': category(lab),
                                                  'max_box_area': round(max_box(lab), 5)})
    rng = random.Random('P-2026')
    out = []
    for c in ('none', 'smoke', 'fire', 'both'):
        pool = sorted(by[c], key=lambda r: r['filename'])
        out += rng.sample(pool, 100)
    SAMPLE.write_text(json.dumps({'seed': 'P-2026', 'source': 'huggingface badsaarow/d-fire test split (D-Fire, CC0)',
                                  'n': len(out), 'images': out}, indent=1) + '\n')
    print('sample', len(out))


def run(data: Path, port: int):
    import pyarrow.parquet as pq
    from rescuemind.local_vision import _client_call
    done = {json.loads(x)['filename'] for x in OUT.read_text().splitlines()} if OUT.is_file() else set()
    todo = [r for r in json.loads(SAMPLE.read_text())['images'] if r['filename'] not in done]
    tables = {}
    for r in todo:
        if r['file'] not in tables:
            tables[r['file']] = pq.read_table(data / r['file'], columns=['image']).to_pydict()['image']
        blob = tables[r['file']][r['row']]['bytes']
        resp = _client_call(f'http://127.0.0.1:{port}/v1/classify', 'Qwen/Qwen3.5-9B', blob, 1, timeout=180)
        sc = resp.get('scores') or {}
        if sc.get('hazard_prompt') != 'h36' or sc.get('hazard_views') != 'tiles':
            sys.exit(f'server is not configured as v3.6 (h36 + tiles): {sc}')
        with OUT.open('a') as f:
            f.write(json.dumps({**r, 'hazard_prob': sc.get('hazard_prob'), 'hazard_view_probs': sc.get('hazard_view_probs')}) + '\n')
    print('scored', len(todo))


def analyse():
    from scripts.t1_analysis import wilson
    recs = [json.loads(x) for x in OUT.read_text().splitlines()]
    flag = lambda r: (r['hazard_prob'] or 0) >= 0.05
    hz = [r for r in recs if r['category'] != 'none']
    none = [r for r in recs if r['category'] == 'none']
    out = {'registered': 'experiments/PREREGISTRATION_P.md', 'n': len(recs),
           'recall': {'k': sum(map(flag, hz)), 'n': len(hz), 'ci95': wilson(sum(map(flag, hz)), len(hz))},
           'false_alarm': {'k': sum(map(flag, none)), 'n': len(none), 'ci95': wilson(sum(map(flag, none)), len(none))},
           'by_category': {c: f"{sum(flag(r) for r in recs if r['category'] == c)}/{sum(r['category'] == c for r in recs)}"
                           for c in ('none', 'smoke', 'fire', 'both')}}
    areas = sorted(r['max_box_area'] for r in hz)
    cuts = [areas[len(areas) // 3], areas[2 * len(areas) // 3]]
    terc = lambda a: 0 if a < cuts[0] else (1 if a < cuts[1] else 2)
    out['by_box_area_tercile'] = {f't{k + 1}': f"{sum(flag(r) for r in hz if terc(r['max_box_area']) == k)}/{sum(terc(r['max_box_area']) == k for r in hz)}"
                                  for k in range(3)}
    out['tercile_cuts_area_fraction'] = cuts
    (RES / 'p_summary.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--data', type=Path)
    ap.add_argument('--sample', action='store_true'); ap.add_argument('--run', action='store_true'); ap.add_argument('--analyse', action='store_true')
    ap.add_argument('--port', type=int, default=8765)
    a = ap.parse_args()
    if a.sample:
        sample(a.data.expanduser())
    if a.run:
        run(a.data.expanduser(), a.port)
    if a.analyse:
        analyse()


if __name__ == '__main__':
    main()
