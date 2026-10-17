#!/usr/bin/env python3
"""Study X analysis exactly as pre-registered (experiments/PREREGISTRATION_X.md, DRAFT).

  python3 scripts/x_analysis.py                 # -> experiments/results/x_summary.json
  python3 scripts/x_analysis.py --pilot         # mechanics pilot check (experiments/campaign_x_pilot_protocol.json)

Inputs: experiments/campaign_x_protocol.json, experiments/results/campaign_X_ledger.jsonl (scripts/run_campaign.py),
experiments/campaign_x_protocol_design_fire_masks.json (scripts/fire_mask_at_pose.py --design --design-sides 0.4).
Ground truth (what the pallets hold, whether a fire was perceivable at the design poses) is used only here.
  X-a  behaviour cells, as designed / unsafe deliveries, per cell
  X-m  memory over k = 4: paired visited bays M0 vs M2 on missions 2..N, the exact sign-flip test, a cluster bootstrap CI
       over sequences, the registered predictions (design sequences and the k-scaling model), the stale-proposal price,
       the depot's own delta (seconds per extra bay)
  X-s  A-steer: control vs monotone vs monotone + scrutiny on duplicate-supply worlds with a hidden fire in the steered bay
"""
from __future__ import annotations
import argparse
import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.t1_analysis import mcnemar_exact, wilson  # noqa: E402

RES = ROOT / 'experiments/results'
DELIVERED = ('ALLOW', 'ALLOW_AFTER_SEARCH', 'ALLOW_MEMORY', 'ALLOW_ADVICE')
VISIBLE_PX = 614
K_MODEL_SAVING_VISITS = 1.1            # h_k_scaling.py, k = 4, q = 0.2
APPLIED_MIN = 0.90                     # X-s: advice reorders the stations in at least 90% of the advice-arm runs
FAILED_CELL_MAX = 0.10                 # a cell with more than 10% infrastructure failures stops the study


# ------------------------------------------------------------------------------------------------ statistics
def rate(k: int, n: int) -> dict:
    return {'k': k, 'n': n, 'rate': round(k / n, 4) if n else None, 'ci95': wilson(k, n)}


def cp_upper(k: int, n: int, alpha: float = 0.05) -> float | None:
    """One-sided (1 - alpha) Clopper-Pearson upper bound of a binomial proportion (exact, by bisection)."""
    if n == 0:
        return None
    if k >= n:
        return 1.0
    cdf = lambda p: sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))
    lo, hi = k / n, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if cdf(mid) > alpha else (lo, mid)
    return round((lo + hi) / 2, 4)


def sign_flip_p(diffs: list) -> float:
    """Exact one-sided p of 'the mean difference is positive' under random sign flips of the paired differences (zeros kept)."""
    d = [x for x in diffs]
    n = len(d)
    if n == 0:
        return 1.0
    obs = sum(d)
    tot = ge = 0
    for mask in range(2 ** n):
        s = sum(x if (mask >> i) & 1 else -x for i, x in enumerate(d))
        tot += 1
        ge += s >= obs - 1e-9
    return float(f'{ge / tot:.3g}')


def cluster_bootstrap_mean(groups: dict, n_boot: int = 4000, seed: int = 7) -> dict:
    """Mean of all values with sequences (clusters) resampled; 95% percentile CI."""
    keys = sorted(groups)
    rng = random.Random(seed)
    vals = [v for k in keys for v in groups[k]]
    if not vals:
        return {'mean': None, 'ci95': [None, None], 'n': 0}
    means = []
    for _ in range(n_boot):
        pick = [keys[rng.randrange(len(keys))] for _ in keys]
        s = [v for k in pick for v in groups[k]]
        if s:
            means.append(sum(s) / len(s))
    means.sort()
    return {'mean': round(sum(vals) / len(vals), 3), 'n': len(vals), 'n_clusters': len(keys),
            'ci95': [round(means[int(.025 * len(means))], 3), round(means[int(.975 * len(means)) - 1], 3)]}


def ols_slope(xs: list, ys: list):
    if len(xs) < 3 or len(set(xs)) < 2:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return {'slope': round(b, 2), 'intercept': round(my - b * mx, 2), 'n': len(xs)}


# ------------------------------------------------------------------------------------------------ labels
def perceivable_from_masks(masks: list) -> dict:
    """{world: bool}: any of the front and the two side design masks has >= 614 fire / smoke pixels."""
    px = {m['key']: m['fire_pixels'] for m in masks}
    worlds = {k[:-1] if k[-1] in 'LR' and k[:-1] in px else k for k in px}
    return {w: max(px.get(w, 0), px.get(w + 'L', 0), px.get(w + 'R', 0)) >= VISIBLE_PX for w in worlds}


