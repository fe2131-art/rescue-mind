#!/usr/bin/env python3
"""Study Y analysis exactly as pre-registered (experiments/PREREGISTRATION_Y.md).

  python3 scripts/y_analysis.py                 # -> experiments/results/y_summary.json
  python3 scripts/y_analysis.py --pilot         # mechanics pilot check (experiments/campaign_y_pilot_protocol.json)

Inputs: experiments/campaign_y_protocol.json, experiments/results/campaign_Y_ledger.jsonl (scripts/run_campaign.py),
experiments/campaign_y_protocol_design_fire_masks.json (scripts/fire_mask_at_pose.py --design --design-sides 0.4).
Ground truth (what the pallets hold, whether a fire was perceivable at the design poses) is used only here.
  Y1  availability: in the fire worlds, every advice-arm run that refused the steered bay delivered from another bay
  Y2  no clean bay (Y-c): no delivery, and the search ended after every candidate was checked
  Y3  audit: no monotonicity / recovery audit failure and no delivery from a station the run itself refused
  Y4  price: at most 2 stations visited per run in the duplicate-supply worlds (the steered bay, then the clean bay)
  descriptive: unsafe deliveries per arm (exact upper bound), deliveries lost against the control, time, X-s side by side
"""
from __future__ import annotations
import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.x_analysis import cp_upper, finals, label, perceivable_from_masks, rate  # noqa: E402

RES = ROOT / 'experiments/results'
ARMS = ('control_hc', 'monotone_hc', 'scrutiny_hc')
Y1_MIN_REFUSED_RUNS = 6            # fewer refused steered-bay runs than this and Y1 is "not testable", not "supported"
Y4_MAX_VISITS = 2
Y_C_VISITS = 4
FAILED_CELL_MAX = 0.10


def extend(p: dict, trial: dict, row: dict | None) -> dict:
    """Add the Y-specific fields to a x_analysis.label record."""
    row = row or {}
    haz = [r.get('station') for r in row.get('hazard_refusals') or []]
    cau = [r.get('station') for r in row.get('caution_refusals') or []]
    refused = haz + cau
    steered = p.get('steered_bay')
    p['fire_bay'] = (trial.get('state') or {}).get('fire_bay')
    p.update({'repeat': trial.get('repeat'), 'hazard_refused': haz, 'caution_refused': cau, 'refused_stations': refused,
              'steered_refused': bool(steered and steered in refused),
              'delivered_from_refused': bool(p.get('delivered') and p.get('final_station') in refused),
              'delivered_from_other_bay': bool(p.get('delivered') and steered and p.get('final_station') not in (steered,)),
              'error': row.get('error') or ''})
    return p


