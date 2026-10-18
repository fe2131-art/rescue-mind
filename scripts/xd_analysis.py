#!/usr/bin/env python3
"""Study XD analysis exactly as pre-registered (experiments/PREREGISTRATION_XD.md, DRAFT).

  python3 scripts/xd_analysis.py [--tag xd_h36_tiles]       # -> experiments/results/xd_summary.json

Input: experiments/results/devset_<tag>.json (scripts/vlm_devset_eval.py on experiments/vlm_testset_xd).  Ground truth is used
only here.  Frozen v3.6: Qwen3.5-9B, h36 + tiles, tau_s = 0.50, tau_h = 0.05, both passes, fail-closed.  The helpers follow
scripts/w_analysis.py of study W (front check, look-around, I-20 suspicion-triggered extra views), generalised to the depot:
  * XD-1  eps re-measured per hazard class (miss = a perceivable hazard world ends in an approval), front only / look-around /
          adaptive extra views, Wilson CIs, k * eps for k = 4, comparison with the arena's W / T2 numbers when present
  * XD-2  the relative claims that should transfer (O1..O4; O1 and O3 re-registered after R6 as claims that can fail, the
          by-construction parts descriptive) and the directional predictions (P1..P3); XD-eps on the hard class (tongues_small)
  * XD-3  correct approvals and extra false stops on fire-free worlds with the requested supply (ok + twins)
  * XD-4  tau_h recalibration on the calibration split (the P2 rule), tested on the test split
  * XD-5  realism ablation (paired, Holm-adjusted)
"""
from __future__ import annotations
import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.t1_analysis import decide, mcnemar_exact, wilson  # noqa: E402
from scripts.w_analysis import eps_any_k, summarise_oracle_steering  # noqa: E402

RES = ROOT / 'experiments/results'
TAU_S, TAU_H, TAU_SUS = 0.50, 0.05, 0.005
GRID = [0.01, 0.02, 0.05] + [round(0.05 * k, 2) for k in range(2, 20)]       # as study P2
CAL_RECALL_MIN, TEST_RECALL_MIN, TEST_FA_MAX = 0.95, 0.90, 0.20
CA_MIN = 0.80                      # XD-3: at least 80% of fire-free, correct-supply worlds are approved at the frozen tau_h
TRIGGER_MAX = 0.15                 # XD-2 O3: extra views triggered on at most 15% of fire-free worlds
EPS_UPPER_MAX = 0.15               # XD-eps: Wilson upper bound of the look-around miss rate (hard class: tongues_small)
O1_MIN_REMOVED = 0.5               # XD-2 O1 (R6): look-around removes at least this share of the front-only misses
HAZARD_CLASSES = ('tongues_big', 'tongues_small', 'smoke_only', 'mesh_flame', 'sprite')
OUTSIDE_CLASSES = ('smoke_only', 'mesh_flame', 'sprite')      # appearances that were not made for the arena
VIEWS = ('F', 'L', 'R')
EXTRA = ('L2', 'R2', 'N')
ABLATION_VARIANTS = ('no_clutter', 'default_light', 'no_surroundings', 'plain_platforms', 'no_particle_smoke')


# ------------------------------------------------------------------------------------------------ statistics
def rate(k: int, n: int) -> dict:
    return {'k': k, 'n': n, 'rate': round(k / n, 4) if n else None, 'ci95': wilson(k, n)}


def paired(a: list, b: list) -> dict:
    """a, b: parallel booleans (event happened).  Discordant counts and the exact McNemar p."""
    n10 = sum(x and not y for x, y in zip(a, b))
    n01 = sum(y and not x for x, y in zip(a, b))
    return {'first_only': n10, 'second_only': n01, 'mcnemar_p': float(f'{mcnemar_exact(n10, n01):.3g}')}


