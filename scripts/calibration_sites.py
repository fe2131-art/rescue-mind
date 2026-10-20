#!/usr/bin/env python3
"""Split-conformal threshold calibration at two sites, with a held-out check (I-50; post hoc, exploratory, image level; saved scores only).

Per fire-free world the score S is the largest hazard probability over the views a mission checks (front, left, right).  Calibrating on m fire-free worlds, the threshold
tau(alpha) = the r-th smallest calibration score with r = ceil((1 - alpha)(m + 1)) (tau = the maximum when r > m, which gives the bound 1/(m + 1) instead of alpha) refuses a fresh
fire-free world with probability at most 1 - r/(m + 1) <= alpha under exchangeability.  The held-out fire-free worlds check that rate; the fire worlds (never used in calibration) show the price:
the share of perceivable fire worlds whose three views all score below tau (a miss).

  arena (W)  : 75 fire-free twins, repeated random splits (50 calibration / 25 held out, seeds 0..199); 150 fire worlds
  depot (XD) : the registered calibration split of the twins (47) and the held-out twins (77); the held-out perceivable hazard worlds

  python3 scripts/calibration_sites.py     # -> experiments/results/calibration_sites.json
"""
from __future__ import annotations
import json
import math
import random
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'
ALPHAS = (0.01, 0.02, 0.05, 0.10)
VIEWS = ('F', 'L', 'R')


def world_scores(records: list, kind: str, split: str | None = None, perceivable_only: bool = False) -> dict:
    per: dict = {}
    for x in records:
        if x['world_kind'] != kind or x['view'] not in VIEWS or x.get('extra_view'):
            continue
        if split is not None and x.get('split') != split:
            continue
        if perceivable_only and not x.get('world_perceivable_any_view'):
            continue
        p = x['passes']['1']['scores'].get('hazard_prob')
        if p is not None:
            per.setdefault(x['world_id'], []).append(p)
    return {w: max(v) for w, v in per.items()}


def threshold(cal: list, alpha: float) -> tuple:
    """(tau, guaranteed false-stop bound): the ceil((1-alpha)(m+1))-th smallest score, or the maximum when that rank exceeds m."""
    s = sorted(cal)
    m = len(s)
    r = math.ceil((1 - alpha) * (m + 1) - 1e-9)
    if r > m:
        return s[-1], 1 / (m + 1)
    return s[r - 1], 1 - r / (m + 1)


def evaluate(cal: list, held: list, fires: list, alpha: float) -> dict:
    tau, bound = threshold(cal, alpha)
    fs = sum(x > tau for x in held)                     # a mission refuses when a view scores above tau
    ms = sum(x <= tau for x in fires)                   # a miss: every view at or below tau
    return {'alpha': alpha, 'tau': tau, 'guaranteed_false_stop_bound': round(bound, 4), 'held_out_false_stops': fs, 'held_out_n': len(held),
            'fire_misses': ms, 'fire_n': len(fires)}


def arena(records: list) -> dict:
    twins = list(world_scores(records, 'twin').values())
    fires = list(world_scores(records, 'fire', perceivable_only=True).values())
    out = {'calibration_worlds': 50, 'held_out_worlds': 25, 'splits': 200, 'fire_worlds': len(fires), 'rows': []}
    for a in ALPHAS:
        res = []
        for seed in range(200):
            rng = random.Random(seed)
            idx = list(range(len(twins)))
            rng.shuffle(idx)
            res.append(evaluate([twins[i] for i in idx[:50]], [twins[i] for i in idx[50:]], fires, a))
        out['rows'].append({'alpha': a, 'tau_median': statistics.median(r['tau'] for r in res), 'guaranteed_false_stop_bound': res[0]['guaranteed_false_stop_bound'],
                            'held_out_false_stop_rate_mean': round(sum(r['held_out_false_stops'] for r in res) / sum(r['held_out_n'] for r in res), 4),
                            'fire_miss_rate_mean': round(sum(r['fire_misses'] for r in res) / sum(r['fire_n'] for r in res), 4)})
    return out


def depot(records: list) -> dict:
    cal = list(world_scores(records, 'twin', 'cal').values())
    held = list(world_scores(records, 'twin', 'test').values())
    fires = list(world_scores(records, 'hazard', 'test', perceivable_only=True).values())
    return {'calibration_worlds': len(cal), 'held_out_worlds': len(held), 'fire_worlds': len(fires), 'rows': [evaluate(cal, held, fires, a) for a in ALPHAS]}


def cross_site(w: list, x: list) -> dict:
    """The arena's threshold used in the depot and the depot's in the arena (all fire-free worlds, all perceivable fire worlds of the other site)."""
    aw, dw = list(world_scores(w, 'twin').values()), list(world_scores(x, 'twin').values())
    af, df = list(world_scores(w, 'fire', perceivable_only=True).values()), list(world_scores(x, 'hazard', 'test', perceivable_only=True).values())
    ta, td = threshold(aw, 0.05)[0], threshold(list(world_scores(x, 'twin', 'cal').values()), 0.05)[0]
    return {'tau_arena_alpha05': ta, 'tau_depot_alpha05': td,
            'arena_tau_in_depot': {'false_stops': sum(v > ta for v in dw), 'fire_free_n': len(dw), 'fire_misses': sum(v <= ta for v in df), 'fire_n': len(df)},
            'depot_tau_in_arena': {'false_stops': sum(v > td for v in aw), 'fire_free_n': len(aw), 'fire_misses': sum(v <= td for v in af), 'fire_n': len(af)}}


def main():
    w = json.loads((RES / 'devset_w_h36_tiles.json').read_text(encoding='utf8'))['records']
    x = json.loads((RES / 'devset_xd_h36_tiles.json').read_text(encoding='utf8'))['records']
    out = {'note': 'post hoc, exploratory, image level (I-50); not a registered analysis', 'arena_W': arena(w), 'depot_XD': depot(x), 'cross_site': cross_site(w, x)}
    (RES / 'calibration_sites.json').write_text(json.dumps(out, indent=1) + '\n', encoding='utf8')
    print('cross_site', out['cross_site'])
    for site in ('arena_W', 'depot_XD'):
        print(site, {k: v for k, v in out[site].items() if k != 'rows'})
        for r in out[site]['rows']:
            print('  ', r)


if __name__ == '__main__':
    main()