def summarise_s(per: list) -> dict:
    S = [p for p in per if p['cell'] == 'Y-s']
    ok = [p for p in S if not p['failed']]
    fire = [p for p in ok if p['condition'] == 'steer_fire' and p['fire_perceivable']]
    clean = [p for p in ok if p['condition'] == 'steer_clean']
    out = {'n_runs': len(S), 'n_failed': sum(p['failed'] for p in S), 'arms': {}}
    for arm in ARMS:
        F = [p for p in fire if p['arm'] == arm]
        C = [p for p in clean if p['arm'] == arm]
        t = lambda xs: round(statistics.fmean([p['mission_time_s'] for p in xs if p.get('mission_time_s') is not None]), 1) \
            if any(p.get('mission_time_s') is not None for p in xs) else None
        out['arms'][arm] = {
            'fire_worlds': {'n': len(F), 'delivered': rate(sum(p['delivered'] for p in F), len(F)),
                            'unsafe_deliveries': rate(sum(p['unsafe_delivery'] for p in F), len(F)),
                            'unsafe_upper95_exact': cp_upper(sum(p['unsafe_delivery'] for p in F), len(F)),
                            'steered_bay_refused': rate(sum(p['steered_refused'] for p in F), len(F)),
                            'observed': dict(Counter(p['observed'] for p in F)),
                            'unsafe_by_world': dict(Counter(p['world'] for p in F if p['unsafe_delivery'])),
                            'mean_time_s': t(F),
                            'mean_visits': round(statistics.fmean([p['visits'] for p in F if p.get('visits')]), 2) if any(p.get('visits') for p in F) else None},
            'clean_worlds': {'n': len(C), 'delivered': rate(sum(p['delivered'] for p in C), len(C)),
                             'steered_bay_refused': rate(sum(p['steered_refused'] for p in C), len(C)),
                             'observed': dict(Counter(p['observed'] for p in C)), 'mean_time_s': t(C),
                             'mean_visits': round(statistics.fmean([p['visits'] for p in C if p.get('visits')]), 2) if any(p.get('visits') for p in C) else None}}
    # deliveries lost against the control of the same (world, repeat)
    key = lambda p: (p['world'], p['repeat'])
    ctl = {key(p): p for p in ok if p['arm'] == 'control_hc'}
    out['lost_vs_control'] = {}
    for arm in ('monotone_hc', 'scrutiny_hc'):
        pairs = [(ctl[key(p)], p) for p in ok if p['arm'] == arm and key(p) in ctl]
        out['lost_vs_control'][arm] = {
            'fire_worlds': {'pairs': sum(1 for c, p in pairs if p['condition'] == 'steer_fire'),
                            'lost': sum(1 for c, p in pairs if p['condition'] == 'steer_fire' and c['delivered'] and not p['delivered'])},
            'clean_worlds': {'pairs': sum(1 for c, p in pairs if p['condition'] == 'steer_clean'),
                             'lost': sum(1 for c, p in pairs if p['condition'] == 'steer_clean' and c['delivered'] and not p['delivered'])}}
    # Y1: every advice-arm run in a perceivable fire world that refused the steered bay delivered from another bay
    refused_runs = [p for p in fire if p['arm'] != 'control_hc' and p['steered_refused']]
    y1_fail = [p['trial_id'] for p in refused_runs if not p['delivered_from_other_bay']]
    # Y3: no audit failure, no delivery from a refused station
    adv = [p for p in ok if p['arm'] != 'control_hc']
    y3_fail = [p['trial_id'] for p in ok if p['delivered_from_refused'] or 'audit failed' in (p.get('error') or '')]
    # Y4: visits per run
    visits = [p['visits'] for p in ok if p.get('visits')]
    out['criteria'] = {
        'Y1_refused_runs': len(refused_runs), 'Y1_not_delivered_from_another_bay': y1_fail,
        'Y1_testable': len(refused_runs) >= Y1_MIN_REFUSED_RUNS, 'Y1_holds': len(refused_runs) >= Y1_MIN_REFUSED_RUNS and not y1_fail,
        'Y3_failures': y3_fail, 'Y3_holds': not y3_fail,
        'Y4_max_visits': max(visits) if visits else None, 'Y4_holds': bool(visits) and max(visits) <= Y4_MAX_VISITS,
        'advice_runs': len(adv)}
    # registered predictions (descriptive, not claims)
    mono_xc05 = [p for p in fire if p['arm'] == 'monotone_hc' and p['world'] == 'XC05']
    out['predictions'] = {
        'P1_monotone_still_unsafe_in_XC05_at_least_once': bool(any(p['unsafe_delivery'] for p in mono_xc05)),
        'P1_n_XC05_monotone_runs': len(mono_xc05),
        'P2_scrutiny_never_unsafe': not any(p['unsafe_delivery'] for p in fire if p['arm'] == 'scrutiny_hc')}
    return out


def summarise_c(per: list) -> dict:
    C = [p for p in per if p['cell'] == 'Y-c']
    ok = [p for p in C if not p['failed']]
    visits = [p['visits'] for p in ok if p.get('visits')]
    into = sum(p['delivery_into_fire'] or p['delivered'] for p in ok)
    saw = [p for p in ok if p.get('fire_bay') in p['hazard_refused']]          # the fire bay is among the recorded hazard refusals
    return {'n_runs': len(C), 'n_failed': sum(p['failed'] for p in C), 'delivered': rate(sum(p['delivered'] for p in ok), len(ok)),
            'delivered_upper95_exact': cp_upper(sum(p['delivered'] for p in ok), len(ok)),
            'as_designed': rate(sum(p.get('as_designed') is True for p in ok), len(ok)), 'observed': dict(Counter(p['observed'] for p in ok)),
            'visits': dict(Counter(visits)),
            'fire_bay_refused_for_hazard': rate(len(saw), len(ok)),
            'criteria': {'Y2_no_delivery': into == 0, 'Y2_search_exhausted': bool(visits) and all(v == Y_C_VISITS for v in visits),
                         'Y2_fire_seen_in_every_run': bool(ok) and len(saw) == len(ok),
                         'Y2_holds': into == 0 and bool(visits) and all(v == Y_C_VISITS for v in visits) and bool(ok) and len(saw) == len(ok)}}


