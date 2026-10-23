#!/usr/bin/env python3
"""Study JK (I-107): suspicion-triggered extra views (I-20) in the closed loop at the depot, on GM's worlds; the registered analysis (experiments/PREREGISTRATION_JK.md).

  python3 scripts/jk_analysis.py [--pilot]    # -> experiments/results/jk_summary.json

New arm `adapt` (v3.6 + --adaptive-views 0.8) on GM's 100 fire worlds and 32 fire-free worlds.  The comparators `v36` and `left` are GM's own final rows of the same worlds (NOT concurrent).
A delivery in a fire world is a delivery into a fire.

Claims (registered):
  JK1  adapt delivers into fewer fires than v36: exact ONE-sided McNemar over the fire worlds gives p < 0.05 and k_adapt < k_v36  (structural: extra views run after every standard view passed and can only add refusals;
       it tests whether the extra poses are reached and catch anything in the closed loop).
  JK2  budget: adapt's delivery into a perceivable fire, exact one-sided 95% upper bound at most 10% (k <= 4 of 100; predicted 4-6, a coin flip).
  JK3  false stops: adapt refuses at most 3 of the 32 fire-free worlds for a hazard (forecast from GV's calibration: about 1).
Descriptive (predictions registered, failing them is reported, not a failed claim): P1 adapt delivers into no more fires than left (GM's left-only arm); P2 the median mission time of adapt exceeds v36's by at most 30 s;
P3 the extra views (L2, R2) are triggered in at least 70% of the missions that pass the standard views and every triggered mission takes both or ends in a refusal.
Infrastructure failures are excluded from the claims and listed; more than 10% fail stops the campaign.
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
from scripts.gm_analysis import mcnemar_one_sided, label, _med, DELIVERED  # noqa: E402

RES = ROOT / 'experiments/results'
JK1_ALPHA = 0.05
JK2_MAX_UPPER = 0.10
JK3_MAX_FALSE_STOPS = 3
P2_MAX_EXTRA_TIME_S = 30.0
P3_MIN_TRIGGER = 0.70
FAILED_MAX = 0.10


def last_rows(path: Path) -> dict:
    out = {}
    for x in path.read_text(encoding='utf8').splitlines():
        if x.strip():
            r = json.loads(x)
            if r.get('final', True):
                out[r['trial_id']] = r
    return out


def adaptive_record(row: dict | None) -> dict | None:
    rid = (row or {}).get('run_id')
    f = ROOT / 'outputs/runs' / str(rid) / 'mission.json'
    if not f.is_file():
        return None
    la = json.loads(f.read_text(encoding='utf8')).get('look_around') or {}
    ad = la.get('adaptive')
    taken = sorted({q.get('side') for q in la.get('peeks', [])} & {'L2', 'R2', 'N'})       # Amendment 2: the arm has L2 and R2 only (N dropped)
    return {'reached_extras_stage': ad is not None, 'triggered': bool((ad or {}).get('triggered')), 'p_max': (ad or {}).get('p_max'), 'extras_taken': taken}


def analyse(jk_protocol: dict, jk_rows: dict, gm_protocol: dict, gm_rows: dict, selection: dict) -> dict:
    px = selection.get('design_pixels', {})
    per = {'adapt': [], 'v36': [], 'left': []}
    for t in jk_protocol['trials']:
        per['adapt'].append(label({**t, 'config': 'adapt'}, jk_rows.get(t['id']), px))
    gm_by_world = {}
    for t in gm_protocol['trials']:
        gm_by_world.setdefault((t['world'], t['config']), t)
    for (w, arm), t in gm_by_world.items():
        if arm in ('v36', 'left'):
            per[arm].append(label(t, gm_rows.get(t['id']), px))
    worlds_jk = {t['world'] for t in jk_protocol['trials']}
    for arm in ('v36', 'left'):
        per[arm] = [p for p in per[arm] if p['world'] in worlds_jk]
    n_failed = sum(p['failed'] for p in per['adapt'])
    out = {'registered': 'experiments/PREREGISTRATION_JK.md', 'n_planned': len(jk_protocol['trials']), 'n_with_result': sum(not p.get('missing') for p in per['adapt']), 'n_failed': n_failed,
           'stop_rule_failed_share_over_10pct': n_failed / max(1, len(per['adapt'])) > FAILED_MAX, 'n_fire_worlds': len(selection.get('selected') or []), 'arms': {}, 'comparators': 'GM final rows, not concurrent'}
    ok = lambda arm, fire: [p for p in per[arm] if p['fire'] == fire and not p['failed']]
    for arm in ('adapt', 'v36', 'left'):
        F = ok(arm, True)
        k = sum(p['delivery_into_fire'] for p in F)
        P = ok(arm, False)
        fs = sum(p['false_hazard_stop'] for p in P)
        out['arms'][arm] = {'fire': {**rate(k, len(F)), 'upper95_exact': cp_upper(k, len(F)), 'worlds_unsafe': sorted(p['world'] for p in F if p['delivery_into_fire']), 'median_time_s': _med([p['mission_time_s'] for p in F]),
                                     'observed': {o: sum(p['observed'] == o for p in F) for o in sorted({p['observed'] for p in F})}},
                            'fire_free': {**rate(fs, len(P)), 'worlds_stopped': sorted(p['world'] for p in P if p['false_hazard_stop']), 'median_time_s': _med([p['mission_time_s'] for p in P])}}

    def pair(a, b):
        A = {p['world']: p for p in ok(a, True)}
        B = {p['world']: p for p in ok(b, True)}
        ws = sorted(set(A) & set(B))
        x = sum(A[w]['delivery_into_fire'] and not B[w]['delivery_into_fire'] for w in ws)       # a unsafe only
        y = sum(B[w]['delivery_into_fire'] and not A[w]['delivery_into_fire'] for w in ws)
        return {'n_pairs': len(ws), f'{a}_only_unsafe': x, f'{b}_only_unsafe': y, 'mcnemar_one_sided_p_a_worse': round(mcnemar_one_sided(x, y), 5) if (x + y) else 1.0,
                'both_unsafe': sorted(w for w in ws if A[w]['delivery_into_fire'] and B[w]['delivery_into_fire'])}
    out['paired_v36_vs_adapt'] = pair('v36', 'adapt')
    out['paired_left_vs_adapt'] = pair('left', 'adapt')
    ka, na = out['arms']['adapt']['fire']['k'], out['arms']['adapt']['fire']['n']
    k36 = out['arms']['v36']['fire']['k']
    kl = out['arms']['left']['fire']['k']
    dt = None
    ta, t36 = out['arms']['adapt']['fire']['median_time_s'], out['arms']['v36']['fire']['median_time_s']
    if ta is not None and t36 is not None:
        dt = round(ta - t36, 1)
    # mechanics: how often the extra views were reached, triggered and taken (missions that passed the standard views)
    recs = [adaptive_record(jk_rows.get(t['id'])) for t in jk_protocol['trials']]
    reached = [r for r in recs if r and r['reached_extras_stage']]
    trig = [r for r in reached if r['triggered']]
    full = [r for r in trig if r['extras_taken'] == ['L2', 'R2']]
    out['extras'] = {'missions_reaching_the_extras_stage': len(reached), 'triggered': len(trig), 'trigger_share': round(len(trig) / len(reached), 3) if reached else None,
                     'triggered_with_all_extras_taken': len(full), 'triggered_with_fewer_extras': sorted(len(r['extras_taken']) for r in trig if r['extras_taken'] != ['L2', 'R2'])}
    P = ok('adapt', False)
    fsa = sum(p['false_hazard_stop'] for p in P)
    out['criteria'] = {
        'JK1_paired_one_sided_p_below_005_and_fewer': na > 0 and out['paired_v36_vs_adapt']['mcnemar_one_sided_p_a_worse'] < JK1_ALPHA and ka < k36, 'JK1_k_adapt': ka, 'JK1_k_v36': k36, 'JK1_p': out['paired_v36_vs_adapt']['mcnemar_one_sided_p_a_worse'],
        'JK2_adapt_upper_at_most_10pct': bool(na) and cp_upper(ka, na) <= JK2_MAX_UPPER, 'JK2_k': ka, 'JK2_n': na, 'JK2_upper95_exact': cp_upper(ka, na),
        'JK3_false_stops_at_most_3': bool(P) and fsa <= JK3_MAX_FALSE_STOPS, 'JK3_false_stops': rate(fsa, len(P)),
        'P1_adapt_not_more_than_left': ka <= kl, 'P2_time_cost_at_most_30s': dt is not None and dt <= P2_MAX_EXTRA_TIME_S, 'time_cost_s': dt,
        'P3_trigger_share_at_least_70pct_and_all_extras_taken': bool(reached) and len(trig) / len(reached) >= P3_MIN_TRIGGER and len(full) == len(trig)}
    out['audit_failures'] = sum(bool(p.get('audit_failed')) for p in per['adapt'])
    out['trials'] = per['adapt']
    return out


def pilot_check(protocol: dict, rows: dict) -> dict:
    """Mechanics pilot (4 runs, never part of JK): the large fire is refused for a hazard at the front under the real arm; each fire-free pilot world, run with the extra views FORCED (tau_sus 0), takes the
    L2 and R2 poses with a model call each and no N pose (Amendment 2), end in a defined state, nothing failed, no audit failure."""
    per = {t['id']: label(t, rows.get(t['id']), {}) for t in protocol['trials']}
    fire = next(p for p in per.values() if p['fire'])
    checks = {'all_defined': all(not p['failed'] and not p.get('missing') for p in per.values()), 'fire_world_refused_for_hazard': fire.get('hazard_refused') is True, 'no_audit_failure': all(not p.get('audit_failed') for p in per.values())}
    forced = []
    for t in protocol['trials']:
        if t['config'] != 'adapt_forced':
            continue
        rid = (rows.get(t['id']) or {}).get('run_id')
        f = ROOT / 'outputs/runs' / str(rid) / 'mission.json'
        if not f.is_file():
            forced.append(False)
            continue
        la = json.loads(f.read_text(encoding='utf8')).get('look_around') or {}
        peeks = {q.get('side'): q for q in la.get('peeks', [])}
        forced.append(bool((la.get('adaptive') or {}).get('triggered')) and all(s in peeks and (peeks[s].get('model_calls') or {}).get('first') for s in ('L2', 'R2')) and 'N' not in peeks)
    checks['forced_runs_took_L2_R2_with_model_calls_and_no_N'] = bool(forced) and all(forced)
    return {'ok': all(checks.values()), 'checks': checks, 'runs': [{k: p.get(k) for k in ('trial_id', 'arm', 'observed')} for p in per.values()]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--pilot', action='store_true')
    a = ap.parse_args(argv)
    if a.pilot:
        proto = json.loads((ROOT / 'experiments/campaign_jk_pilot_protocol.json').read_text())
        r = pilot_check(proto, last_rows(RES / 'campaign_JK_pilot_ledger.jsonl'))
        print(json.dumps(r, indent=1))
        raise SystemExit(0 if r['ok'] else 1)
    selection = json.loads((ROOT / 'experiments/campaign_gm_selection.json').read_text())
    out = analyse(json.loads((ROOT / 'experiments/campaign_jk_protocol.json').read_text()), last_rows(RES / 'campaign_JK_ledger.jsonl'),
                  json.loads((ROOT / 'experiments/campaign_gm_protocol.json').read_text()), last_rows(RES / 'campaign_GM_ledger.jsonl'), selection)
    (RES / 'jk_summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({k: v for k, v in out.items() if k != 'trials'}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