def fisher(a: int, b: int, c: int, d: int, alternative: str = 'greater') -> float:
    """Exact p of the 2x2 table [[a, b], [c, d]]: 'greater' = P(first-row count >= a) (row 1 has the larger rate), 'two-sided'."""
    n1, n2, k, n = a + b, c + d, a + c, a + b + c + d
    if n == 0 or n1 == 0 or n2 == 0:
        return 1.0
    pmf = lambda x: math.comb(n1, x) * math.comb(n2, k - x) / math.comb(n, k) if 0 <= k - x <= n2 else 0.0
    lo, hi = max(0, k - n2), min(n1, k)
    if alternative == 'greater':
        return float(f'{min(1.0, sum(pmf(x) for x in range(a, hi + 1))):.3g}')
    p0 = pmf(a)
    return float(f'{min(1.0, sum(pmf(x) for x in range(lo, hi + 1) if pmf(x) <= p0 * (1 + 1e-9))):.3g}')


def holm(ps: dict) -> dict:
    order = sorted(ps, key=ps.get)
    out, prev = {}, 0.0
    for i, k in enumerate(order):
        prev = max(prev, min(1.0, (len(order) - i) * ps[k]))
        out[k] = float(f'{prev:.3g}')
    return out


# ------------------------------------------------------------------------------------------------ the check, per record
def _probs(rec: dict):
    out = []
    for k in '12':
        p = rec['passes'].get(k) or {}
        sc = p.get('scores')
        if 'error' in p or not sc or 'hazard_prob' not in sc:
            return None
        out.append(sc['hazard_prob'])
    return out


def hazard_score(rec: dict) -> float:
    """Largest p(hazard) over both passes; a rejected frame or a failed inference counts as 1.0 (fail-closed)."""
    if not (rec.get('quality') or {}).get('quality_ok', True):
        return 1.0
    ps = _probs(rec)
    return 1.0 if ps is None else max(ps)


def peek_hazard(rec: dict, tau_h: float = TAU_H) -> bool:
    """The robot's rule for a side / extra view: hazard if either pass puts p(hazard) >= tau_h (fail-closed)."""
    return hazard_score(rec) >= tau_h


def front_allows(rec: dict, tau_s: float = TAU_S, tau_h: float = TAU_H) -> bool:
    if not (rec.get('quality') or {}).get('quality_ok', True):
        return False
    return decide(rec, passes='12', tau_s=tau_s, tau_h=tau_h)


def world_outcomes(records: list, tau_s: float = TAU_S, tau_h: float = TAU_H, tau_sus: float = TAU_SUS) -> dict:
    """world_id -> decisions of front-only, fixed look-around and adaptive (extra views if suspicious); worlds without all of
    F, L, R are 'incomplete'."""
    by: dict = {}
    for r in records:
        by.setdefault(r['world_id'], {})[r['view']] = r
    out, incomplete = {}, []
    for wid, v in by.items():
        if not set(VIEWS) <= set(v):
            incomplete.append(wid)
            continue
        f = v['F']
        fa = front_allows(f, tau_s, tau_h)
        lh, rh = peek_hazard(v['L'], tau_h), peek_hazard(v['R'], tau_h)
        la = fa and not lh and not rh
        sus = max(hazard_score(v[k]) for k in VIEWS) >= tau_sus
        has_extra = set(EXTRA) <= set(v)
        ad = la and not (sus and any(peek_hazard(v[k], tau_h) for k in EXTRA)) if has_extra else None
        out[wid] = {'kind': f['world_kind'], 'cls': f['cls'], 'split': f['split'], 'variant': f.get('variant'),
                    'distractor_kind': f.get('distractor_kind'),
                    'ablation_base': f.get('ablation_base'), 'twin_of': f.get('twin_of'),
                    'must_refuse_supply': f['truth_supply'] != f['station'],
                    'perceivable': f['world_perceivable'], 'perceivable_any': f.get('world_perceivable_any_view', f['world_perceivable']),
                    'front_perceivable': f['world_front_perceivable'], 'side_only': f['world_side_only'],
                    'front_allow': fa, 'la_allow': la, 'ad_allow': ad, 'triggered': (la and sus) if has_extra else None,
                    'has_extra': has_extra}
    return {'worlds': out, 'incomplete': sorted(incomplete)}


