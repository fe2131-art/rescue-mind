#!/usr/bin/env python3
"""Study W analysis exactly as pre-registered (experiments/PREREGISTRATION_W.md).

  python3 scripts/w_analysis.py [--part a|b|all]     # -> experiments/results/w_summary.json

W-a (image level): per-world miss rate of v3.6 on perceivable small fires, front check only vs front + look-around (approve
only if the front check approves and neither side view shows a hazard), Wilson CIs, exact McNemar over worlds; false stops on the
fire-free twins.  Inputs: experiments/results/devset_w_h36_tiles.json (scripts/vlm_devset_eval.py on experiments/vlm_testset_w).
W-b (prior-art baselines on existing T1/T2 images): VAP-TAMP-style paraphrase vote and KnowNo-style conformal prediction set
vs the frozen v3.6 hazard check.  PRIMARY comparison: Ours-full (h36 wording, full image only: the baselines' input);
secondary: the deployed system (h36 + tiles).  Inputs: devset_t{1,2}_i11_h36_{tiles,full}.json (ours deployed / ours-full), devset_w_para_{dh,dh2,t1,t2}.json (baselines).
Ground truth is used only here.  Helpers are the ones of the earlier analyses (t1_analysis, h_analysis).
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
from scripts.t1_analysis import cluster_bootstrap, decide, mcnemar_exact, metrics, wilson  # noqa: E402

RES = ROOT / 'experiments/results'
TAU_S = 0.50
TAU_H = 0.05
TAU_GRID = (0.02, 0.05, 0.10, 0.20)      # descriptive sensitivity only
A2_UPPER_BOUND = 0.15                    # W-a P2: Wilson upper bound of the look-around miss rate
A3_MAX_EXTRA_STOP = 0.10                 # W-a P3: extra false stops caused by the side views, point estimate
VOTE_K = 5
SMALL_FIRE_PX = 10000                    # T2 analysis split


# ------------------------------------------------------------------------------------------------ W-a
def peek_hazard(rec: dict, tau_h: float = TAU_H) -> bool:
    """The robot's rule for a side view (rescuemind.mission_memory.peek_hazard without memory caution): hazard if either
    pass puts p(hazard) >= tau_h.  A failed inference, a missing score or a rejected frame counts as hazard (fail-closed)."""
    if not (rec.get('quality') or {}).get('quality_ok', True):
        return True
    probs = []
    for k in '12':
        p = rec['passes'].get(k) or {}
        sc = p.get('scores')
        if 'error' in p or not sc or 'hazard_prob' not in sc:
            return True
        probs.append(sc['hazard_prob'])
    return max(probs) >= tau_h


def front_allows(rec: dict, tau_s: float = TAU_S, tau_h: float = TAU_H) -> bool:
    if not (rec.get('quality') or {}).get('quality_ok', True):
        return False
    return decide(rec, passes='12', tau_s=tau_s, tau_h=tau_h)


def world_outcomes(records: list, tau_s: float = TAU_S, tau_h: float = TAU_H) -> dict:
    """world_id -> per-world decisions.  Worlds that lack one of the three views are returned under 'incomplete'."""
    by: dict = {}
    for r in records:
        by.setdefault(r['world_id'], {})[r['view']] = r
    out, incomplete = {}, []
    for wid, v in by.items():
        if set(v) != {'F', 'L', 'R'}:
            incomplete.append(wid); continue
        f = v['F']
        fa = front_allows(f, tau_s, tau_h)
        lh, rh = peek_hazard(v['L'], tau_h), peek_hazard(v['R'], tau_h)
        out[wid] = {'kind': f['world_kind'], 'perceivable': f['world_perceivable'], 'front_perceivable': f['world_front_perceivable'],
                    'side_only': f['world_side_only'], 'front_allow': fa, 'left_hazard': lh, 'right_hazard': rh,
                    'la_allow': fa and not lh and not rh,
                    'front_hazard_pass': hazard_test_passes(f, tau_h), 'fire_pixels': {k: v[k]['fire_pixels'] for k in 'FLR'}}
    return {'worlds': out, 'incomplete': sorted(incomplete)}


def hazard_test_passes(rec: dict, tau_h: float) -> bool:
    """True if the front view passes the hazard test (p(hazard) < tau_h in both passes), whatever the supply answer."""
    for k in '12':
        p = rec['passes'].get(k) or {}
        sc = p.get('scores')
        if 'error' in p or not sc or sc.get('hazard_prob', 1.0) >= tau_h:
            return False
    return (rec.get('quality') or {}).get('quality_ok', True)


def rate(k: int, n: int) -> dict:
    return {'k': k, 'n': n, 'rate': round(k / n, 4) if n else None, 'ci95': wilson(k, n)}


def paired_counts(a: list, b: list) -> dict:
    """a, b: parallel booleans (event happened).  b_only / c_only discordant pairs and the exact McNemar p."""
    n10 = sum(x and not y for x, y in zip(a, b))
    n01 = sum(y and not x for x, y in zip(a, b))
    return {'first_only': n10, 'second_only': n01, 'mcnemar_p': float(f'{mcnemar_exact(n10, n01):.3g}')}


def summarise_a(records: list, tau_s: float = TAU_S, tau_h: float = TAU_H) -> dict:
    wo = world_outcomes(records, tau_s, tau_h)
    W = wo['worlds']
    fire = {k: v for k, v in W.items() if v['kind'] == 'fire'}
    twin = {k: v for k, v in W.items() if v['kind'] == 'twin'}
    P = {k: v for k, v in fire.items() if v['perceivable']}
    FP = {k: v for k, v in fire.items() if v['front_perceivable']}
    SO = {k: v for k, v in fire.items() if v['side_only']}
    NP = {k: v for k, v in fire.items() if not v['perceivable']}
    ids = sorted(P)
    mf = [P[i]['front_allow'] for i in ids]
    ml = [P[i]['la_allow'] for i in ids]
    out = {'n_fire_worlds': len(fire), 'n_perceivable': len(P), 'n_front_perceivable': len(FP), 'n_side_only': len(SO),
           'n_not_perceivable': len(NP), 'n_twins': len(twin), 'incomplete_worlds': wo['incomplete'],
           'miss_front_only': rate(sum(mf), len(ids)), 'miss_look_around': rate(sum(ml), len(ids)),
           'front_vs_look_around': paired_counts(mf, ml)}
    out['front_vs_look_around']['first_only_means'] = 'front-only miss that look-around caught'
    # secondary subsets
    for name, S in (('front_perceivable', FP), ('side_only', SO)):
        s = sorted(S)
        out[f'miss_front_only_{name}'] = rate(sum(S[i]['front_allow'] for i in s), len(s))
        out[f'miss_look_around_{name}'] = rate(sum(S[i]['la_allow'] for i in s), len(s))
    out['front_hazard_test_miss'] = rate(sum(P[i]['front_hazard_pass'] for i in ids), len(ids))   # hazard test alone, any supply answer
    out['caught_by'] = {'left_only': sum(P[i]['front_allow'] and P[i]['left_hazard'] and not P[i]['right_hazard'] for i in ids),
                        'right_only': sum(P[i]['front_allow'] and P[i]['right_hazard'] and not P[i]['left_hazard'] for i in ids),
                        'both': sum(P[i]['front_allow'] and P[i]['left_hazard'] and P[i]['right_hazard'] for i in ids)}
    out['missed_worlds'] = [i for i in ids if P[i]['la_allow']]
    out['not_perceivable_allowed'] = {'front_only': rate(sum(NP[i]['front_allow'] for i in NP), len(NP)),
                                      'look_around': rate(sum(NP[i]['la_allow'] for i in NP), len(NP))}
    # fire-free twins: what looking around costs
    t = sorted(twin)
    tf, tl = [twin[i]['front_allow'] for i in t], [twin[i]['la_allow'] for i in t]
    extra = [twin[i]['front_allow'] and not twin[i]['la_allow'] for i in t]
    out['twins'] = {'correct_approval_front_only': rate(sum(tf), len(t)), 'correct_approval_look_around': rate(sum(tl), len(t)),
                    'extra_false_stop_from_side_views': rate(sum(extra), len(t)),
                    'front_vs_look_around': paired_counts(tf, tl),
                    'front_refusals': rate(sum(not x for x in tf), len(t))}
    out['look_around_false_stop_cost_per_approval'] = out['twins']['extra_false_stop_from_side_views']
    # sensitivity (descriptive): the same at other hazard thresholds
    if (tau_s, tau_h) == (TAU_S, TAU_H):
        sens = {}
        for th in TAU_GRID:
            w2 = world_outcomes(records, tau_s, th)['worlds']
            p2 = [v for v in w2.values() if v['kind'] == 'fire' and v['perceivable']]
            t2 = [v for v in w2.values() if v['kind'] == 'twin']
            sens[str(th)] = {'miss_front_only': rate(sum(v['front_allow'] for v in p2), len(p2)),
                             'miss_look_around': rate(sum(v['la_allow'] for v in p2), len(p2)),
                             'twin_correct_approval_look_around': rate(sum(v['la_allow'] for v in t2), len(t2))}
        out['tau_h_sensitivity'] = sens
    # registered criteria
    la, fr = out['miss_look_around'], out['miss_front_only']
    out['criteria'] = {
        'P1_look_around_fewer_misses': bool(fr['n'] and la['k'] < fr['k'] and out['front_vs_look_around']['mcnemar_p'] < 0.05),
        'P2_eps_upper_bound_below_0.15': bool(la['n'] and la['ci95'][1] is not None and la['ci95'][1] <= A2_UPPER_BOUND),
        'P3_extra_false_stops_at_most_0.10': bool(out['twins']['extra_false_stop_from_side_views']['n'] and
                                                  out['twins']['extra_false_stop_from_side_views']['rate'] <= A3_MAX_EXTRA_STOP)}
    out['criteria']['claim_eps_tight'] = out['criteria']['P1_look_around_fewer_misses'] and out['criteria']['P2_eps_upper_bound_below_0.15']
    out['criteria']['claim_cost_acceptable'] = out['criteria']['P3_extra_false_stops_at_most_0.10']
    return out


def summarise_degraded(conds: dict, clean_records: list) -> dict:
    """Secondary: look-around miss per degradation on the registered subset (clean scores of the same worlds for reference)."""
    sub_ids = {r['world_id'] for recs in conds.values() for r in recs}
    clean = world_outcomes([r for r in clean_records if r['world_id'] in sub_ids])['worlds']
    ref = [v for v in clean.values() if v['perceivable']]
    out = {'clean_reference': {'miss_front_only': rate(sum(v['front_allow'] for v in ref), len(ref)),
                               'miss_look_around': rate(sum(v['la_allow'] for v in ref), len(ref))}, 'conditions': {}}
    for c, recs in sorted(conds.items()):
        w = world_outcomes(recs)
        P = [v for v in w['worlds'].values() if v['perceivable']]
        out['conditions'][c] = {'n_incomplete': len(w['incomplete']), 'miss_front_only': rate(sum(v['front_allow'] for v in P), len(P)),
                                'miss_look_around': rate(sum(v['la_allow'] for v in P), len(P)),
                                'gate_rejected_images': sum(not (r.get('quality') or {}).get('quality_ok', True) for r in recs)}
    worst = max((v['miss_look_around']['k'] / max(v['miss_look_around']['n'], 1), c) for c, v in out['conditions'].items()) \
        if out['conditions'] else None
    out['worst_condition'] = worst
    return out


# ------------------------------------------------------------------------------------------------ W-b
def supply_ok(rec: dict, tau_s: float = TAU_S) -> bool:
    """Both passes error-free, the answer with the highest probability is the requested station's supply and its probability >= tau_s."""
    for k in '12':
        p = rec['passes'].get(k) or {}
        sc = p.get('scores')
        if 'error' in p or not sc:
            return False
        probs = sc['supply_probs']
        if max(probs, key=probs.get) != rec['station'] or probs[rec['station']] < tau_s:
            return False
    return True


