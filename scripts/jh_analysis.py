#!/usr/bin/env python3
"""Study JH exactly as pre-registered (experiments/PREREGISTRATION_JH.md): do judges of different model families miss different small hidden fires?

  python3 scripts/jh_analysis.py        # reads jev_scores_<judge>_{xd,closed_loop}.jsonl, devset_xd_h36_tiles.json, gv_dev_prompts.jsonl -> experiments/results/jh_summary.json
"""
from __future__ import annotations
import json
import math
import sys
from itertools import combinations  # noqa: F401
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.calibration_sites import threshold  # noqa: E402
from scripts.x_analysis import cp_upper  # noqa: E402

RES = ROOT / 'experiments/results'
CANDIDATES = ['internvl3', 'idefics3', 'qwen3vl', 'smolvlm2']        # tie order of the registration
ALPHA = 0.02
MAX_FS = 0.05


def roc_auc(pos: list, neg: list) -> float:
    if not pos or not neg:
        return float('nan')
    w = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return w / (len(pos) * len(neg))


def tau_of(clean_scores: list) -> float:
    t, _ = threshold(clean_scores, ALPHA)
    return math.ceil(t * 1000 - 1e-9) / 1000


def fisher_exact_two_sided(a: int, b: int, c: int, d: int) -> float:
    """Exact two-sided p of the 2 x 2 table [[a, b], [c, d]] (sum of tables at most as probable)."""
    n1, n2, k = a + b, c + d, a + c
    tot = n1 + n2

    def pr(x):
        return math.comb(n1, x) * math.comb(n2, k - x) / math.comb(tot, k)
    p0 = pr(a)
    return min(1.0, sum(pr(x) for x in range(max(0, k - n2), min(n1, k) + 1) if pr(x) <= p0 * (1 + 1e-9)))


def phi(a: int, b: int, c: int, d: int) -> float:
    den = math.sqrt((a + b) * (c + d) * (a + c) * (b + d))
    return (a * d - b * c) / den if den else float('nan')


def overlap(flag_q: dict, flag_j: dict, fire: list, clean: list) -> dict:
    """flag_* : world -> bool (flagged).  Misses on the fire worlds, the joint miss, independence expectation, phi, Fisher; false stops on the clean worlds."""
    n = len(fire)
    mq = [w for w in fire if not flag_q[w]]
    mj = [w for w in fire if not flag_j[w]]
    both = [w for w in fire if not flag_q[w] and not flag_j[w]]
    a, b, c = len(both), len(mq) - len(both), len(mj) - len(both)
    d = n - a - b - c
    fq = sum(flag_q[w] for w in clean)
    fj = sum(flag_j[w] for w in clean)
    fu = sum(flag_q[w] or flag_j[w] for w in clean)
    return {'n_fire': n, 'n_clean': len(clean), 'miss_Q': len(mq), 'miss_J': len(mj), 'miss_joint': len(both), 'expected_joint_if_independent': round(n * (len(mq) / n) * (len(mj) / n), 2) if n else None,
            'phi': None if math.isnan(phi(a, b, c, d)) else round(phi(a, b, c, d), 3), 'fisher_p_two_sided': round(fisher_exact_two_sided(a, b, c, d), 4),
            'false_stops_Q': fq, 'false_stops_J': fj, 'false_stops_union': fu, 'false_stop_union_rate': round(fu / len(clean), 4) if clean else None,
            'false_stop_union_upper95': round(cp_upper(fu, len(clean)), 4) if clean else None}


def jh1(o: dict) -> dict:
    ok_miss = o['miss_joint'] <= (2 * o['miss_Q']) // 3
    ok_fs = o['false_stop_union_upper95'] is not None and o['false_stop_union_rate'] <= MAX_FS
    return {'miss_reduction_ok': ok_miss, 'false_stop_ok': ok_fs, 'holds': bool(ok_miss and ok_fs)}


def rows(path: Path) -> list:
    return [json.loads(x) for x in path.read_text(encoding='utf8').splitlines() if x.strip()] if path.is_file() else []