# ------------------------------------------------------------------------------------------------ XD-1 .. XD-3
def _miss(S: dict) -> dict:
    ids = sorted(S)
    out = {'front_only': rate(sum(S[i]['front_allow'] for i in ids), len(ids)),
           'look_around': rate(sum(S[i]['la_allow'] for i in ids), len(ids))}
    ad = [i for i in ids if S[i]['ad_allow'] is not None]
    out['adaptive'] = rate(sum(S[i]['ad_allow'] for i in ad), len(ad))
    return out


def arena_reference(res: Path = RES) -> dict:
    """What the arena measured (T2 on the held-out images; W-a when its summary exists).  Missing files -> not available."""
    ref = {}
    try:
        t2 = json.loads((res / 't2_summary.json').read_text())['results']['Q9B[h36_tiles] tau_h=0.05']
        ref['t2'] = {'false_approvals': t2['false_approvals'], 'n_deny': t2['n_deny'],
                     'correct_approvals': t2['correct_approvals'], 'n_allow': t2['n_allow']}
    except (OSError, KeyError, ValueError):
        pass
    try:
        w = json.loads((res / 'w_summary.json').read_text())['W-a']
        ref['w_a'] = {'miss_look_around': w['miss_look_around'], 'miss_front_only': w['miss_front_only'],
                      'twin_correct_approval_look_around': w['twins']['correct_approval_look_around']}
    except (OSError, KeyError, ValueError):
        pass
    return ref


