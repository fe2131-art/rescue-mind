#!/usr/bin/env python3
"""I-33 (exploratory; rule written in docs/IMPROVEMENT_LOG.md before this was computed): a per-site tau_sus for the I-20 extra views.

tau_sus' = the smallest world-level maximum F/L/R hazard score such that at most 15% of the fire-free worlds (ok, wrong, twin) of the
CALIBRATION split score at or above it.  The adaptive policy with tau_sus' is evaluated on the TEST split only.  Not a replacement of the
registered XD verdict (the XD test split was seen in aggregate); a confirmation would need a fresh set.

  python3 scripts/xd_site_tau_sus.py      # -> experiments/results/xd_site_tau_sus.json
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import xd_analysis as xa  # noqa: E402

RES = ROOT / 'experiments/results'


def analyse(records: list) -> dict:
    rec = [x for x in records if not x.get('variant')]
    w0 = xa.world_outcomes(rec)['worlds']
    byw = {}
    for x in rec:
        byw.setdefault(x['world_id'], {})[x['view']] = x
    cal = [w for w, v in w0.items() if v['kind'] in ('ok', 'twin', 'wrong') and v['split'] == 'cal']
    wl = sorted(max(xa.hazard_score(byw[w][k]) for k in 'FLR') for w in cal)
    tau = min(t for t in wl if sum(x >= t for x in wl) / len(wl) <= 0.15)
    W = xa.world_outcomes(rec, tau_sus=tau)['worlds']
    test = {w: v for w, v in W.items() if v['split'] == 'test'}
    tw = [v for v in test.values() if v['kind'] == 'twin' and v['has_extra']]
    P = [v for v in test.values() if v['kind'] == 'hazard' and v['perceivable']]
    la, ad = sum(v['la_allow'] for v in P), sum(v['ad_allow'] for v in P if v['ad_allow'] is not None)
    caa, cal_ = sum(bool(v['ad_allow']) for v in tw), sum(bool(v['la_allow']) for v in tw)
    trig = sum(bool(v['triggered']) for v in tw)
    ref = {w: v for w, v in xa.world_outcomes(rec)['worlds'].items() if v['split'] == 'test'}
    rp = [v for v in ref.values() if v['kind'] == 'hazard' and v['perceivable']]
    rt = [v for v in ref.values() if v['kind'] == 'twin' and v['has_extra']]
    out = {'rule': 'I-33 (exploratory)', 'tau_sus_site': tau, 'n_cal_fire_free_worlds': len(cal),
           'test': {'twins_with_extra': len(tw), 'triggered': trig, 'perceivable': len(P), 'look_around_misses': la, 'adaptive_misses': ad,
                    'twin_correct_approvals_adaptive': caa, 'twin_correct_approvals_look_around': cal_},
           'reference_tau_sus_0.005': {'triggered': sum(bool(v['triggered']) for v in rt), 'of': len(rt), 'perceivable': len(rp),
                                       'look_around_misses': sum(v['la_allow'] for v in rp), 'adaptive_misses': sum(v['ad_allow'] for v in rp if v['ad_allow'] is not None)}}
    out['promising'] = bool(trig / len(tw) <= 0.15 and (la - ad) >= 0.5 * la and (cal_ - caa) <= 1)
    out['readout'] = {'trigger_rate_at_most_15pct': trig / len(tw) <= 0.15, 'removes_at_least_half_of_misses': (la - ad) >= 0.5 * la,
                      'loses_at_most_one_correct_approval': (cal_ - caa) <= 1}
    return out


def main():
    recs = json.loads((RES / 'devset_xd_h36_tiles.json').read_text())['records']
    out = analyse(recs)
    (RES / 'xd_site_tau_sus.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
