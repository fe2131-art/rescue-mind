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


def xd_clean(path: Path) -> dict:
    """Image-level reference: the fire-free records of XD's set (teleported camera, same detector) per item: the largest hazard score over all views and the count at or above 0.05."""
    recs = [r for r in json.loads(path.read_text(encoding='utf8'))['records'] if r.get('hazard_at') is None]
    out = {}
    for item in ('medicine', 'water'):
        x = [r['passes']['1']['scores']['hazard_prob'] for r in recs if r['station'] == item]
        out[item] = {'n_images': len(x), 'max': max(x), 'n_at_or_above_default': sum(v >= DEFAULT_TAU for v in x)}
    return out


def tile_of_high_scores(ledger: Path, runs: Path, floor: float = 0.03) -> dict:
    """Which view and which of the four scored crops (index 3 = the last one) holds a score at or above `floor` in the calibration missions (needs the local run folders)."""
    n = {}
    for line in ledger.read_text(encoding='utf8').splitlines():
        r = json.loads(line)
        f = runs / r['run_id'] / 'mission.json'
        if not f.is_file():
            continue
        m = json.loads(f.read_text(encoding='utf8'))
        views = {'F': (((m.get('checkpoint') or {}).get('model_calls') or {}).get('first') or {}).get('scores', {}).get('hazard_view_probs')}
        views.update({pk['side']: pk['model_calls']['first']['scores']['hazard_view_probs'] for pk in (m.get('look_around') or {}).get('peeks') or []})
        for side, p in views.items():
            if p and max(p) >= floor:
                key = f"{r.get('expected_supply')}/{side}/crop{p.index(max(p))}"
                n[key] = n.get(key, 0) + 1
    return n


def gd_unsafe_by_item() -> dict:
    """GD's unsafe deliveries (post hoc, from gd_readout.json) by requested item, all arms and the `cal` arm."""
    item = {t['world']: t['expected'] for t in json.loads((ROOT / 'experiments/campaign_gd_protocol.json').read_text(encoding='utf8'))['trials']}
    u = json.loads((RES / 'gd_readout.json').read_text(encoding='utf8'))['digest']['unsafe_deliveries']
    out = {'all_arms': {}, 'cal': {}}
    for d in u:
        out['all_arms'][item[d['world']]] = out['all_arms'].get(item[d['world']], 0) + 1
        if d['arm'] == 'cal':
            out['cal'][item[d['world']]] = out['cal'].get(item[d['world']], 0) + 1
    return out


def main():
    gv = json.loads((RES / 'gv_calibration.json').read_text(encoding='utf8'))
    gd = json.loads((RES / 'gd_calibration.json').read_text(encoding='utf8'))
    res = {'note': 'post hoc, descriptive (I-60); not a registered analysis', 'gv_wide_0.8m': {'tau_cal': gv['tau_cal'], **summarise(gv['worlds'])}, 'gd_0.4m': {'tau_cal': gd['tau_cal'], **summarise(gd['worlds'])},
           'xd_images_fire_free': xd_clean(RES / 'devset_xd_h36_tiles.json'),
           'gd_unsafe_deliveries_by_item': gd_unsafe_by_item(),
           'views_at_or_above_0.03_by_item_side_crop': tile_of_high_scores(RES / 'campaign_GVK_ledger.jsonl', ROOT / 'outputs/runs')}
    (RES / 'gv_stop_readout.json').write_text(json.dumps(res, ensure_ascii=False, indent=1) + '\n', encoding='utf8')
    for k in ('gv_wide_0.8m', 'gd_0.4m'):
        r = res[k]
        print(k, 'tau_cal', r['tau_cal'], 'median', r['median'], 'max', r['max'], 'at/above 0.05:', r['n_at_or_above_default_0.05'], 'rank', r['rank_rule'], 'items', r['by_item'], 'views', r['by_view'])


if __name__ == '__main__':
    main()