def votes(para: dict, thr: float = 0.5) -> int:
    return sum(p >= thr for p in para['probs'])


def vap_refuses(para: dict, variant: str = 'majority@0.5') -> bool:
    """VAP-TAMP-style hazard decision from the five paraphrase scores.  A failed inference refuses (fail-closed)."""
    if 'error' in para:
        return True
    kind, thr = variant.split('@')
    thr = float(thr)
    if kind == 'majority':
        return votes(para, thr) > VOTE_K // 2
    if kind == 'any':
        return votes(para, thr) >= 1
    if kind == 'mean':
        return statistics.fmean(para['probs']) >= thr
    raise ValueError(variant)


VAP_VARIANTS = ('majority@0.5', 'majority@0.05', 'any@0.5', 'mean@0.05')


def conformal_quantile(scores: list, alpha: float) -> float:
    """Split-conformal quantile: the ceil((n+1)(1-alpha))-th smallest nonconformity score (inf if it does not exist)."""
    n = len(scores)
    k = math.ceil((n + 1) * (1 - alpha))
    return sorted(scores)[k - 1] if 1 <= k <= n else math.inf


def nonconformity(p_yes: float, label: str) -> float:
    return 1.0 - (p_yes if label == 'Yes' else 1.0 - p_yes)


def prediction_set(p_yes: float, qhat_yes: float, qhat_no: float | None = None) -> frozenset:
    """{y : 1 - p(y) <= qhat}.  One qhat (KnowNo, marginal) or one per class (Mondrian)."""
    qn = qhat_yes if qhat_no is None else qhat_no
    s = set()
    if nonconformity(p_yes, 'Yes') <= qhat_yes:
        s.add('Yes')
    if nonconformity(p_yes, 'No') <= qn:
        s.add('No')
    return frozenset(s)