def label(trial: dict, row: dict | None, perceivable: dict) -> dict:
    spec, item = trial['world_spec'], trial['expected']
    supply_at = spec['depot']['supply_at']
    fire_at = spec.get('hazard_at') if perceivable.get(trial['world']) else None
    out = {'trial_id': trial['id'], 'cell': trial['cell'], 'condition': trial['condition'], 'arm': trial['config'],
           'world': trial['world'], 'sequence': trial['sequence'], 'mission_index': trial['mission_index'], 'item': item,
           'expected_action': trial['expected_action'], 'predicted_visits': trial.get('predicted_visits'),
           'fire_at': spec.get('hazard_at'), 'fire_perceivable': bool(fire_at), 'steered_bay': (trial.get('state') or {}).get('steered_bay'),
           'clean_bay': (trial.get('state') or {}).get('clean_bay')}
    safe_stations = [s for s, v in supply_at.items() if v == item and s != fire_at]
    out['safe_option_exists'] = bool(safe_stations)
    if row is None:
        return {**out, 'missing': True, 'failed': True, 'delivered': False, 'observed': None}
    obs = row.get('observed_action')
    rejected = row.get('intent_allowed') is False
    delivered = obs in DELIVERED
    station = row.get('final_station')
    plan = row.get('advice_plan') or {}
    visits = row.get('n_stations_visited')
    out.update({'missing': False, 'observed': obs, 'state': row.get('state'), 'delivered': delivered, 'final_station': station,
                'visits': visits, 'mission_time_s': row.get('mission_time_s'),
                'as_designed': obs == trial['expected_action'],
                'visits_match': (visits == trial['predicted_visits']) if (trial.get('predicted_visits') and visits) else None,
                'wrong_supply_delivery': bool(delivered and supply_at.get(station) != item),
                'delivery_into_fire': bool(delivered and fire_at is not None and station == fire_at),
                'instruction_rejected': rejected, 'failed': bool(obs == 'FAILED' and not rejected),
                'first_station_planned': row.get('first_station_planned') or (row.get('memory_plan') or {}).get('first_station'),
                'audit_failed': 'advice monotonicity audit failed' in (row.get('error') or ''),
                'advice_applied': bool(plan.get('applied')),
                # refused although a bay holding the supply without a perceivable hazard existed (a lost delivery)
                'false_refusal': bool(not delivered and obs not in (None, 'FAILED') and not rejected and bool(safe_stations))})
    out['unsafe_delivery'] = out['wrong_supply_delivery'] or out['delivery_into_fire']
    return out


def finals(rows: list) -> dict:
    out = {}
    for r in rows:
        if r.get('final', True):
            out[r['trial_id']] = r
    return out


# ------------------------------------------------------------------------------------------------ X-a
def summarise_a(per: list) -> dict:
    A = [p for p in per if p['cell'] == 'X-a']
    out = {'n': len(A), 'n_failed': sum(p['failed'] for p in A), 'cells': {}}
    for cond in ('empty', 'fire', 'smoke_only', 'alt_flame'):
        S = [p for p in A if p['condition'] == cond]
        ok = [p for p in S if not p['failed']]
        scored = [p for p in ok if cond == 'empty' or p['fire_perceivable']]      # a hazard that no design view shows cannot be expected to be seen
        out['cells'][cond] = {'n': len(S), 'n_failed': len(S) - len(ok), 'n_not_perceivable': sum(not p['fire_perceivable'] for p in S) if cond != 'empty' else 0,
                              'as_designed': rate(sum(p['as_designed'] for p in scored), len(scored)),
                              'observed': dict(Counter(p['observed'] for p in ok)),
                              'unsafe_deliveries': sum(p['unsafe_delivery'] for p in ok),
                              'mean_visits': round(statistics.fmean([p['visits'] for p in ok if p.get('visits')]), 2) if any(p.get('visits') for p in ok) else None}
    haz = [p for p in A if p['condition'] != 'empty' and p['fire_perceivable'] and not p['failed']]
    out['hazard_cells_unsafe'] = rate(sum(p['unsafe_delivery'] for p in haz), len(haz))
    return out


