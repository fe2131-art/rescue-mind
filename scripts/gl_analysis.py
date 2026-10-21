#!/usr/bin/env python3
"""Study GL (I-75): left-only 0.8 m look-around with the front + left threshold against v3.6, closed loop at the depot, fresh worlds; the registered analysis (experiments/PREREGISTRATION_GL.md).

  python3 scripts/gl_analysis.py [--pilot]    # -> experiments/results/gl_summary.json

Fire worlds (the first 120 of 150 candidates whose design masks show the fire, >= 614 px from the front or a 0.4 m side pose) are run twice: `v36` (look-around 0.4 m both sides, tau_h 0.05) and `left` (look-around 0.8 m
left side only, tau_h 0.028).  Fire-free worlds (40) run both arms.  A delivery in a fire world is a delivery into a fire.

Claims (registered):
  GL1 (primary)  paired reduction: the exact ONE-sided McNemar test over fire worlds (v36 unsafe only vs left unsafe only) gives p < 0.05 and k_left < k_v36.
  GL2            budget: left's closed-loop delivery into a perceivable fire, exact one-sided 95% upper bound at most 10%.
  GL3            false stops: left refuses at most 2 of the 40 fire-free worlds for a hazard.
Descriptive (predictions registered, failing them is reported, not a failed claim): P1 left's false stops are not more than v36's by more than 2; P2 the median mission time of left is not more than 20 s above v36's;
the strata (front visible, side only; left visible or not), the worlds in which a miss happened, the paired counts.  Infrastructure failures are excluded from the claims and listed; more than 10% failed stops the study.
"""
from __future__ import annotations
import argparse
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.x_analysis import cp_upper, rate  # noqa: E402

RES = ROOT / 'experiments/results'
DELIVERED = ('ALLOW', 'ALLOW_AFTER_SEARCH')
VISIBLE_PX = 614
GL1_ALPHA = 0.05
GL2_MAX_UPPER = 0.10
GL3_MAX_FALSE_STOPS = 2
P2_MAX_EXTRA_TIME_S = 20.0
FAILED_MAX = 0.10


def mcnemar_one_sided(b: int, c: int) -> float:
    """Exact one-sided p that the arm with the b discordant unsafe worlds is worse than the arm with c: P(X >= b), X ~ Binomial(b + c, 1/2)."""
    d = b + c
    return 1.0 if d == 0 else sum(math.comb(d, i) for i in range(b, d + 1)) / 2 ** d


def label(trial: dict, row: dict | None, px: dict) -> dict:
    fire = trial['condition'] == 'fire_hidden'
    out = {'trial_id': trial['id'], 'world': trial['world'], 'arm': trial['config'], 'fire': fire, 'expected_action': trial['expected_action']}
    if fire:
        out['design_px'] = px.get(trial['world'])
        out['stratum'] = 'front_visible' if (px.get(trial['world']) or {}).get('F', 0) >= VISIBLE_PX else 'side_only'
        out['left_visible'] = (px.get(trial['world']) or {}).get('L', 0) >= VISIBLE_PX      # the left arm sees only the front and the left pose
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
    out = {'registered': 'experiments/PREREGISTRATION_GL.md', 'n_planned': len(per), 'n_with_result': sum(not p.get('missing') for p in per), 'n_failed': n_failed,
           'stop_rule_failed_share_over_10pct': bool(per) and n_failed / len(per) > FAILED_MAX, 'n_fire_worlds': len(selection.get('selected') or []), 'arms': {}}
    ok = lambda arm, fire: [p for p in per if p['arm'] == arm and p['fire'] == fire and not p['failed']]
    for arm in ('v36', 'left'):
        F = ok(arm, True)
        k = sum(p['delivery_into_fire'] for p in F)
        out['arms'][arm] = {'fire': {**rate(k, len(F)), 'upper95_exact': cp_upper(k, len(F)), 'worlds_unsafe': sorted(p['world'] for p in F if p['delivery_into_fire']),
                                     'median_time_s': _med([p['mission_time_s'] for p in F]), 'observed': {o: sum(p['observed'] == o for p in F) for o in sorted({p['observed'] for p in F})}}}
        for name, pick in (('front_visible', lambda p: p['stratum'] == 'front_visible'), ('side_only', lambda p: p['stratum'] == 'side_only'),
                           ('left_visible', lambda p: p['left_visible']), ('left_not_visible', lambda p: not p['left_visible'])):
            S = [p for p in F if pick(p)]
            ks = sum(p['delivery_into_fire'] for p in S)
            out['arms'][arm]['fire'].setdefault('strata', {})[name] = {**rate(ks, len(S)), 'upper95_exact': cp_upper(ks, len(S))}
    fsd = {}
    for arm in ('left', 'v36'):
        P = ok(arm, False)
        fsd[arm] = sum(p['false_hazard_stop'] for p in P)
        out['arms'][arm]['fire_free'] = {**rate(fsd[arm], len(P)), 'observed': {o: sum(p['observed'] == o for p in P) for o in sorted({p['observed'] for p in P})},
                                         'median_time_s': _med([p['mission_time_s'] for p in P])}
    by = {}
    for p in per:
        if p['fire'] and not p['failed']:
            by.setdefault(p['world'], {})[p['arm']] = p
    pairs = [w for w in by.values() if 'v36' in w and 'left' in w]
    b = sum(w['v36']['delivery_into_fire'] and not w['left']['delivery_into_fire'] for w in pairs)      # v36 delivered into the fire, left did not
    c = sum(w['left']['delivery_into_fire'] and not w['v36']['delivery_into_fire'] for w in pairs)
    out['paired'] = {'n_pairs': len(pairs), 'v36_unsafe': sum(w['v36']['delivery_into_fire'] for w in pairs), 'left_unsafe': sum(w['left']['delivery_into_fire'] for w in pairs),
                     'discordant_v36_only': b, 'discordant_left_only': c, 'mcnemar_one_sided_p': round(mcnemar_one_sided(b, c), 5) if (b + c) else 1.0,
                     'worlds_both_unsafe': sorted(w['v36']['world'] for w in pairs if w['v36']['delivery_into_fire'] and w['left']['delivery_into_fire'])}
    kl, nl = out['arms']['left']['fire']['k'], out['arms']['left']['fire']['n']
    k36 = out['arms']['v36']['fire']['k']
    dt = None
    if out['arms']['left']['fire']['median_time_s'] is not None and out['arms']['v36']['fire']['median_time_s'] is not None:
        dt = round(out['arms']['left']['fire']['median_time_s'] - out['arms']['v36']['fire']['median_time_s'], 1)
    P = ok('left', False)
    out['criteria'] = {
        'GL1_paired_one_sided_p_below_005_and_fewer': bool(pairs) and out['paired']['mcnemar_one_sided_p'] < GL1_ALPHA and kl < k36,
        'GL1_k_left': kl, 'GL1_k_v36': k36, 'GL1_p': out['paired']['mcnemar_one_sided_p'],
        'GL2_left_upper_at_most_10pct': bool(nl) and cp_upper(kl, nl) is not None and cp_upper(kl, nl) <= GL2_MAX_UPPER, 'GL2_k': kl, 'GL2_n': nl, 'GL2_upper95_exact': cp_upper(kl, nl),
        'GL3_false_stops_at_most_2': bool(P) and fsd['left'] <= GL3_MAX_FALSE_STOPS, 'GL3_false_stops': rate(fsd['left'], len(P)),
        'P1_left_false_stops_not_more_than_v36_plus_2': fsd['left'] <= fsd['v36'] + 2,
        'P2_time_cost_at_most_20s': dt is not None and dt <= P2_MAX_EXTRA_TIME_S, 'time_cost_s': dt}
    out['audit_failures'] = sum(bool(p.get('audit_failed')) for p in per)
    out['trials'] = per
    return out