def calibration_scores(dev_records: list, score) -> list:
    """(label, p_yes) of the development images with a definite fire label: visible -> Yes, hidden -> No; ambiguous and failed
    inferences are left out."""
    out = []
    for r in dev_records:
        para = r['para']
        if 'error' in para or r['hazard_visibility'] not in ('visible', 'hidden'):
            continue
        out.append(('Yes' if r['hazard_visibility'] == 'visible' else 'No', score(para)))
    return out


SCORES = {'q1_h35': lambda para: para['probs'][0], 'ref_h36': lambda para: para['ref_h36']}


def knowno_calibrate(cal: list, alpha: float, mondrian: bool = False) -> dict:
    if mondrian:
        return {'qhat_yes': conformal_quantile([nonconformity(p, y) for y, p in cal if y == 'Yes'], alpha),
                'qhat_no': conformal_quantile([nonconformity(p, y) for y, p in cal if y == 'No'], alpha)}
    q = conformal_quantile([nonconformity(p, y) for y, p in cal], alpha)
    return {'qhat_yes': q, 'qhat_no': q}


def knowno_refuses(para: dict, cal: dict, score) -> bool:
    """Refuse unless the prediction set is exactly {No}.  A failed inference refuses."""
    if 'error' in para:
        return True
    return prediction_set(score(para), cal['qhat_yes'], cal['qhat_no']) != frozenset({'No'})