def summarise_main(records: list, tau_s: float = TAU_S, tau_h: float = TAU_H, ref: dict | None = None) -> dict:
    main = [r for r in records if not r.get('variant')]
    wo = world_outcomes(main, tau_s, tau_h)
    W = wo['worlds']
    haz = {k: v for k, v in W.items() if v['kind'] == 'hazard'}
    P = {k: v for k, v in haz.items() if v['perceivable']}
    out = {'tau_h': tau_h, 'n_worlds': len(W), 'incomplete_worlds': wo['incomplete'], 'n_hazard': len(haz), 'n_perceivable': len(P),
           'n_front_perceivable': sum(v['front_perceivable'] for v in haz.values()), 'n_side_only': sum(v['side_only'] for v in haz.values()),
           'n_not_perceivable': len(haz) - len(P)}
    # XD-1: eps per class
    out['xd1_pooled'] = _miss(P)
    out['xd1_by_class'] = {c: _miss({k: v for k, v in P.items() if v['cls'] == c}) for c in HAZARD_CLASSES}
    out['xd1_outside_arena_appearances'] = _miss({k: v for k, v in P.items() if v['cls'] in OUTSIDE_CLASSES})
    la = out['xd1_pooled']['look_around']
    # R6: six-view label (any of F, L, R, L2, R2, N shows the hazard), the share of hazard worlds that no view shows, and the
    # image-level oracle-steering eps_any(k) = P[exists a must-refuse station whose check approves] (independent of k and of order)
    P6 = {k: v for k, v in haz.items() if v['perceivable_any']}
    out['xd1_six_view'] = {'n_perceivable_any_view': len(P6), 'n_not_visible_from_any_view': len(haz) - len(P6),
                           'share_not_visible_from_any_view': rate(len(haz) - len(P6), len(haz)),
                           'pooled': _miss(P6),
                           'by_class': {c: _miss({k: v for k, v in P6.items() if v['cls'] == c}) for c in HAZARD_CLASSES},
                           'not_visible_allowed': {a: rate(sum(v[a] for k, v in haz.items() if not v['perceivable_any']), len(haz) - len(P6))
                                                   for a in ('front_allow', 'la_allow')}}
    hard = lambda S: {k: v for k, v in S.items() if v['cls'] == 'tongues_small'}
    out['oracle_steering'] = {'pooled': summarise_oracle_steering(P, P6), 'hard_class_tongues_small': summarise_oracle_steering(hard(P), hard(P6))}
    out['xd1_k_eps'] = {'k': 4, 'point': round(4 * la['rate'], 4) if la['n'] else None,
                        'upper95': round(min(1.0, 4 * la['ci95'][1]), 4) if la['n'] else None}
    out['not_perceivable_allowed'] = {a: rate(sum(v[a] for k, v in haz.items() if not v['perceivable']), out['n_not_perceivable'])
                                      for a in ('front_allow', 'la_allow')}
    out['caught_by_extra_views'] = {'paired_la_vs_adaptive': _paired_la_ad(P)}
    # XD-3: fire-free worlds with the requested supply (ok + twins), wrong-supply worlds
    ok = {k: v for k, v in W.items() if v['kind'] in ('ok', 'twin')}
    out['xd3_correct_approvals'] = {'pooled': {'front_only': rate(sum(v['front_allow'] for v in ok.values()), len(ok)),
                                               'look_around': rate(sum(v['la_allow'] for v in ok.values()), len(ok))}}
    for kind in ('ok', 'twin'):
        S = {k: v for k, v in ok.items() if v['kind'] == kind}
        out['xd3_correct_approvals'][kind] = {'front_only': rate(sum(v['front_allow'] for v in S.values()), len(S)),
                                              'look_around': rate(sum(v['la_allow'] for v in S.values()), len(S)),
                                              'extra_false_stop_from_side_views': rate(sum(v['front_allow'] and not v['la_allow']
                                                                                           for v in S.values()), len(S))}
    out['xd3_by_lookalike_ok_worlds'] = {str(kd): {'front_only': rate(sum(v['front_allow'] for v in ok.values() if v['kind'] == 'ok' and v['distractor_kind'] == kd),
                                                    sum(1 for v in ok.values() if v['kind'] == 'ok' and v['distractor_kind'] == kd)),
                                                   'look_around': rate(sum(v['la_allow'] for v in ok.values() if v['kind'] == 'ok' and v['distractor_kind'] == kd),
                                                                       sum(1 for v in ok.values() if v['kind'] == 'ok' and v['distractor_kind'] == kd))}
                                         for kd in sorted({v['distractor_kind'] for v in ok.values() if v['kind'] == 'ok'}, key=str)}
    tw = {k: v for k, v in ok.items() if v['kind'] == 'twin' and v['has_extra']}
    out['xd3_extra_view_trigger_rate_on_twins'] = rate(sum(bool(v['triggered']) for v in tw.values()), len(tw))
    out['xd3_adaptive_correct_approvals_twins'] = rate(sum(bool(v['ad_allow']) for v in tw.values()), len(tw))
    out['xd3_look_around_correct_approvals_same_twins'] = rate(sum(bool(v['la_allow']) for v in tw.values()), len(tw))
    wrong = {k: v for k, v in W.items() if v['kind'] == 'wrong'}
    out['xd3_wrong_supply_false_approvals'] = {
        'pooled': {'front_only': rate(sum(v['front_allow'] for v in wrong.values()), len(wrong)),
                   'look_around': rate(sum(v['la_allow'] for v in wrong.values()), len(wrong))},
        **{c: {'front_only': rate(sum(v['front_allow'] for v in wrong.values() if v['cls'] == c),
                                  sum(v['cls'] == c for v in wrong.values()))}
           for c in ('wrong_swapped', 'wrong_empty')}}
    out['missed_worlds_look_around'] = sorted(k for k, v in P.items() if v['la_allow'])
    # tau_h sensitivity (descriptive; no tau is chosen here)
    sens = {}
    for th in (0.02, 0.05, 0.10, 0.20):
        w2 = world_outcomes(main, tau_s, th)['worlds']
        p2 = [v for v in w2.values() if v['kind'] == 'hazard' and v['perceivable']]
        c2 = [v for v in w2.values() if v['kind'] in ('ok', 'twin')]
        sens[str(th)] = {'miss_look_around': rate(sum(v['la_allow'] for v in p2), len(p2)),
                         'correct_approval_look_around': rate(sum(v['la_allow'] for v in c2), len(c2))}
    out['tau_h_sensitivity'] = sens
    out['criteria'] = criteria(out, P, W)
    out['i20_revert_verdict'] = i20_revert_verdict(out)
    out['arena_reference'] = compare_to_arena(out, ref if ref is not None else arena_reference())
    return out