def pilot_check(protocol: dict, rows: list, selection: dict, masks: list) -> dict:
    """Mechanics pilot (2 runs, never part of GL): the fire world's fire is large at the front pose (design mask >= 614 px), `left` refuses it for a hazard (the SUCCESS branch: a pilot that misses the fire fails the gate),
    exactly ONE look-around peek (the left one) was scheduled and taken in each run, the fire-free world's outcome is recorded (not gated), nothing failed, no audit failure."""
    trials = {t['id']: t for t in protocol['trials']}
    last = {r['trial_id']: r for r in rows if r.get('final', True)}
    pxm = {m['key']: m['fire_pixels'] for m in masks}
    per = [label(t, last.get(tid), {}) for tid, t in trials.items()]
    fire = next((p for p in per if p['fire']), None)
    plain = next((p for p in per if not p['fire']), None)
    one_peek = []                                     # for every run with a look-around record (an approval at the front): only the left point was scheduled, and only the left peek was taken
    for tid in trials:
        rid = (last.get(tid) or {}).get('run_id')
        f = ROOT / 'outputs/runs' / str(rid) / 'mission.json'
        if f.is_file():
            la = (json.loads(f.read_text(encoding='utf8')).get('look_around') or {})
            if la.get('points'):
                one_peek.append([q.get('side') for q in la['points']] == ['L'] and set(q.get('side') for q in la.get('peeks', [])) <= {'L'})
    checks = {'all_defined': all(not p['failed'] and not p.get('missing') for p in per),
              'pilot_fire_visible_at_front': pxm.get('GLQ1', 0) >= VISIBLE_PX,
              'fire_world_refused_for_hazard': bool(fire) and fire.get('hazard_refused') is True,
              'only_the_left_peek_scheduled': bool(one_peek) and all(one_peek),
              'no_audit_failure': all(not p.get('audit_failed') for p in per)}
    return {'ok': all(checks.values()), 'checks': checks, 'pilot_front_px': pxm.get('GLQ1'), 'fire_free_outcome': (plain or {}).get('observed'), 'runs': [{k: p.get(k) for k in ('trial_id', 'arm', 'observed')} for p in per]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--pilot', action='store_true')
    a = ap.parse_args(argv)
    sel_p = ROOT / 'experiments/campaign_gl_selection.json'
    selection = json.loads(sel_p.read_text()) if sel_p.is_file() else {}
    if a.pilot:
        proto = json.loads((ROOT / 'experiments/campaign_gl_pilot_protocol.json').read_text())
        rows = [json.loads(x) for x in (RES / 'campaign_GL_pilot_ledger.jsonl').read_text().splitlines() if x.strip()]
        masks = json.loads((ROOT / 'experiments/campaign_gl_candidates_design_fire_masks.json').read_text())
        r = pilot_check(proto, rows, selection, masks)
        print(json.dumps(r, indent=1))
        raise SystemExit(0 if r['ok'] else 1)
    proto = json.loads((ROOT / 'experiments/campaign_gl_protocol.json').read_text())
    rows = [json.loads(x) for x in (RES / 'campaign_GL_ledger.jsonl').read_text().splitlines() if x.strip()]
    out = analyse(proto, rows, selection)
    (RES / 'gl_summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({k: v for k, v in out.items() if k != 'trials'}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