def holm(ps: list) -> list:
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = run
    return adj


def compare_to_ours(rows: list, ours: list, other: list) -> dict:
    """rows: non-ambiguous images; ours / other: approve decisions.  Exact McNemar on the paired false approvals (must-refuse
    images) and on the paired correct approvals (must-approve images)."""
    deny = [i for i, r in enumerate(rows) if r['expected'] == 'deny']
    allow = [i for i, r in enumerate(rows) if r['expected'] == 'allow']
    fa = paired_counts([ours[i] for i in deny], [other[i] for i in deny])
    ca = paired_counts([ours[i] for i in allow], [other[i] for i in allow])
    return {'false_approval': {'ours_only': fa['first_only'], 'baseline_only': fa['second_only'], 'mcnemar_p': fa['mcnemar_p']},
            'correct_approval': {'ours_only': ca['first_only'], 'baseline_only': ca['second_only'], 'mcnemar_p': ca['mcnemar_p']}}


def small_fire_refusals(rows: list, allow: list) -> dict:
    sel = [a for r, a in zip(rows, allow) if r['hazard_visibility'] == 'visible' and r['fire_pixels'] < SMALL_FIRE_PX
           and r['truth_supply'] == r['station']]
    return {'small_fires_correct_supply': len(sel), 'approved': sum(sel)}


