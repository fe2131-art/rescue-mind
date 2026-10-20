#!/usr/bin/env python3
"""Study GC (I-45): a per-site calibrated hazard threshold in closed loop on fresh worlds; the registered analysis (experiments/PREREGISTRATION_GC.md).

  python3 scripts/gc_analysis.py [--pilot]    # -> experiments/results/gc_summary.json

Fire worlds (the first 40 candidates whose design masks show the fire, >= 614 px from the front or a side pose) are run twice: `v36` (the submitted v3.6, tau_h 0.05) and `cal`
(`--hazard-threshold 0.01`, 1.6 x the largest fire-free score of the calibration set).  Fire-free worlds are run once with `cal`.  A delivery in a fire world is a delivery into a fire.

Claims (registered):
  GC1  cal's closed-loop delivery into a perceivable fire: k of n, exact one-sided 95% upper bound; holds iff the bound is at most 15% (n = 40: k <= 2: 14.9% at k = 2, 18.3% at k = 3).  GR's v3.6 bound was 18.3%.
  GC2  false stops: cal refuses at most 1 of the fire-free worlds for a hazard.
Descriptive (predictions registered, failing them is reported and is not a failed claim): P1 cal k <= 1; P2 cal delivers into no fire that v36 refused in the same world more often than the reverse
(discordant cal-only <= discordant v36-only); the control (v36) k/n and the paired counts, the pooled cal estimate, mission time.
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
GC1_MAX_UPPER = 0.15
GC2_MAX_FALSE_STOPS = 1
P1_MAX_MISSES = 1
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
    out = {'registered': 'experiments/PREREGISTRATION_GC.md', 'n_planned': len(per), 'n_with_result': sum(not p.get('missing') for p in per), 'n_failed': n_failed,
           'stop_rule_failed_share_over_10pct': bool(per) and n_failed / len(per) > FAILED_MAX, 'n_fire_worlds': len(selection.get('selected') or []), 'arms': {}}
    ok = lambda arm, fire: [p for p in per if p['arm'] == arm and p['fire'] == fire and not p['failed']]
    for arm in ('v36', 'cal'):
        F = ok(arm, True)
        k = sum(p['delivery_into_fire'] for p in F)
        out['arms'][arm] = {'fire': {**rate(k, len(F)), 'upper95_exact': cp_upper(k, len(F)), 'worlds_unsafe': sorted(p['world'] for p in F if p['delivery_into_fire']),
                                     'mean_time_s': _med([p['mission_time_s'] for p in F]), 'observed': {o: sum(p['observed'] == o for p in F) for o in sorted({p['observed'] for p in F})}}}
        for s in ('front_visible', 'side_only'):
            S = [p for p in F if p['stratum'] == s]
            ks = sum(p['delivery_into_fire'] for p in S)
            out['arms'][arm]['fire'].setdefault('strata', {})[s] = {**rate(ks, len(S)), 'upper95_exact': cp_upper(ks, len(S))}
    P = ok('cal', False)
    fs = sum(p['false_hazard_stop'] for p in P)
    out['arms']['cal']['fire_free'] = {**rate(fs, len(P)), 'observed': {o: sum(p['observed'] == o for p in P) for o in sorted({p['observed'] for p in P})}}
    by = {}
    for p in per:
        if p['fire'] and not p['failed']:
            by.setdefault(p['world'], {})[p['arm']] = p
    pairs = [w for w in by.values() if 'cal' in w and 'v36' in w]
    b = sum(w['v36']['delivery_into_fire'] and not w['cal']['delivery_into_fire'] for w in pairs)      # v36 delivered into the fire, cal did not
    c = sum(w['cal']['delivery_into_fire'] and not w['v36']['delivery_into_fire'] for w in pairs)      # cal delivered, v36 did not
    kc = out['arms']['cal']['fire']['k']
    nc = out['arms']['cal']['fire']['n']
    k36 = out['arms']['v36']['fire']['k']
    gj = RES / 'gr_summary.json'
    pooled = None
    if gj.is_file():       # the v3.6 estimate pooled over G, GR and the v36 control of GC (three independent sets of worlds)
        g = json.loads(gj.read_text())['criteria']['pooled_with_G_v36']
        kp, np_ = k36 + g['k'], out['arms']['v36']['fire']['n'] + g['n']
        pooled = {**rate(kp, np_), 'upper95_exact': cp_upper(kp, np_), 'G_GR_v36': {'k': g['k'], 'n': g['n']}}
    p_mc = round(mcnemar_exact(b, c), 5) if (b + c) else 1.0
    out['paired'] = {'n_pairs': len(pairs), 'v36_unsafe_in_pairs': sum(w['v36']['delivery_into_fire'] for w in pairs), 'cal_unsafe_in_pairs': sum(w['cal']['delivery_into_fire'] for w in pairs),
                     'discordant_v36_only': b, 'discordant_cal_only': c, 'mcnemar_p': p_mc}
    out['criteria'] = {
        'GC1_cal_upper_at_most_15pct': bool(nc) and cp_upper(kc, nc) is not None and cp_upper(kc, nc) <= GC1_MAX_UPPER,
        'GC1_k': kc, 'GC1_n': nc, 'GC1_upper95_exact': cp_upper(kc, nc), 'GR_v36_upper_for_reference': 0.1826,
        'GC2_false_stops_at_most_1': bool(P) and fs <= GC2_MAX_FALSE_STOPS, 'GC2_false_stops': rate(fs, len(P)),
        'P1_cal_misses_at_most_1': kc <= P1_MAX_MISSES,
        'P2_cal_only_not_more_than_v36_only': c <= b,
        'pooled_v36_with_G_GR': pooled}
    out['audit_failures'] = sum(bool(p.get('audit_failed')) for p in per)
    out['trials'] = per
    return out


def pilot_check(protocol: dict, rows: list, selection: dict, masks: list) -> dict:
    """Mechanics pilot (2 runs, never part of GC): the fire world's fire is large at the front pose (design mask >= 614 px), `cal` refuses it for a hazard (the SUCCESS branch:
    a pilot that misses the fire fails the gate, it is not waved through), `cal` delivers in the fire-free world, nothing failed, no audit failure."""
    trials = {t['id']: t for t in protocol['trials']}
    last = {r['trial_id']: r for r in rows if r.get('final', True)}
    pxm = {m['key']: m['fire_pixels'] for m in masks}
    per = [label(t, last.get(tid), {}) for tid, t in trials.items()]
    fire = next((p for p in per if p['fire']), None)
    plain = next((p for p in per if not p['fire']), None)
    checks = {'all_defined': all(not p['failed'] and not p.get('missing') for p in per),
              'pilot_fire_visible_at_front': pxm.get('GQ1', 0) >= VISIBLE_PX,
              'fire_world_refused_for_hazard': bool(fire) and fire.get('hazard_refused') is True,
              'fire_free_world_delivered': bool(plain) and plain.get('delivered') is True,
              'no_audit_failure': all(not p.get('audit_failed') for p in per)}
    return {'ok': all(checks.values()), 'checks': checks, 'pilot_front_px': pxm.get('GQ1'), 'runs': [{k: p.get(k) for k in ('trial_id', 'arm', 'observed')} for p in per]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--pilot', action='store_true')
    a = ap.parse_args(argv)
    sel_p = ROOT / 'experiments/campaign_gc_selection.json'
    selection = json.loads(sel_p.read_text()) if sel_p.is_file() else {}
    if a.pilot:
        proto = json.loads((ROOT / 'experiments/campaign_gc_pilot_protocol.json').read_text())
        rows = [json.loads(x) for x in (RES / 'campaign_GC_pilot_ledger.jsonl').read_text().splitlines() if x.strip()]
        masks = json.loads((ROOT / 'experiments/campaign_gc_candidates_design_fire_masks.json').read_text())
        r = pilot_check(proto, rows, selection, masks)
        print(json.dumps(r, indent=1))
        raise SystemExit(0 if r['ok'] else 1)
    proto = json.loads((ROOT / 'experiments/campaign_gc_protocol.json').read_text())
    rows = [json.loads(x) for x in (RES / 'campaign_GC_ledger.jsonl').read_text().splitlines() if x.strip()]
    out = analyse(proto, rows, selection)
    (RES / 'gc_summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({k: v for k, v in out.items() if k != 'trials'}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