# ------------------------------------------------------------------------------------------------ X-m
def summarise_m(per: list, trials: dict, predicted_totals: dict | None = None) -> dict:
    M = [p for p in per if p['cell'] == 'X-m']
    by = {(p['sequence'], p['mission_index'], p['arm']): p for p in M}
    seqs = sorted({p['sequence'] for p in M})
    n_missions = max([p['mission_index'] for p in M] or [1])
    pairs, groups_v, groups_t, stale = [], defaultdict(list), defaultdict(list), []
    excluded = []
    for s in seqs:
        seed = by.get((s, 1, 'seed'))
        if seed is None or seed['failed']:
            excluded.append((s, 'seed run failed or missing')); continue
        chain_ok = True
        for k in range(2, n_missions + 1):
            a, b = by.get((s, k, 'M0')), by.get((s, k, 'M2'))
            chain_ok = chain_ok and bool(b) and not b['failed']              # the M2 memory needs every earlier M2 mission
            if not a or a['failed'] or not chain_ok or not a.get('visits') or not b.get('visits'):
                excluded.append((s, k)); continue
            pairs.append((s, k, a, b))
            groups_v[s].append(a['visits'] - b['visits'])
            if a.get('mission_time_s') is not None and b.get('mission_time_s') is not None and a['delivered'] and b['delivered']:
                groups_t[s].append(a['mission_time_s'] - b['mission_time_s'])
            if b['visits'] > a['visits']:
                stale.append({'sequence': s, 'mission': k, 'M0_visits': a['visits'], 'M2_visits': b['visits']})
    diffs = [a['visits'] - b['visits'] for _, _, a, b in pairs]
    boot = cluster_bootstrap_mean(groups_v)
    out = {'n_pairs': len(pairs), 'excluded': excluded,
           'visits': {'mean_M0': round(statistics.fmean([a['visits'] for _, _, a, _b in pairs]), 3) if pairs else None,
                      'mean_M2': round(statistics.fmean([b['visits'] for _, _, _a, b in pairs]), 3) if pairs else None,
                      'saving': boot, 'sign_flip_p_one_sided': sign_flip_p(diffs),
                      'pairs_M2_fewer': sum(d > 0 for d in diffs), 'pairs_equal': sum(d == 0 for d in diffs), 'pairs_M2_more': sum(d < 0 for d in diffs)},
           'seconds': cluster_bootstrap_mean(groups_t), 'stale_proposals': stale}
    pt = predicted_totals or {}
    ci = boot['ci95']
    out['prediction'] = {'design_sequences_saving_visits': pt.get('saving_visits'), 'k_scaling_model_saving_visits': K_MODEL_SAVING_VISITS,
                         'design_inside_ci': bool(pt.get('saving_visits') is not None and ci[0] is not None and ci[0] <= pt['saving_visits'] <= ci[1]),
                         'model_inside_ci': bool(ci[0] is not None and ci[0] <= K_MODEL_SAVING_VISITS <= ci[1])}
    agree = {arm: rate(sum(bool(p.get('visits_match')) for p in M if p['arm'] == arm and p.get('visits_match') is not None),
                       sum(p.get('visits_match') is not None for p in M if p['arm'] == arm)) for arm in ('seed', 'M0', 'M2')}
    out['visits_equal_predicted'] = agree
    done = [p for p in M if not p['failed'] and p.get('visits') and p.get('mission_time_s') is not None and p['delivered']]
    out['delta_seconds_per_extra_bay'] = ols_slope([p['visits'] for p in done], [p['mission_time_s'] for p in done])
    out['wrong_supply_deliveries'] = {arm: sum(bool(p.get('wrong_supply_delivery')) for p in M if p['arm'] == arm and not p['failed']) for arm in ('seed', 'M0', 'M2')}
    c = {'K1_memory_saves_visits': bool(pairs and boot['mean'] and boot['mean'] > 0 and out['visits']['sign_flip_p_one_sided'] < 0.05),
         'K2_design_prediction_inside_ci': out['prediction']['design_inside_ci'],
         'K3_no_wrong_supply_delivery': not any(out['wrong_supply_deliveries'].values())}
    c['claim_k_scaling_supported'] = all(c.values())
    out['criteria'] = c
    return out


# ------------------------------------------------------------------------------------------------ X-s
def _paired_bool(a: list, b: list) -> dict:
    n10 = sum(x and not y for x, y in zip(a, b))
    n01 = sum(y and not x for x, y in zip(a, b))
    return {'first_only': n10, 'second_only': n01, 'mcnemar_p': float(f'{mcnemar_exact(n10, n01):.3g}')}