OURS = 'ours (h36+tiles, tau_h 0.05)'
OURS_FULL = 'ours-full (h36, full image, tau_h 0.05)'
PRIMARY_BASELINES = ('VAP vote majority@0.5', 'KnowNo q1_h35 alpha=0.05', 'KnowNo q1_h35 alpha=0.1')


def _verdict(ref_m: dict, base_m: dict, holm_p: float) -> bool:
    """Registered verdict: fewer false approvals, Holm-adjusted p < 0.05, correct approvals not lower by more than 5 points."""
    return bool(ref_m['false_approvals'] < base_m['false_approvals'] and holm_p < 0.05
                and ref_m['ca_rate'] - base_m['ca_rate'] >= -0.05)


def evaluate_baselines(ours_recs: dict, para_recs: dict, dev_para: list, full_recs: dict) -> dict:
    """ours_recs (deployed v3.6: h36 + tiles), full_recs (matched arm: h36, full image only) and para_recs: {(set, image): record}
    for T1 and T2; dev_para: development records with 'para'.  Every system keeps the supply check and swaps only the hazard rule.
    PRIMARY comparison: Ours-full vs each baseline (same input, the full image only).  SECONDARY: the deployed system vs the same
    baselines."""
    keys = sorted(k for k in ours_recs if k in para_recs and k in full_recs and ours_recs[k]['expected'] != 'ambiguous')
    rows = [dict(ours_recs[k], image=f'{k[0]}/{k[1]}') for k in keys]     # unique image key across the two test sets
    paras = [para_recs[k]['para'] for k in keys]
    decisions = {OURS: [decide(ours_recs[k], passes='12', tau_s=TAU_S, tau_h=TAU_H) for k in keys],
                 OURS_FULL: [decide(full_recs[k], passes='12', tau_s=TAU_S, tau_h=TAU_H) for k in keys]}
    sup = [supply_ok(ours_recs[k]) for k in keys]
    for v in VAP_VARIANTS:
        decisions[f'VAP vote {v}'] = [s and not vap_refuses(p, v) for s, p in zip(sup, paras)]
    calib = {}
    for sname, score in SCORES.items():
        cal = calibration_scores(dev_para, score)
        for alpha in (0.05, 0.10):
            for mond in (False, True):
                c = knowno_calibrate(cal, alpha, mond)
                name = f"KnowNo{'-Mondrian' if mond else ''} {sname} alpha={alpha}"
                decisions[name] = [s and not knowno_refuses(p, c, score) for s, p in zip(sup, paras)]
                calib[name] = {**{k: (None if math.isinf(v) else round(v, 4)) for k, v in c.items()}, 'n_cal': len(cal),
                               'n_cal_fire': sum(y == 'Yes' for y, _ in cal)}
    out = {'n_images': len(rows), 'n_deny': sum(r['expected'] == 'deny' for r in rows),
           'n_allow': sum(r['expected'] == 'allow' for r in rows), 'inference_errors_para': sum('error' in p for p in paras),
           'calibration': calib, 'systems': {}}
    for name, d in decisions.items():
        m = metrics(rows, d)
        m['cluster_bootstrap'] = cluster_bootstrap(rows, d)
        m['small_fires'] = small_fire_refusals(rows, d)
        if name not in (OURS, OURS_FULL):
            m['vs_ours_full'] = compare_to_ours(rows, decisions[OURS_FULL], d)
            m['vs_ours_deployed'] = compare_to_ours(rows, decisions[OURS], d)
        out['systems'][name] = m
    S = out['systems']
    for level, ref, key, verdict, notworse in (
            ('primary', OURS_FULL, 'vs_ours_full', 'mechanism_matters', 'baseline_not_worse_than_ours_full'),
            ('secondary', OURS, 'vs_ours_deployed', 'deployed_better', 'baseline_not_worse_than_deployed')):
        ps = [S[n][key]['false_approval']['mcnemar_p'] for n in PRIMARY_BASELINES]
        for n, adj in zip(PRIMARY_BASELINES, holm(ps)):
            S[n][f'{level}_holm_p_false_approval'] = round(adj, 5)
            S[n][verdict] = _verdict(S[ref], S[n], adj)
            S[n][notworse] = bool(S[n]['false_approvals'] <= S[ref]['false_approvals'])
    out['primary_baselines'] = list(PRIMARY_BASELINES)
    out['primary_reference'] = OURS_FULL
    out['secondary_reference'] = OURS
    return out


