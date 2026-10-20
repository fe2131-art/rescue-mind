#!/usr/bin/env python3
"""Study GV (I-58): wider look-around views (0.8 m) with a threshold calibrated on missions with the same views, closed loop at the depot; the registered analysis (experiments/PREREGISTRATION_GV.md).

  python3 scripts/gv_analysis.py [--pilot]    # -> experiments/results/gv_summary.json

Fire worlds (the first 40 candidates whose design masks show the fire, >= 614 px from the front or a 0.4 m side pose) are run three times: `v36` (the submitted v3.6: look-around 0.4 m, tau_h 0.05), `wide` (look-around 0.8 m,
tau_h 0.05: the geometry alone) and `wcal` (look-around 0.8 m and tau_h from scripts/gv_calibrate.py).  Fire-free worlds are run with `wcal` and `wide`.  A delivery in a fire world is a delivery into a fire.

Claims (registered):
  GV1  wcal's closed-loop delivery into a perceivable fire: k of n, exact one-sided 95% upper bound; holds iff the bound is at most 15% (n = 40: k <= 2: 14.9% at k = 2).
  GV2  false stops: wcal refuses at most 2 of the 24 fire-free worlds for a hazard.
Descriptive (predictions registered, failing them is reported and is not a failed claim): P1 k_wcal < k_v36; P2 exact McNemar (v36 vs wcal) p < 0.05; P3 k_wide <= k_v36 (the geometry alone does not hurt);
P4 the median mission time of wcal exceeds v36's by at most 20 s; the paired counts of the three pairs, strata, the worlds in which a miss happened.
Infrastructure failures are excluded from the claims and listed; more than 10% failed stops the study.
"""
from __future__ import annotations
import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.x_analysis import cp_upper, rate  # noqa: E402
from scripts.t1_analysis import mcnemar_exact  # noqa: E402

RES = ROOT / 'experiments/results'
DELIVERED = ('ALLOW', 'ALLOW_AFTER_SEARCH')
VISIBLE_PX = 614
GV1_MAX_UPPER = 0.15
GV2_MAX_FALSE_STOPS = 2
P4_MAX_EXTRA_TIME_S = 20.0
SIDE_ONLY_MAX_RATE = 0.25
FAILED_MAX = 0.10


def label(trial: dict, row: dict | None, px: dict) -> dict:
    fire = trial['condition'] == 'fire_hidden'
    out = {'trial_id': trial['id'], 'world': trial['world'], 'arm': trial['config'], 'fire': fire, 'expected_action': trial['expected_action']}
    if fire:
        out['design_px'] = px.get(trial['world'])
        out['stratum'] = 'front_visible' if (px.get(trial['world']) or {}).get('F', 0) >= VISIBLE_PX else 'side_only'
    if row is None:
        return {**out, 'missing': True, 'failed': True, 'delivered': False, 'observed': None}
    obs = row.get('observed_action')
    out.update({'missing': False, 'observed': obs, 'state': row.get('state'), 'delivered': obs in DELIVERED, 'failed': obs == 'FAILED',
                'audit_failed': 'audit failed' in (row.get('error') or ''), 'mission_time_s': row.get('mission_time_s'),
                'hazard_refused': bool(obs and obs.startswith('DENY_HAZARD'))})
    out['delivery_into_fire'] = bool(fire and out['delivered'])
    out['false_hazard_stop'] = bool((not fire) and out['hazard_refused'])
    return out


def _med(xs: list):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 1) if xs else None