def i20_revert_verdict(out: dict) -> dict:
    """The I-20 revert rule, fixed on 2026-10-18 before XD was rendered or scored (IMPROVEMENT_LOG I-20): the v3.7 default
    (suspicion-triggered extra views) is withdrawn if ANY of (a) the extra views fire on more than 15% of the fire-free twins,
    (b) correct approvals on the twins fall by 5 points or more compared with look-around, (c) no look-around miss is removed
    on the perceivable XD worlds.  Reported either way; needs the adaptive pass to have run (otherwise 'not_evaluable')."""
    tr = out.get('xd3_extra_view_trigger_rate_on_twins') or {}
    ca_ad, ca_la = out.get('xd3_adaptive_correct_approvals_twins') or {}, out.get('xd3_look_around_correct_approvals_same_twins') or {}
    pr = (out.get('caught_by_extra_views') or {}).get('paired_la_vs_adaptive') or {}
    if not tr.get('n') or not pr.get('n'):
        return {'status': 'not_evaluable'}
    fired = {'a_trigger_rate_over_15pct': bool(tr['rate'] > TRIGGER_MAX),
             'b_correct_approvals_down_5pts_or_more': bool(ca_la.get('n') and (ca_la['rate'] - ca_ad['rate']) >= 0.05 - 1e-12),
             'c_removes_no_look_around_miss': bool(pr['first_only'] == 0)}
    return {'status': 'withdrawn' if any(fired.values()) else 'kept', 'fired': fired,
            'trigger_rate': tr['rate'], 'twin_correct_approvals_adaptive': ca_ad.get('rate'),
            'twin_correct_approvals_look_around': ca_la.get('rate'),
            'misses_removed_by_adaptive': pr['first_only'], 'misses_added_by_adaptive': pr['second_only']}


def _paired_la_ad(P: dict) -> dict:
    ids = [i for i in sorted(P) if P[i]['ad_allow'] is not None]
    return paired([P[i]['la_allow'] for i in ids], [P[i]['ad_allow'] for i in ids]) | {'n': len(ids)}