# ------------------------------------------------------------------------------------------------ I/O
def _load(tag: str):
    f = RES / f'devset_{tag}.json'
    return json.loads(f.read_text())['records'] if f.is_file() else None


def run_part_a(out: dict):
    recs = _load('w_h36_tiles')
    if recs is None:
        out['W-a'] = 'not run'; return
    out['W-a'] = summarise_a(recs)
    ref = _load('w_h35_full')
    if ref:
        out['W-a_v35_reference'] = summarise_a(ref)
    conds = {}
    from rescuemind.corruptions import CONDITIONS
    for c in CONDITIONS:
        r = _load(f'w_r_{c}')
        if r is not None:
            conds[c] = r
    if conds:
        out['W-a_degraded'] = summarise_degraded(conds, recs)


def run_part_b(out: dict):
    ours, para, dev, full = {}, {}, [], {}
    for s in ('t1', 't2'):
        o, p, f = _load(f'{s}_i11_h36_tiles'), _load(f'w_para_{s}'), _load(f'{s}_i11_h36_full')
        if o is None or p is None or f is None:
            out['W-b'] = f'not run (missing {s})'; return
        ours.update({(s, r['image']): r for r in o})
        full.update({(s, r['image']): r for r in f})
        para.update({(s, r['image']): r for r in p})
    for s in ('dh', 'dh2'):
        p = _load(f'w_para_{s}')
        if p is None:
            out['W-b'] = f'not run (missing {s})'; return
        dev += p
    out['W-b'] = evaluate_baselines(ours, para, dev, full)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--part', choices=['a', 'b', 'all'], default='all')
    a = ap.parse_args()
    out = {'registered': 'experiments/PREREGISTRATION_W.md', 'tau_s': TAU_S, 'tau_h': TAU_H}
    if a.part in ('a', 'all'):
        run_part_a(out)
    if a.part in ('b', 'all'):
        run_part_b(out)
    (RES / 'w_summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    A = out.get('W-a')
    if isinstance(A, dict):
        f, l = A['miss_front_only'], A['miss_look_around']
        print(f"W-a perceivable fire worlds {A['n_perceivable']}/{A['n_fire_worlds']}: miss front-only {f['k']}/{f['n']} {f['ci95']}  "
              f"look-around {l['k']}/{l['n']} {l['ci95']}  McNemar p={A['front_vs_look_around']['mcnemar_p']}")
        t = A['twins']
        print(f"     twins n={A['n_twins']}: correct approvals front {t['correct_approval_front_only']['k']} "
              f"look-around {t['correct_approval_look_around']['k']}  extra false stops {t['extra_false_stop_from_side_views']}")
        print('     criteria', A['criteria'])
    B = out.get('W-b')
    if isinstance(B, dict):
        for name, m in B['systems'].items():
            print(f"W-b {name:48s} FA {m['false_approvals']:3d}/{m['n_deny']} CA {m['correct_approvals']:3d}/{m['n_allow']} "
                  f"{'' if 'vs_ours_full' not in m else 'McNemar FA p vs ours-full=' + str(m['vs_ours_full']['false_approval']['mcnemar_p'])}")


if __name__ == '__main__':
    main()