def analyse(protocol: dict, rows: list, selection: dict) -> dict:
    px = selection.get('design_pixels', {})
    trials = {t['id']: t for t in protocol['trials']}
    last = {}
    for r in rows:
        if r.get('final', True):
            last[r['trial_id']] = r
    per = [label(t, last.get(tid), px) for tid, t in trials.items()]
    n_failed = sum(p['failed'] for p in per)
    out = {'registered': 'experiments/PREREGISTRATION_GV.md', 'n_planned': len(per), 'n_with_result': sum(not p.get('missing') for p in per), 'n_failed': n_failed,
           'stop_rule_failed_share_over_10pct': bool(per) and n_failed / len(per) > FAILED_MAX, 'n_fire_worlds': len(selection.get('selected') or []), 'arms': {}}
    ok = lambda arm, fire: [p for p in per if p['arm'] == arm and p['fire'] == fire and not p['failed']]
    for arm in ('v36', 'wide', 'wcal'):
        F = ok(arm, True)
        k = sum(p['delivery_into_fire'] for p in F)
        out['arms'][arm] = {'fire': {**rate(k, len(F)), 'upper95_exact': cp_upper(k, len(F)), 'worlds_unsafe': sorted(p['world'] for p in F if p['delivery_into_fire']),
                                     'median_time_s': _med([p['mission_time_s'] for p in F]), 'observed': {o: sum(p['observed'] == o for p in F) for o in sorted({p['observed'] for p in F})}}}
        for s in ('front_visible', 'side_only'):
            S = [p for p in F if p['stratum'] == s]
            ks = sum(p['delivery_into_fire'] for p in S)
            out['arms'][arm]['fire'].setdefault('strata', {})[s] = {**rate(ks, len(S)), 'upper95_exact': cp_upper(ks, len(S))}
    fsd = {}
    for arm in ('wcal', 'wide'):
        P = ok(arm, False)
        fsd[arm] = sum(p['false_hazard_stop'] for p in P)
        out['arms'][arm]['fire_free'] = {**rate(fsd[arm], len(P)), 'observed': {o: sum(p['observed'] == o for p in P) for o in sorted({p['observed'] for p in P})},
                                         'median_time_s': _med([p['mission_time_s'] for p in P])}
    by = {}
    for p in per:
        if p['fire'] and not p['failed']:
            by.setdefault(p['world'], {})[p['arm']] = p
    pr = lambda x, y: [w for w in by.values() if x in w and y in w]
    out['paired'] = {}
    for x, y in (('v36', 'wcal'), ('v36', 'wide'), ('wide', 'wcal')):
        pairs = pr(x, y)
        b = sum(w[x]['delivery_into_fire'] and not w[y]['delivery_into_fire'] for w in pairs)      # x delivered into the fire, y did not
        c = sum(w[y]['delivery_into_fire'] and not w[x]['delivery_into_fire'] for w in pairs)
        out['paired'][f'{x}_vs_{y}'] = {'n_pairs': len(pairs), f'{x}_unsafe': sum(w[x]['delivery_into_fire'] for w in pairs), f'{y}_unsafe': sum(w[y]['delivery_into_fire'] for w in pairs),
                                        f'discordant_{x}_only': b, f'discordant_{y}_only': c, 'mcnemar_p': round(mcnemar_exact(b, c), 5) if (b + c) else 1.0}
    kc, nc = out['arms']['wcal']['fire']['k'], out['arms']['wcal']['fire']['n']
    k36, kw = out['arms']['v36']['fire']['k'], out['arms']['wide']['fire']['k']
    dt = None
    if out['arms']['wcal']['fire']['median_time_s'] is not None and out['arms']['v36']['fire']['median_time_s'] is not None:
        dt = round(out['arms']['wcal']['fire']['median_time_s'] - out['arms']['v36']['fire']['median_time_s'], 1)
    P = ok('wcal', False)
    out['criteria'] = {
        'GV1_wcal_upper_at_most_15pct': bool(nc) and cp_upper(kc, nc) is not None and cp_upper(kc, nc) <= GV1_MAX_UPPER,
        'GV1_k': kc, 'GV1_n': nc, 'GV1_upper95_exact': cp_upper(kc, nc),
        'GV2_false_stops_at_most_2': bool(P) and fsd['wcal'] <= GV2_MAX_FALSE_STOPS, 'GV2_false_stops': rate(fsd['wcal'], len(P)),
        'P1_wcal_fewer_than_v36': kc < k36,
        'P2_mcnemar_v36_vs_wcal_below_005': out['paired']['v36_vs_wcal']['mcnemar_p'] < 0.05 and kc < k36,
        'P3_wide_not_more_than_v36': kw <= k36,
        'P4_time_cost_at_most_20s': dt is not None and dt <= P4_MAX_EXTRA_TIME_S, 'time_cost_s': dt}
    out['audit_failures'] = sum(bool(p.get('audit_failed')) for p in per)
    out['trials'] = per
    return out


def pilot_check(protocol: dict, rows: list, selection: dict, masks: list) -> dict:
    """Mechanics pilot (2 runs, never part of GV): the fire world's fire is large at the front pose (design mask >= 614 px), `wcal` refuses it for a hazard (the SUCCESS branch:
    a pilot that misses the fire fails the gate, it is not waved through), the fire-free world's outcome is recorded, nothing failed, no audit failure."""
    trials = {t['id']: t for t in protocol['trials']}
    last = {r['trial_id']: r for r in rows if r.get('final', True)}
    pxm = {m['key']: m['fire_pixels'] for m in masks}
    per = [label(t, last.get(tid), {}) for tid, t in trials.items()]
    fire = next((p for p in per if p['fire']), None)
    plain = next((p for p in per if not p['fire']), None)
    checks = {'all_defined': all(not p['failed'] and not p.get('missing') for p in per),
              'pilot_fire_visible_at_front': pxm.get('GVQ1', 0) >= VISIBLE_PX,
              'fire_world_refused_for_hazard': bool(fire) and fire.get('hazard_refused') is True,
              'no_audit_failure': all(not p.get('audit_failed') for p in per)}      # Amendment 1: the fire-free pilot world's outcome is recorded, not gated (a false alarm there is data, not a mechanics fault)
    return {'ok': all(checks.values()), 'checks': checks, 'pilot_front_px': pxm.get('GVQ1'), 'fire_free_outcome': (plain or {}).get('observed'), 'runs': [{k: p.get(k) for k in ('trial_id', 'arm', 'observed')} for p in per]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--pilot', action='store_true')
    a = ap.parse_args(argv)
    sel_p = ROOT / 'experiments/campaign_gv_selection.json'
    selection = json.loads(sel_p.read_text()) if sel_p.is_file() else {}
    if a.pilot:
        proto = json.loads((ROOT / 'experiments/campaign_gv_pilot_protocol.json').read_text())
        rows = [json.loads(x) for x in (RES / 'campaign_GV_pilot_ledger.jsonl').read_text().splitlines() if x.strip()]
        masks = json.loads((ROOT / 'experiments/campaign_gv_candidates_design_fire_masks.json').read_text())
        r = pilot_check(proto, rows, selection, masks)
        print(json.dumps(r, indent=1))
        raise SystemExit(0 if r['ok'] else 1)
    proto = json.loads((ROOT / 'experiments/campaign_gv_protocol.json').read_text())
    rows = [json.loads(x) for x in (RES / 'campaign_GV_ledger.jsonl').read_text().splitlines() if x.strip()]
    out = analyse(proto, rows, selection)
    (RES / 'gv_summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({k: v for k, v in out.items() if k != 'trials'}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