def criteria(out: dict, P: dict, W: dict) -> dict:
    """The registered transfer claims (O1-O4), the cost claim (C1) and the directional predictions (P1-P3)."""
    fr, la = out['xd1_pooled']['front_only'], out['xd1_pooled']['look_around']
    ids = sorted(P)
    mc = paired([P[i]['front_allow'] for i in ids], [P[i]['la_allow'] for i in ids])
    big = out['xd1_by_class']['tongues_big']['front_only']
    small = out['xd1_by_class']['tongues_small']['front_only']
    # R6: O1 as registered first ("look-around has fewer misses", a sign test on a subset relation) holds by construction and is
    # descriptive.  The claim that can fail is an effect size: look-around removes at least half of the front-only misses.
    c = {'descriptive_look_around_fewer_misses_mcnemar_p': mc['mcnemar_p'],
         'O1_look_around_removes_at_least_half_of_front_misses': bool(fr['n'] and fr['k'] > 0 and la['k'] <= O1_MIN_REMOVED * fr['k']),
         'O1_front_misses_removed_share': (round(1 - la['k'] / fr['k'], 4) if fr['k'] else None)}
    # XD-eps (R6): registered on the hard class (small partly hidden flames, tongues_small), pooled reported next to it
    hc = out['xd1_by_class']['tongues_small']['look_around']
    c['XDe_hard_class_upper_bound_below_0.15'] = bool(hc['n'] and hc['ci95'][1] is not None and hc['ci95'][1] <= EPS_UPPER_MAX)
    c['XDe_pooled_upper_bound_below_0.15'] = bool(la['n'] and la['ci95'][1] is not None and la['ci95'][1] <= EPS_UPPER_MAX)
    c['claim_eps_tight_hard_class'] = c['XDe_hard_class_upper_bound_below_0.15']
    p_size = fisher(small['k'], small['n'] - small['k'], big['k'], big['n'] - big['k']) if small['n'] and big['n'] else None
    c['O2_small_hidden_harder_than_big_visible'] = bool(p_size is not None and small['rate'] > big['rate'] and p_size < 0.05)
    c['O2_fisher_p_one_sided'] = p_size
    ad, tr = out['xd1_pooled']['adaptive'], out['xd3_extra_view_trigger_rate_on_twins']
    # R6: "adaptive misses <= look-around misses" is true by construction (descriptive count); the claim is the trigger rate
    c['descriptive_adaptive_misses_vs_look_around'] = {'adaptive': ad['k'], 'look_around': la['k'], 'n': ad['n']}
    c['O3_adaptive_no_worse_and_trigger_rate_at_most_0.15'] = bool(
        ad['n'] and ad['k'] <= la['k'] and tr['n'] and tr['rate'] <= TRIGGER_MAX)
    wf = out['xd3_wrong_supply_false_approvals']['pooled']
    c['O4_no_wrong_supply_false_approval'] = bool(wf['front_only']['n'] and wf['front_only']['k'] == 0 and wf['look_around']['k'] == 0)
    ca = out['xd3_correct_approvals']['pooled']['look_around']
    ca_front = out['xd3_correct_approvals']['pooled']['front_only']
    c['C1_correct_approvals_at_least_0.80'] = bool(ca_front['n'] and ca_front['rate'] >= CA_MIN)
    c['claim_relative_ordering_transfers'] = all(c[k] for k in ('O1_look_around_removes_at_least_half_of_front_misses', 'O2_small_hidden_harder_than_big_visible',
                                                                'O3_adaptive_no_worse_and_trigger_rate_at_most_0.15',
                                                                'O4_no_wrong_supply_false_approval'))
    # predictions (reported either way)
    rates = {k: out['xd1_by_class'][k]['look_around'] for k in HAZARD_CLASSES}
    tong = [P[i] for i in ids if P[i]['cls'] in ('tongues_big', 'tongues_small')]
    smoke = [P[i] for i in ids if P[i]['cls'] == 'smoke_only']
    if tong and smoke:
        a, b = sum(v['la_allow'] for v in smoke), sum(v['la_allow'] for v in tong)
        c['P1_smoke_only_miss_rate_at_least_tongues'] = a / len(smoke) >= b / len(tong)
        c['P1_fisher_p_one_sided'] = fisher(a, len(smoke) - a, b, len(tong) - b)
    c['P2_class_order_by_look_around_miss_rate'] = sorted(HAZARD_CLASSES, key=lambda k: -(rates[k]['rate'] or 0.0))
    c['P3_depot_eps_look_around_upper_bound'] = la['ci95'][1] if la['n'] else None
    return c


def compare_to_arena(out: dict, ref: dict) -> dict:
    """Absolute numbers are NOT claimed to transfer: this only re-estimates them next to the arena's (Fisher, two-sided)."""
    res = {'note': 'absolute eps / correct-approval rates are re-estimated, not transferred'}
    la = out['xd1_pooled']['look_around']
    if 'w_a' in ref and la['n']:
        a = ref['w_a']['miss_look_around']
        res['eps_look_around_depot_vs_arena_W'] = {'depot': la, 'arena': a,
                                                   'fisher_two_sided_p': fisher(la['k'], la['n'] - la['k'], a['k'], a['n'] - a['k'], 'two-sided'),
                                                   'arena_point_inside_depot_ci': bool(la['ci95'][0] <= a['rate'] <= la['ci95'][1])}
    if 't2' in ref:
        t = ref['t2']
        ca = out['xd3_correct_approvals']['pooled']['front_only']
        wf = out['xd3_wrong_supply_false_approvals']['pooled']['front_only']
        if ca['n']:
            res['correct_approval_depot_vs_arena_T2'] = {'depot': ca, 'arena': rate(t['correct_approvals'], t['n_allow']),
                                                         'fisher_two_sided_p': fisher(ca['k'], ca['n'] - ca['k'], t['correct_approvals'],
                                                                                      t['n_allow'] - t['correct_approvals'], 'two-sided')}
        if wf['n']:
            res['false_approval_depot_vs_arena_T2'] = {'depot': wf, 'arena': rate(t['false_approvals'], t['n_deny'])}
    if not res.keys() - {'note'}:
        res['available'] = False
    return res