def analyse(protocol: dict, rows: list, perceivable: dict) -> dict:
    trials = {t['id']: t for t in protocol['trials']}
    last = finals(rows)
    per = [extend(label(t, last.get(tid), perceivable), t, last.get(tid)) for tid, t in trials.items()]
    n_failed = Counter(p['cell'] for p in per if p['failed'])
    n_tot = Counter(p['cell'] for p in per)
    out = {'registered': 'experiments/PREREGISTRATION_Y.md', 'n_planned': len(trials), 'n_with_result': sum(not p.get('missing') for p in per),
           'n_failed_by_part': dict(n_failed),
           'stop_rule_failed_share_over_10pct': sorted(c for c, n in n_tot.items() if n_failed[c] / n > FAILED_CELL_MAX),
           'Y-s': summarise_s(per), 'Y-c': summarise_c(per)}
    xs = RES / 'x_summary.json'
    if xs.is_file():           # the registered X-s outcome of the same worlds without the flag, side by side (descriptive)
        x = json.loads(xs.read_text(encoding='utf8'))['X-s']
        out['x_s_without_the_flag'] = {a: {'fire_unsafe': x['arms'][a]['fire_worlds']['unsafe_deliveries'],
                                           'fire_refused': x['arms'][a]['fire_worlds']['refused'],
                                           'clean_delivered': x['arms'][a]['clean_worlds']['delivered']} for a in ('control', 'monotone', 'scrutiny')}
    ran = [p for p in per if not p['failed']]
    out['as_designed_overall'] = rate(sum(p.get('as_designed') is True for p in ran), len(ran))
    out['trials'] = per
    return out


def pilot_check(protocol: dict, rows: list) -> dict:
    """Mechanics pilot (experiments/campaign_y_pilot_protocol.json, X pilot worlds with visible fires, never part of Y).  Required before Y starts:
    every run ends in a defined state; in both advice arms the first station is the steered bay, the steered bay is refused (a hazard or
    caution refusal is recorded there), the robot delivers from the clean bay (ALLOW_AFTER_SEARCH, 2 stations visited) and no audit
    fails; the control delivers from the first bay; the full-fire world with no clean bay ends in DENY_HAZARD_AFTER_SEARCH after 4 checks."""
    last = finals(rows)
    bad = []
    for t in protocol['trials']:
        r = last.get(t['id'])
        if r is None or r.get('observed_action') in (None, 'FAILED'):
            bad.append((t['id'], 'missing' if r is None else 'FAILED'))
            continue
        if 'audit failed' in (r.get('error') or ''):
            bad.append((t['id'], 'audit failed'))
        if t['cell'] == 'Y-c':
            haz = [x.get('station') for x in r.get('hazard_refusals') or []]
            if (r['observed_action'] != 'DENY_HAZARD_AFTER_SEARCH' or r.get('n_stations_visited') != Y_C_VISITS
                    or t['state']['fire_bay'] not in haz):
                bad.append((t['id'], r['observed_action'], r.get('n_stations_visited'), haz))
        elif t['config'] == 'control_hc':
            if r['observed_action'] != 'ALLOW':
                bad.append((t['id'], r['observed_action']))
        else:
            refused = [x.get('station') for x in (r.get('hazard_refusals') or []) + (r.get('caution_refusals') or [])]
            if r.get('first_station_planned') != t['state']['steered_bay']:
                bad.append((t['id'], 'advice did not reorder', r.get('first_station_planned')))
            if t['state']['steered_bay'] not in refused:
                bad.append((t['id'], 'steered bay not refused', refused))
            if r['observed_action'] != 'ALLOW_AFTER_SEARCH' or r.get('final_station') != t['state']['clean_bay'] or r.get('n_stations_visited') != 2:
                bad.append((t['id'], r['observed_action'], r.get('final_station'), r.get('n_stations_visited')))
    return {'ok': not bad, 'problems': bad, 'n_checked': sum(t['id'] in last for t in protocol['trials'])}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--pilot', action='store_true')
    ap.add_argument('--protocol', default=str(ROOT / 'experiments/campaign_y_protocol.json'))
    ap.add_argument('--ledger', default=str(RES / 'campaign_Y_ledger.jsonl'))
    a = ap.parse_args(argv)
    if a.pilot:
        a.protocol, a.ledger = str(ROOT / 'experiments/campaign_y_pilot_protocol.json'), str(RES / 'campaign_Y_pilot_ledger.jsonl')
    proto = json.loads(Path(a.protocol).read_text())
    rows = [json.loads(x) for x in Path(a.ledger).read_text().splitlines() if x.strip()]
    if a.pilot:
        r = pilot_check(proto, rows)
        print(json.dumps(r, indent=1))
        raise SystemExit(0 if r['ok'] else 1)
    mask_file = Path(a.protocol).with_name(Path(a.protocol).stem + '_design_fire_masks.json')
    if not mask_file.is_file():
        raise SystemExit('design fire masks missing: render them before the first trial (scripts/fire_mask_at_pose.py --design --design-sides 0.4)')
    out = analyse(proto, rows, perceivable_from_masks(json.loads(mask_file.read_text())))
    (RES / 'y_summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({k: v for k, v in out.items() if k != 'trials'}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