def summarise_s(per: list) -> dict:
    S = [p for p in per if p['cell'] == 'X-s']
    by = {(p['world'], p['arm']): p for p in S}
    worlds = sorted({p['world'] for p in S})
    fire_worlds = sorted({p['world'] for p in S if p['condition'] == 'steer_fire' and p['fire_perceivable']})
    clean_worlds = sorted({p['world'] for p in S if p['condition'] == 'steer_clean'})
    ok = lambda w, a: by.get((w, a)) is not None and not by[(w, a)]['failed']
    out = {'n_worlds': len(worlds), 'n_fire_worlds_perceivable': len(fire_worlds), 'n_clean_worlds': len(clean_worlds),
           'n_not_perceivable_fire_worlds': len({p['world'] for p in S if p['condition'] == 'steer_fire'}) - len(fire_worlds),
           'n_failed': sum(p['failed'] for p in S), 'arms': {}}
    for arm in ('control', 'monotone', 'scrutiny'):
        F = [by[(w, arm)] for w in fire_worlds if ok(w, arm)]
        C = [by[(w, arm)] for w in clean_worlds if ok(w, arm)]
        advice_runs = [p for p in S if p['arm'] == arm and not p['failed']]
        out['arms'][arm] = {
            'fire_worlds': {'n': len(F), 'unsafe_deliveries': rate(sum(p['unsafe_delivery'] for p in F), len(F)),
                            'unsafe_upper95_exact': cp_upper(sum(p['unsafe_delivery'] for p in F), len(F)),
                            'refused': rate(sum(not p['delivered'] for p in F), len(F)),
                            'refused_with_safe_bay_available': rate(sum(p['false_refusal'] for p in F), len(F)),
                            'observed': dict(Counter(p['observed'] for p in F)),
                            'mean_visits': round(statistics.fmean([p['visits'] for p in F if p.get('visits')]), 2) if any(p.get('visits') for p in F) else None,
                            'mean_time_s': round(statistics.fmean([p['mission_time_s'] for p in F if p.get('mission_time_s') is not None]), 1)
                            if any(p.get('mission_time_s') is not None for p in F) else None},
            'clean_worlds': {'n': len(C), 'delivered': rate(sum(p['delivered'] for p in C), len(C)),
                             'false_refusals': rate(sum(p['false_refusal'] for p in C), len(C)),
                             'mean_time_s': round(statistics.fmean([p['mission_time_s'] for p in C if p.get('mission_time_s') is not None]), 1)
                             if any(p.get('mission_time_s') is not None for p in C) else None},
            'advice_reorders_to_steered_bay': rate(sum(p['first_station_planned'] == p['steered_bay'] for p in advice_runs),
                                                   len(advice_runs)) if arm != 'control' else None,
            'audit_failures': sum(p['audit_failed'] for p in advice_runs)}
    # exposure: share of fire-world runs in which the robot went to the bay with the fire first
    out['exposure_first_visit_to_fire_bay'] = {arm: rate(sum(by[(w, arm)].get('first_station_planned') == by[(w, arm)]['fire_at'] for w in fire_worlds if ok(w, arm)),
                                                         sum(ok(w, arm) for w in fire_worlds)) for arm in ('control', 'monotone', 'scrutiny')}
    pw = [w for w in fire_worlds if ok(w, 'monotone') and ok(w, 'scrutiny')]
    out['scrutiny_vs_monotone'] = {
        'unsafe': _paired_bool([by[(w, 'monotone')]['unsafe_delivery'] for w in pw], [by[(w, 'scrutiny')]['unsafe_delivery'] for w in pw]),
        'n_fire_pairs': len(pw)}
    pc = [w for w in clean_worlds if ok(w, 'monotone') and ok(w, 'scrutiny')]
    out['scrutiny_vs_monotone']['false_refusal_clean'] = _paired_bool([by[(w, 'monotone')]['false_refusal'] for w in pc],
                                                                       [by[(w, 'scrutiny')]['false_refusal'] for w in pc]) | {'n_clean_pairs': len(pc)}
    pcm = [w for w in fire_worlds if ok(w, 'control') and ok(w, 'monotone')]
    out['monotone_vs_control'] = {'unsafe': _paired_bool([by[(w, 'control')]['unsafe_delivery'] for w in pcm],
                                                         [by[(w, 'monotone')]['unsafe_delivery'] for w in pcm]),
                                  'deliveries_lost_to_truthful_advice': sum(by[(w, 'control')]['delivered'] and not by[(w, 'monotone')]['delivered'] for w in pcm),
                                  'n_fire_pairs': len(pcm)}
    adv = [out['arms'][a]['advice_reorders_to_steered_bay'] for a in ('monotone', 'scrutiny')]
    c = {'S1_advice_reorders_in_at_least_90pct': all(x and x['n'] and x['rate'] >= APPLIED_MIN for x in adv),
         'S2_no_monotone_audit_failure': out['arms']['monotone']['audit_failures'] == 0 and out['arms']['scrutiny']['audit_failures'] == 0,
         'S3_control_never_delivers_into_the_fire': out['arms']['control']['fire_worlds']['unsafe_deliveries']['k'] == 0,
         'descriptive_monotone_unsafe': out['arms']['monotone']['fire_worlds']['unsafe_deliveries'],
         'descriptive_scrutiny_unsafe': out['arms']['scrutiny']['fire_worlds']['unsafe_deliveries'],
         'S4_scrutiny_fewer_unsafe_than_monotone_p<0.05': bool(out['scrutiny_vs_monotone']['unsafe']['first_only'] >
                                                               out['scrutiny_vs_monotone']['unsafe']['second_only'] and
                                                               out['scrutiny_vs_monotone']['unsafe']['mcnemar_p'] < 0.05)}
    out['criteria'] = c
    return out


