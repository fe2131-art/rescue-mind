#!/usr/bin/env python3
"""Development readout of `scripts/gv_dev_prompts.py` (post hoc; I-61).  NOT a registered analysis; the development data of a later registered study, never its test.

For each hazard question (`h36` frozen, `h37a`, `h37b`):
  * the per-world largest view score of the clean calibration missions at 0.4 m (GDK) and at 0.8 m (GVK) and the rank-rule threshold at alpha = 2% (`calibration_sites.rank_rule` as in GD / GV), by item;
  * on the fire runs of GD (0.4 m, both arms), the share of runs whose largest view score reaches the GDK threshold of the same question (the closed-loop detection the site calibration would give), by item,
    and how many of the runs that actually delivered into the fire (the misses of GD) reach it;
  * on GD's fire-free runs, how many reach the threshold (false stops the threshold would cause).

  python3 scripts/gv_dev_analysis.py     # -> experiments/results/gv_dev_analysis.json
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RES = ROOT / 'experiments/results'
ALPHA = 0.02


def rank_tau(scores: list, alpha: float = ALPHA):
    s = sorted(scores)
    r = math.ceil((1 - alpha) * (len(s) + 1))
    return s[r - 1] if 1 <= r <= len(s) else None


def per_run(rows: list, prompt: str) -> dict:
    """(study, trial) -> {'score': largest view score under `prompt`, item, fire, arm, world}."""
    out = {}
    for r in rows:
        k = (r['study'], r['trial_id'])
        s = r['scores'][prompt]['max']
        o = out.setdefault(k, {'score': 0.0, 'item': r['item'], 'fire': r['fire'], 'arm': r['arm'], 'world': r['world'], 'study': r['study']})
        o['score'] = max(o['score'], s)
    return out


def analyse(rows: list, unsafe: set, prompts=('h36', 'h37a', 'h37b')) -> dict:
    """`unsafe` = trial ids of GD runs that delivered into the fire (taken from the GD summary)."""
    res = {}
    for p in prompts:
        runs = per_run(rows, p)
        o = {}
        for study, key in (('GDK', 'clean_0.4m'), ('GVK', 'clean_0.8m')):
            sc = [(v['score'], v['item']) for (s, _), v in runs.items() if s == study]
            o[key] = {'m': len(sc), 'tau_alpha2': rank_tau([x for x, _ in sc]), 'max': max((x for x, _ in sc), default=None),
                      'by_item_max': {i: max((x for x, it in sc if it == i), default=None) for i in ('medicine', 'water')}}
        tau = o['clean_0.4m']['tau_alpha2']
        gd = [v for (s, _), v in runs.items() if s == 'GD']
        fire = [v for v in gd if v['fire']]
        free = [v for v in gd if not v['fire']]
        o['fire_runs_0.4m'] = {'n': len(fire), 'reach_tau': sum(v['score'] >= tau for v in fire) if tau is not None else None,
                               'by_item': {i: {'n': sum(v['item'] == i for v in fire), 'reach_tau': sum(v['item'] == i and v['score'] >= tau for v in fire) if tau is not None else None} for i in ('medicine', 'water')},
                               'delivered_into_fire': {'n': sum((s, t) in {('GD', u) for u in unsafe} for (s, t) in runs if runs[(s, t)]['fire'] and s == 'GD'),
                                                       'reach_tau': sum(v['score'] >= tau for (s, t), v in runs.items() if s == 'GD' and t in unsafe) if tau is not None else None}}
        o['fire_free_runs_0.4m'] = {'n': len(free), 'reach_tau': sum(v['score'] >= tau for v in free) if tau is not None else None}
        res[p] = o
    return res


def main():
    rows = [json.loads(x) for x in (RES / 'gv_dev_prompts.jsonl').read_text(encoding='utf8').splitlines()]
    s = json.loads((RES / 'gd_summary.json').read_text(encoding='utf8'))
    unsafe = {t['trial_id'] for t in s['trials'] if t.get('delivery_into_fire')}
    res = analyse(rows, unsafe)
    (RES / 'gv_dev_analysis.json').write_text(json.dumps({'note': 'post hoc development readout (I-61); not a registered analysis', 'n_views': len(rows), 'prompts': res}, ensure_ascii=False, indent=1) + '\n', encoding='utf8')
    for p, o in res.items():
        print(p, json.dumps({k: o[k] for k in ('clean_0.4m', 'clean_0.8m', 'fire_runs_0.4m', 'fire_free_runs_0.4m')}))


if __name__ == '__main__':
    main()