# ------------------------------------------------------------------------------------------------ XD-4 recalibration
def view_flag_scores(records: list, split: str):
    """(positive scores, negative scores): visible-hazard views of hazard worlds vs views of fire-free worlds, standard views only."""
    pos, neg = [], []
    for r in records:
        if r.get('variant') or r['split'] != split or r['view'] not in VIEWS:
            continue
        s = hazard_score(r)
        if r['world_kind'] == 'hazard':
            if r['hazard_visibility'] == 'visible':
                pos.append(s)
        else:
            neg.append(s)
    return pos, neg


def choose_tau(pos: list, neg: list, grid=GRID, recall_min: float = CAL_RECALL_MIN):
    """The largest tau in the grid whose recall on the positives is >= recall_min (the safety constraint first), else None."""
    best = None
    for t in grid:
        if pos and sum(s >= t for s in pos) / len(pos) >= recall_min:
            best = t
    return best


def endpoint(pos: list, neg: list, tau: float) -> dict:
    return {'tau': tau, 'recall': rate(sum(s >= tau for s in pos), len(pos)), 'false_alarm': rate(sum(s >= tau for s in neg), len(neg))}


def recalibrate(records: list, tau_s: float = TAU_S) -> dict:
    cp, cn = view_flag_scores(records, 'cal')
    tp, tn = view_flag_scores(records, 'test')
    tau = choose_tau(cp, cn)
    out = {'frozen_tau': TAU_H, 'calibration': {'n_pos': len(cp), 'n_neg': len(cn), 'tau_star': tau,
                                                'at_tau_star': endpoint(cp, cn, tau) if tau is not None else None,
                                                'at_frozen': endpoint(cp, cn, TAU_H)},
           'test_image_level': {'at_frozen': endpoint(tp, tn, TAU_H), 'at_tau_star': endpoint(tp, tn, tau) if tau is not None else None}}
    test_recs = [r for r in records if not r.get('variant') and r['split'] == 'test']
    world = {}
    for name, th in (('at_frozen', TAU_H), ('at_tau_star', tau)):
        if th is None:
            continue
        W = world_outcomes(test_recs, tau_s, th)['worlds']
        P = [v for v in W.values() if v['kind'] == 'hazard' and v['perceivable']]
        C = [v for v in W.values() if v['kind'] in ('ok', 'twin')]
        Wr = [v for v in W.values() if v['kind'] == 'wrong']
        world[name] = {'tau': th, 'miss_look_around': rate(sum(v['la_allow'] for v in P), len(P)),
                       'miss_front_only': rate(sum(v['front_allow'] for v in P), len(P)),
                       'correct_approval_look_around': rate(sum(v['la_allow'] for v in C), len(C)),
                       'wrong_supply_false_approval_look_around': rate(sum(v['la_allow'] for v in Wr), len(Wr))}
    out['test_world_level'] = world
    cfg = out['test_image_level']['at_tau_star']
    out['moved'] = tau is not None and tau != TAU_H
    out['claim_calibration_usable'] = bool(cfg and cfg['recall']['n'] and cfg['recall']['rate'] >= TEST_RECALL_MIN
                                           and cfg['false_alarm']['n'] and cfg['false_alarm']['rate'] <= TEST_FA_MAX)
    out['claim_frozen_tau_usable'] = bool(out['test_image_level']['at_frozen']['recall']['n'] and
                                          out['test_image_level']['at_frozen']['recall']['rate'] >= TEST_RECALL_MIN and
                                          out['test_image_level']['at_frozen']['false_alarm']['rate'] <= TEST_FA_MAX)
    return out