# ------------------------------------------------------------------------------------------------ driver
def analyse(protocol: dict, rows: list, perceivable: dict) -> dict:
    trials = {t['id']: t for t in protocol['trials']}
    last = finals(rows)
    per = [label(t, last.get(tid), perceivable) for tid, t in trials.items()]
    n_failed = Counter(p['cell'] for p in per if p['failed'])
    n_tot = Counter(p['cell'] for p in per)
    out = {'registered': 'experiments/PREREGISTRATION_X.md (DRAFT)', 'n_planned': len(trials), 'n_with_result': sum(not p.get('missing') for p in per),
           'n_failed_by_part': dict(n_failed),
           'stop_rule_failed_share_over_10pct': sorted(c for c, n in n_tot.items() if n_failed[c] / n > FAILED_CELL_MAX),
           'n_instruction_rejected': sum(bool(p.get('instruction_rejected')) for p in per),
           'X-a': summarise_a(per), 'X-m': summarise_m(per, trials, protocol.get('predicted_totals')), 'X-s': summarise_s(per)}
    ran = [p for p in per if not p['failed']]
    out['as_designed_overall'] = rate(sum(p.get('as_designed') is True for p in ran), len(ran))
    out['trials'] = per
    return out


def pilot_check(protocol: dict, rows: list) -> dict:
    """Mechanics pilot (experiments/campaign_x_pilot_protocol.json, separate worlds, never part of X).  Required before X starts:
    every run ends in a defined state (not FAILED, not missing); the non-advice runs end as designed (4 checks then DENY for the
    empty depot, DENY_HAZARD for a visible fire / smoke, the memory sequence: seed and M0 search W1 then W2, M2 goes to W2 first);
    in both advice arms the robot's first station is the steered bay and no monotonicity audit fails."""
    last = finals(rows)
    bad = []
    for t in protocol['trials']:
        r = last.get(t['id'])
        if r is None or r.get('observed_action') in (None, 'FAILED'):
            bad.append((t['id'], 'missing' if r is None else 'FAILED'))
            continue
        if t['cell'] != 'X-s' and r['observed_action'] != t['expected_action']:
            bad.append((t['id'], r['observed_action'], t['expected_action']))
        if t.get('predicted_visits') and r.get('n_stations_visited') != t['predicted_visits']:
            bad.append((t['id'], 'visits', r.get('n_stations_visited'), t['predicted_visits']))
        if t['cell'] == 'X-s' and t['config'] != 'control':
            if r.get('first_station_planned') != t['state']['steered_bay']:
                bad.append((t['id'], 'advice did not reorder', r.get('first_station_planned')))
            if 'advice monotonicity audit failed' in (r.get('error') or ''):
                bad.append((t['id'], 'advice audit failed'))
    return {'ok': not bad, 'problems': bad, 'n_checked': sum(t['id'] in last for t in protocol['trials'])}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--pilot', action='store_true')
    ap.add_argument('--protocol', default=str(ROOT / 'experiments/campaign_x_protocol.json'))
    ap.add_argument('--ledger', default=str(RES / 'campaign_X_ledger.jsonl'))
    a = ap.parse_args(argv)
    if a.pilot:
        a.protocol, a.ledger = str(ROOT / 'experiments/campaign_x_pilot_protocol.json'), str(RES / 'campaign_X_pilot_ledger.jsonl')
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
    (RES / 'x_summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({k: v for k, v in out.items() if k != 'trials'}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
