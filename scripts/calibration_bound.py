#!/usr/bin/env python3
"""A distribution-free false-stop bound for a site-calibrated hazard threshold (I-48; split-conformal, post hoc).

Let S_1..S_m be the per-world scores of fire-free calibration worlds (S = the largest hazard probability of the views one mission checks: front and both side poses) and S_new that of a fresh fire-free
world.  If the worlds are exchangeable, P(S_new >= max_i S_i) <= 1/(m+1) (equality without ties).  A threshold tau >= max_i S_i therefore refuses a fresh fire-free world with probability at most 1/(m+1),
whatever the score distribution.  The bound is on the refusal of one mission: the look-around views are inside S.  It says nothing about fires (that is the miss rate, measured separately) and it holds only
where the calibration worlds and the site's worlds are exchangeable (same generator, same lighting law), which is the assumption the paper states.

  python3 scripts/calibration_bound.py          # the bound for W's 75 fire-free twins (experiments/results/devset_w_h36_tiles.json) and the expected false stops of a 24-world check
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ('F', 'L', 'R')


def false_stop_bound(m: int) -> float:
    """P(a fresh fire-free world scores at least as high as all m calibration worlds) <= 1/(m+1)."""
    if m < 1:
        raise ValueError('need at least one calibration world')
    return 1.0 / (m + 1)


def world_maxima(records: list) -> list:
    per: dict = {}
    for x in records:
        if x['world_kind'] == 'twin' and x['view'] in VIEWS and not x.get('extra_view'):
            p = x['passes']['1']['scores'].get('hazard_prob')
            if p is not None:
                per.setdefault(x['world_id'], []).append(p)
    return sorted(max(v) for v in per.values())


def main():
    recs = json.loads((ROOT / 'experiments/results/devset_w_h36_tiles.json').read_text(encoding='utf8'))['records']
    mx = world_maxima(recs)
    m = len(mx)
    b = false_stop_bound(m)
    print(json.dumps({'calibration_worlds': m, 'largest_world_score': mx[-1], 'second_largest': mx[-2], 'false_stop_bound_per_mission': round(b, 4),
                      'expected_false_stops_in_24_worlds_at_most': round(24 * b, 3)}, indent=1))


if __name__ == '__main__':
    sys.exit(main())
