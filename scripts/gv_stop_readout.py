#!/usr/bin/env python3
"""Study GV stop-rule readout (post hoc, descriptive; I-60).  NOT a registered analysis.

GV stopped at its registered calibration stop rule (tau_cal 0.071 >= 0.05), so no GV trial exists.  This reads the 100 calibration missions that did run (fire-free depot worlds, threshold off, front + two 0.8 m side views):
the score of each view, by item and by side, how many worlds a threshold at the default 0.05 would stop, the rank-rule thresholds at other alphas, and the same quantities for the 0.4 m views of GD's calibration
(`experiments/results/gd_calibration.json`), so the effect of the wider views on the clean tail is visible.  The images behind the highest scores were looked at by hand (see I-60).

  python3 scripts/gv_stop_readout.py      # -> experiments/results/gv_stop_readout.json
"""
from __future__ import annotations
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RES = ROOT / 'experiments/results'
DEFAULT_TAU = 0.05


def rank_tau(scores: list, alpha: float) -> float | None:
    """Split-conformal rank rule: the ceil((1 - alpha)(m + 1))-th smallest score (None if it does not exist at this m)."""
    s = sorted(scores)
    r = math.ceil((1 - alpha) * (len(s) + 1))
    return s[r - 1] if 1 <= r <= len(s) else None


def summarise(worlds: dict) -> dict:
    sc = {w: v['score'] for w, v in worlds.items()}
    out = {'m': len(sc), 'median': round(statistics.median(sc.values()), 4), 'max': max(sc.values()),
           'n_at_or_above_default_0.05': sum(x >= DEFAULT_TAU for x in sc.values()),
           'rank_rule': {str(a): rank_tau(list(sc.values()), a) for a in (0.05, 0.02, 0.01)}}
    items = {}
    for w, v in worlds.items():
        items.setdefault(v.get('item'), []).append(v['score'])
    out['by_item'] = {i: {'n': len(x), 'median': round(statistics.median(x), 4), 'max': max(x), 'n_at_or_above_default': sum(y >= DEFAULT_TAU for y in x)} for i, x in sorted(items.items(), key=lambda t: str(t[0]))}
    views = {}
    for v in worlds.values():
        for k, p in (v.get('views') or {}).items():
            views.setdefault(k, []).append(p)
    out['by_view'] = {k: {'n': len(x), 'median': round(statistics.median(x), 4), 'max': max(x)} for k, x in sorted(views.items())}
    out['top'] = [{'world': w, 'score': v['score'], 'item': v.get('item'), 'views': v.get('views')} for w, v in sorted(worlds.items(), key=lambda t: -t[1]['score'])[:5]]
    return out


def main():
    gv = json.loads((RES / 'gv_calibration.json').read_text(encoding='utf8'))
    gd = json.loads((RES / 'gd_calibration.json').read_text(encoding='utf8'))
    res = {'note': 'post hoc, descriptive (I-60); not a registered analysis', 'gv_wide_0.8m': {'tau_cal': gv['tau_cal'], **summarise(gv['worlds'])}, 'gd_0.4m': {'tau_cal': gd['tau_cal'], **summarise(gd['worlds'])}}
    (RES / 'gv_stop_readout.json').write_text(json.dumps(res, ensure_ascii=False, indent=1) + '\n', encoding='utf8')
    for k in ('gv_wide_0.8m', 'gd_0.4m'):
        r = res[k]
        print(k, 'tau_cal', r['tau_cal'], 'median', r['median'], 'max', r['max'], 'at/above 0.05:', r['n_at_or_above_default_0.05'], 'rank', r['rank_rule'], 'items', r['by_item'], 'views', r['by_view'])


if __name__ == '__main__':
    main()
