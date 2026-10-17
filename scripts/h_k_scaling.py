#!/usr/bin/env python3
"""Campaign H follow-up (descriptive, not registered): how does check-preserving memory scale with the number of stations k?

  python3 scripts/h_k_scaling.py        # -> experiments/results/h_k_scaling.json

Model (answers the reviewer question "two stations is almost a lookup table").  k stations; the requested supply sits at
one of them.  Between missions it relocates with probability q to a uniformly chosen other station, so in the long run its
location is uniform.  Every policy checks each visited station exactly as v3.6 does (supply + hazard + look-around);
only the ORDER differs:
  M0 (no memory)       visits stations in the fixed inventory order 1..k until the supply is confirmed;
  M2 (verified memory) visits the station where it last SAW the supply first, then the rest in inventory order.
Mission time = t_direct + (visits - 1) * delta, with t_direct and delta = t_search - t_direct measured in campaign H
(h_change_rate.json 'rates').  Supply identification is taken as perfect (T1: 0/332 supply false approvals).

Closed form (uniform stationary location):
  E[visits | M0] = (k + 1) / 2,     E[visits | M2] = 1 + q k / 2,
  saving = delta * ((k - 1) - q k) / 2 per mission,   break-even q* = (k - 1) / k.
For k = 2 this gives delta (1 - 2q) / 2, which the campaign-H Monte-Carlo model reproduces (q = 0: 14.7 s, q = 0.2: 8.8 s).
Safety: both policies check every station they deliver from with the same rule (M2 with extra caution), so Corollary 1's
bound is unchanged; the expected number of checks per mission (the exposure term) is what memory reduces.
A Monte-Carlo run with the same process verifies the closed form.
"""
from __future__ import annotations
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'
KS = [2, 3, 4, 6, 8]
QS = [0.0, 0.1, 0.2, 0.3, 0.5]


def closed(k, q, t0, d):
    v0, v2 = (k + 1) / 2, 1 + q * k / 2
    return {'visits_M0': v0, 'visits_M2': v2, 'time_M0': t0 + (v0 - 1) * d, 'time_M2': t0 + (v2 - 1) * d,
            'saving_s': d * ((k - 1) - q * k) / 2}


def simulate(k, q, t0, d, missions=200_000, seed=2026):
    rng = random.Random(seed * 100 + k * 10 + int(q * 100))
    v0 = v2 = 0
    for i in range(missions):
        if i % 1000 == 0:                           # restart from the stationary (uniform) location; needed for q = 0
            loc, mem = rng.randrange(k), None
        if mem is not None and rng.random() < q:
            loc = rng.choice([s for s in range(k) if s != loc])
        v0 += loc + 1
        order = ([mem] if mem is not None else []) + [s for s in range(k) if s != mem]
        v2 += order.index(loc) + 1
        mem = loc                                   # M2 saw the supply where it delivered from
    v0, v2 = v0 / missions, v2 / missions
    return {'visits_M0': v0, 'visits_M2': v2, 'saving_s': (v0 - v2) * d}


def main():
    r = json.loads((RES / 'h_change_rate.json').read_text())['rates']['time_s']
    t0, d = r['deliver_direct'], r['deliver_search'] - r['deliver_direct']
    out = {'note': 'descriptive model, not registered; see docstring', 't_direct_s': round(t0, 1), 'delta_s': round(d, 1),
           'break_even_q': {k: round((k - 1) / k, 3) for k in KS}, 'grid': []}
    for k in KS:
        for q in QS:
            c, s = closed(k, q, t0, d), simulate(k, q, t0, d)
            out['grid'].append({'k': k, 'q': q, **{kk: round(v, 2) for kk, v in c.items()},
                                'mc_visits_M0': round(s['visits_M0'], 3), 'mc_visits_M2': round(s['visits_M2'], 3),
                                'mc_saving_s': round(s['saving_s'], 2)})
    (RES / 'h_k_scaling.json').write_text(json.dumps(out, indent=1) + '\n')
    for g in out['grid']:
        print(f"k={g['k']} q={g['q']:.1f}  visits M0 {g['visits_M0']:.2f} M2 {g['visits_M2']:.2f}  saving {g['saving_s']:5.1f} s "
              f"(MC {g['mc_saving_s']:5.1f})")
    print('delta', out['delta_s'], 'break-even', out['break_even_q'])


if __name__ == '__main__':
    main()