# ------------------------------------------------------------------------------------------------ XD-5 ablation
def ablation(records: list, tau_s: float = TAU_S, tau_h: float = TAU_H) -> dict:
    """Each ablation world against its base world (same poses): miss of a hazard world perceivable in BOTH renders, false stop
    of a fire-free twin.  Paired exact McNemar per variant, Holm over the variants (separately for the two endpoints)."""
    W = world_outcomes(records, tau_s, tau_h)['worlds']
    base = {k: v for k, v in W.items() if not v['variant']}
    out, p_miss, p_stop = {}, {}, {}
    for var in ABLATION_VARIANTS:
        vs = {k: v for k, v in W.items() if v['variant'] == var and v['ablation_base'] in base}
        pairs_h = [(base[v['ablation_base']], v) for v in vs.values() if v['kind'] == 'hazard' and v['perceivable']
                   and base[v['ablation_base']]['perceivable']]
        pairs_t = [(base[v['ablation_base']], v) for v in vs.values() if v['kind'] == 'twin']
        mb, mv = [b['la_allow'] for b, _ in pairs_h], [v['la_allow'] for _, v in pairs_h]
        sb, sv = [not b['la_allow'] for b, _ in pairs_t], [not v['la_allow'] for _, v in pairs_t]
        pm, ps = paired(mb, mv), paired(sb, sv)
        out[var] = {'n_hazard_pairs': len(pairs_h), 'miss_base': rate(sum(mb), len(mb)), 'miss_variant': rate(sum(mv), len(mv)),
                    'miss_paired': pm, 'n_twin_pairs': len(pairs_t), 'false_stop_base': rate(sum(sb), len(sb)),
                    'false_stop_variant': rate(sum(sv), len(sv)), 'false_stop_paired': ps,
                    'n_not_perceivable_in_variant': sum(1 for v in vs.values() if v['kind'] == 'hazard' and not v['perceivable'])}
        if pairs_h:
            p_miss[var] = pm['mcnemar_p']
        if pairs_t:
            p_stop[var] = ps['mcnemar_p']
    for var, p in holm(p_miss).items():
        out[var]['miss_holm_p'] = p
    for var, p in holm(p_stop).items():
        out[var]['false_stop_holm_p'] = p
    out['features_that_move_eps'] = sorted(v for v in ABLATION_VARIANTS if v in out and out[v].get('miss_holm_p', 1) < 0.05)
    out['features_that_move_false_stops'] = sorted(v for v in ABLATION_VARIANTS if v in out and out[v].get('false_stop_holm_p', 1) < 0.05)
    return out


# ------------------------------------------------------------------------------------------------ driver
def analyse(records: list, ref: dict | None = None) -> dict:
    return {'registered': 'experiments/PREREGISTRATION_XD.md (DRAFT)', 'tau_s': TAU_S, 'tau_h': TAU_H,
            'XD_main': summarise_main(records, ref=ref), 'XD_recalibration': recalibrate(records), 'XD_ablation': ablation(records)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--tag', default='xd_h36_tiles')
    a = ap.parse_args(argv)
    records = json.loads((RES / f'devset_{a.tag}.json').read_text())['records']
    out = analyse(records)
    (RES / 'xd_summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    m, r = out['XD_main'], out['XD_recalibration']
    f, l = m['xd1_pooled']['front_only'], m['xd1_pooled']['look_around']
    print(f"XD-1 perceivable hazard worlds {m['n_perceivable']}/{m['n_hazard']}: miss front-only {f['k']}/{f['n']} {f['ci95']}  "
          f"look-around {l['k']}/{l['n']} {l['ci95']}  k*eps(4) {m['xd1_k_eps']}")
    for c, v in m['xd1_by_class'].items():
        print(f"     {c:14s} front {v['front_only']['k']}/{v['front_only']['n']}  look-around {v['look_around']['k']}/{v['look_around']['n']}")
    print('     criteria', {k: v for k, v in m['criteria'].items() if k[0] in 'OCP' or k.startswith('claim')})
    print(f"XD-4 tau* = {r['calibration']['tau_star']} (frozen {TAU_H}); usable at tau*: {r['claim_calibration_usable']}, "
          f"frozen usable: {r['claim_frozen_tau_usable']}")
    print('XD-5 features that move eps:', out['XD_ablation']['features_that_move_eps'])


if __name__ == '__main__':
    main()
