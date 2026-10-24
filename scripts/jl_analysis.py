#!/usr/bin/env python3
"""Study JL (I-115): suspicion-triggered extra views in the closed loop at the depot on FRESH worlds with a CONCURRENT control; the registered analysis (experiments/PREREGISTRATION_JL.md).

  python3 scripts/jl_analysis.py      # -> experiments/results/jl_summary.json

Arms `v36` (the submitted look-around) and `adapt` (v3.6 + --adaptive-views 0.8 --adaptive-near 0), both on the 100 fire worlds and the 32 fire-free worlds of the selection, interleaved.  A delivery in a fire world is a
delivery into a fire.
Claims (registered):
  JL1  adapt delivers into fewer fires than v36 on the same worlds: exact ONE-sided McNemar p < 0.05 and k_adapt < k_v36.
  JL2  budget: adapt's delivery into a perceivable fire has an exact one-sided 95% upper bound of at most 10% (k <= 4 of 100; JK measured 3).
  JL3  false stops: adapt refuses at most 3 of the 32 fire-free worlds for a hazard.
Descriptive (predictions registered, failing them is reported, not a failed claim): P1 the median mission time of adapt exceeds v36's by at most 30 s (now concurrent); P2 the extra views are triggered in at least 70% of the
missions that reach them and every triggered mission takes both poses or ends in a hazard refusal; P3 adapt's false stops are not more than v36's by more than 2.
Infrastructure failures are excluded from the claims and listed; more than 10% fail stops the campaign.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.x_analysis import cp_upper, rate  # noqa: E402
from scripts.gm_analysis import mcnemar_one_sided, label, _med  # noqa: E402
from scripts.jk_analysis import last_rows, adaptive_record  # noqa: E402

RES = ROOT / 'experiments/results'
JL1_ALPHA = 0.05
JL2_MAX_UPPER = 0.10
JL3_MAX_FALSE_STOPS = 3
P1_MAX_EXTRA_TIME_S = 30.0
P2_MIN_TRIGGER = 0.70
FAILED_MAX = 0.10


def analyse(protocol: dict, rows: dict, selection: dict) -> dict:
    px = selection.get('design_pixels', {})
    per = [label(t, rows.get(t['id']), px) for t in protocol['trials']]
    n_failed = sum(p['failed'] for p in per)
    out = {'registered': 'experiments/PREREGISTRATION_JL.md', 'n_planned': len(per), 'n_with_result': sum(not p.get('missing') for p in per), 'n_failed': n_failed,
           'stop_rule_failed_share_over_10pct': bool(per) and n_failed / len(per) > FAILED_MAX, 'n_fire_worlds': len(selection.get('selected') or []), 'arms': {}}
    ok = lambda arm, fire: [p for p in per if p['arm'] == arm and p['fire'] == fire and not p['failed']]
    fsd = {}
    for arm in ('v36', 'adapt'):
        F, P = ok(arm, True), ok(arm, False)
        k = sum(p['delivery_into_fire'] for p in F)
        fsd[arm] = sum(p['false_hazard_stop'] for p in P)
        out['arms'][arm] = {'fire': {**rate(k, len(F)), 'upper95_exact': cp_upper(k, len(F)), 'worlds_unsafe': sorted(p['world'] for p in F if p['delivery_into_fire']), 'median_time_s': _med([p['mission_time_s'] for p in F]),
                                     'observed': {o: sum(p['observed'] == o for p in F) for o in sorted({p['observed'] for p in F})}},
                            'fire_free': {**rate(fsd[arm], len(P)), 'worlds_stopped': sorted(p['world'] for p in P if p['false_hazard_stop']), 'median_time_s': _med([p['mission_time_s'] for p in P])}}
        for name, pick in (('front_visible', lambda p: p['stratum'] == 'front_visible'), ('side_only', lambda p: p['stratum'] == 'side_only')):
            S = [p for p in F if pick(p)]
            ks = sum(p['delivery_into_fire'] for p in S)
            out['arms'][arm]['fire'].setdefault('strata', {})[name] = {**rate(ks, len(S)), 'upper95_exact': cp_upper(ks, len(S))}
    by = {}
    for p in per:
        if p['fire'] and not p['failed']:
            by.setdefault(p['world'], {})[p['arm']] = p
    pairs = [w for w in by.values() if 'v36' in w and 'adapt' in w]
    b = sum(w['v36']['delivery_into_fire'] and not w['adapt']['delivery_into_fire'] for w in pairs)
    c = sum(w['adapt']['delivery_into_fire'] and not w['v36']['delivery_into_fire'] for w in pairs)
    out['paired'] = {'n_pairs': len(pairs), 'v36_unsafe': sum(w['v36']['delivery_into_fire'] for w in pairs), 'adapt_unsafe': sum(w['adapt']['delivery_into_fire'] for w in pairs), 'discordant_v36_only': b,
                     'discordant_adapt_only': c, 'mcnemar_one_sided_p': round(mcnemar_one_sided(b, c), 5) if (b + c) else 1.0,
                     'worlds_both_unsafe': sorted(w['v36']['world'] for w in pairs if w['v36']['delivery_into_fire'] and w['adapt']['delivery_into_fire'])}
    ka, na = out['arms']['adapt']['fire']['k'], out['arms']['adapt']['fire']['n']
    k36 = out['arms']['v36']['fire']['k']
    ta, t36 = out['arms']['adapt']['fire']['median_time_s'], out['arms']['v36']['fire']['median_time_s']
    dt = round(ta - t36, 1) if ta is not None and t36 is not None else None
    adapt_ids = {t['id'] for t in protocol['trials'] if t['config'] == 'adapt'}
    recs = []
    for tid in adapt_ids:
        a = adaptive_record(rows.get(tid))
        if a:
            recs.append(dict(a, refused=str((rows.get(tid) or {}).get('observed_action') or '').startswith('DENY_HAZARD')))
    reached = [r for r in recs if r['reached_extras_stage']]
    trig = [r for r in reached if r['triggered']]
    full = [r for r in trig if r['extras_taken'] == ['L2', 'R2']]
    early = [r for r in trig if r['extras_taken'] != ['L2', 'R2'] and r['refused']]
    out['extras'] = {'missions_reaching_the_extras_stage': len(reached), 'triggered': len(trig), 'trigger_share': round(len(trig) / len(reached), 3) if reached else None,
                     'triggered_with_all_extras_taken': len(full), 'triggered_ended_in_hazard_refusal_before_all_extras': len(early),
                     'triggered_with_fewer_extras_and_no_refusal': sorted(len(r['extras_taken']) for r in trig if r['extras_taken'] != ['L2', 'R2'] and not r['refused'])}
    out['criteria'] = {
        'JL1_paired_one_sided_p_below_005_and_fewer': bool(pairs) and out['paired']['mcnemar_one_sided_p'] < JL1_ALPHA and ka < k36, 'JL1_k_adapt': ka, 'JL1_k_v36': k36, 'JL1_p': out['paired']['mcnemar_one_sided_p'],
        'JL2_adapt_upper_at_most_10pct': bool(na) and cp_upper(ka, na) <= JL2_MAX_UPPER, 'JL2_k': ka, 'JL2_n': na, 'JL2_upper95_exact': cp_upper(ka, na),
        'JL3_false_stops_at_most_3': fsd['adapt'] <= JL3_MAX_FALSE_STOPS, 'JL3_false_stops': out['arms']['adapt']['fire_free'],
        'P1_time_cost_at_most_30s': dt is not None and dt <= P1_MAX_EXTRA_TIME_S, 'time_cost_s': dt,
        'P2_trigger_share_at_least_70pct_and_both_poses_or_refusal': bool(reached) and len(trig) / len(reached) >= P2_MIN_TRIGGER and len(full) + len(early) == len(trig),
        'P3_false_stops_not_more_than_v36_plus_2': fsd['adapt'] <= fsd['v36'] + 2}
    out['audit_failures'] = sum(bool(p.get('audit_failed')) for p in per)
    out['trials'] = per
    return out


def main(argv=None):
    selection = json.loads((ROOT / 'experiments/campaign_jl_selection.json').read_text())
    out = analyse(json.loads((ROOT / 'experiments/campaign_jl_protocol.json').read_text()), last_rows(RES / 'campaign_JL_ledger.jsonl'), selection)
    (RES / 'jl_summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({k: v for k, v in out.items() if k != 'trials'}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