def xd_world_scores() -> dict:
    """judge -> world -> {'split', 'kind', 'score'}; Qwen from the stored devset scores, per-world maximum over the views F, L, R (no extra views)."""
    labels = {}
    for r in (json.loads(x) for x in (ROOT / 'experiments/vlm_testset_xd/labels.jsonl').read_text(encoding='utf8').splitlines() if x.strip()):
        labels[r['image']] = r
    out = {'qwen35': {}}
    for r in json.loads((RES / 'devset_xd_h36_tiles.json').read_text(encoding='utf8'))['records']:
        p = ((r['passes'].get('1') or {}).get('scores') or {}).get('hazard_prob')
        out['qwen35'] = _put(out['qwen35'], r, p)
    for j in CANDIDATES:
        d = {}
        for r in rows(RES / f'jev_scores_{j}_xd.jsonl'):
            lab = labels.get(r['key'])
            if lab:
                d = _put(d, lab, r['score']['max'])
        out[j] = d
    return out


def _put(d: dict, lab: dict, p) -> dict:
    if p is None or lab.get('view') not in ('F', 'L', 'R') or lab.get('extra_view'):
        return d
    w = lab['world_id']
    kind = 'fire' if (lab['world_kind'] == 'hazard' and lab.get('world_perceivable_any_view')) else ('clean' if lab['world_kind'] in ('twin', 'ok') else 'other')
    e = d.setdefault(w, {'split': lab['split'], 'kind': kind, 'score': 0.0, 'views': 0})
    e['score'] = max(e['score'], p)
    e['views'] += 1
    return d


def analyse_xd(ws: dict) -> dict:
    q = ws['qwen35']
    cal_fire = [w for w, e in q.items() if e['split'] == 'cal' and e['kind'] == 'fire']
    cal_clean = [w for w, e in q.items() if e['split'] == 'cal' and e['kind'] == 'clean']
    test_fire = [w for w, e in q.items() if e['split'] == 'test' and e['kind'] == 'fire']
    test_clean = [w for w, e in q.items() if e['split'] == 'test' and e['kind'] == 'clean']
    tq = tau_of([q[w]['score'] for w in cal_clean])
    res = {'n': {'cal_fire': len(cal_fire), 'cal_clean': len(cal_clean), 'test_fire': len(test_fire), 'test_clean': len(test_clean)}, 'tau_Q': tq, 'candidates': {}}
    flag_q = {w: q[w]['score'] >= tq for w in test_fire + test_clean}
    aucs = {}
    for j in CANDIDATES:
        d = ws.get(j) or {}
        if not all(w in d for w in cal_fire + cal_clean + test_fire + test_clean):
            res['candidates'][j] = {'status': 'not scored'}
            continue
        aucs[j] = roc_auc([d[w]['score'] for w in cal_fire], [d[w]['score'] for w in cal_clean])
        tj = tau_of([d[w]['score'] for w in cal_clean])
        flag_j = {w: d[w]['score'] >= tj for w in test_fire + test_clean}
        o = overlap(flag_q, flag_j, test_fire, test_clean)
        res['candidates'][j] = {'tau_J': tj, 'auc_cal': round(aucs[j], 4), 'auc_test': round(roc_auc([d[w]['score'] for w in test_fire], [d[w]['score'] for w in test_clean]), 4), **o}
    res['auc_Q_cal'] = round(roc_auc([q[w]['score'] for w in cal_fire], [q[w]['score'] for w in cal_clean]), 4)
    if aucs:
        best = max(CANDIDATES, key=lambda j: (aucs.get(j, -1), -CANDIDATES.index(j)))
        res['selected'] = best
        res['JH1'] = {**jh1(res['candidates'][best]), 'judge': best, 'rule': 'miss_joint <= floor(2 miss_Q / 3) and union false stops <= 5%'}
    return res


def main():
    out = {'registered': 'experiments/PREREGISTRATION_JH.md', 'xd': analyse_xd(xd_world_scores())}
    (RES / 'jh_summary.json').write_text(json.dumps(out, indent=1) + '\n', encoding='utf8')
    print(json.dumps({'xd': {k: v for k, v in out['xd'].items() if k != 'candidates'}}, indent=1))
    for j, c in out['xd']['candidates'].items():
        print(j, {k: c.get(k) for k in ('status', 'auc_cal', 'miss_Q', 'miss_J', 'miss_joint', 'expected_joint_if_independent', 'phi', 'false_stop_union_rate')})


if __name__ == '__main__':
    main()
