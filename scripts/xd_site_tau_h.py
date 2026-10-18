#!/usr/bin/env python3
"""I-35 (exploratory; rule written in docs/IMPROVEMENT_LOG.md before this was computed): a per-site tau_h for the look-around.

tau_h' = the smallest value of the grid {0.01, 0.02, 0.05, 0.10, 0.15, 0.20} whose look-around correct-approval rate on the fire-free,
correct-supply worlds (ok + twin) of the CALIBRATION split is at least 95%.  Both tau_h' and the frozen 0.05 are evaluated on the TEST split
only.  Not a replacement of any registered XD verdict; a confirmation would need a fresh set.

  python3 scripts/xd_site_tau_h.py      # -> experiments/results/xd_site_tau_h.json
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import xd_analysis as xa  # noqa: E402

RES = ROOT / 'experiments/results'
GRID = (0.01, 0.02, 0.05, 0.10, 0.15, 0.20)


def _on(records: list, tau_h: float, split: str) -> dict:
    W = xa.world_outcomes(records, tau_h=tau_h)['worlds']
    S = {w: v for w, v in W.items() if v['split'] == split}
    P = [v for v in S.values() if v['kind'] == 'hazard' and v['perceivable']]
    hard = [v for v in P if v['cls'] == 'tongues_small']
    ok = [v for v in S.values() if v['kind'] in ('ok', 'twin')]
    wr = [v for v in S.values() if v['kind'] == 'wrong']
    return {'tau_h': tau_h, 'perceivable': len(P), 'misses': sum(v['la_allow'] for v in P),
            'hard_n': len(hard), 'hard_misses': sum(v['la_allow'] for v in hard),
            'correct_n': len(ok), 'correct_approvals': sum(v['la_allow'] for v in ok),
            'wrong_n': len(wr), 'wrong_false_approvals': sum(v['la_allow'] for v in wr)}


def analyse(records: list) -> dict:
    rec = [x for x in records if not x.get('variant')]
    cal = {t: _on(rec, t, 'cal') for t in GRID}
    ok_rate = {t: c['correct_approvals'] / c['correct_n'] for t, c in cal.items()}
    tau = next(t for t in GRID if ok_rate[t] >= 0.95)
    base, site = _on(rec, 0.05, 'test'), _on(rec, tau, 'test')
    out = {'rule': 'I-35 (exploratory)', 'tau_h_site': tau, 'calibration_correct_approval_rate': {str(t): round(r, 4) for t, r in ok_rate.items()},
           'test_frozen_0.05': base, 'test_site': site}
    r = {'hard_misses_at_most_half': site['hard_misses'] <= 0.5 * base['hard_misses'],
         'correct_approvals_at_least_90pct': site['correct_approvals'] >= 0.9 * site['correct_n'],
         'no_wrong_supply_approved': site['wrong_false_approvals'] == 0}
    out['readout'] = r
    out['promising'] = all(r.values())
    return out


def main():
    recs = json.loads((RES / 'devset_xd_h36_tiles.json').read_text())['records']
    out = analyse(recs)
    (RES / 'xd_site_tau_h.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
