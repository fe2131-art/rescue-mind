#!/usr/bin/env python3
"""I-23: machine-checked "advice may only tighten" (Proposition 2) and the cost bound, with z3.

What this file contains
  1. MODELS (z3, no Python semantics hidden in them), each a line-by-line transcription of the code it names:
       plan_step      <- rescuemind/advice.py   plan() (mode 'monotone') + assert_monotone()
       station        <- rescuemind/{mission_memory,local_vision,adaptive_views}.py  the approval predicate A(o; tau, scrutiny)
                         = local_decision . apply_memory_caution . peek_hazard . combine_with_look_around . schedule_adaptive_views
       loop           <- ros/gazebo_waypoint_mission.py main loop (supply_station / peek / begin_search) and rescuemind/stations.py
  2. PROOFS: every property is "the negation is unsat" (z3 returns `unsat`); results and timings go to
     experiments/results/smt_advice_proof.json.
       P2a  approve_with_advice => approve_without_advice (absolute: vs the v3.6 rule; relative: vs the base/memory plan)
            for an advice list of ANY length (inductive invariant of the plan fold) and, in addition, unrolled end to end.
       P2b  every delivery is preceded by an approving check at that station; the candidate order stays a permutation of
            all k stations (no candidate dropped, none repeated); the visited stations are a prefix of the order.
       C    visits <= k; a reorder costs <= 1 extra visit when the outcomes are unchanged; <= 6 views per station and
            advice adds at most the 3 scrutiny views; an approval is lost to advice ONLY through the caution threshold
            (or the scrutiny extra views); advice that names no hazard station and no scrutiny changes no approval.
  3. LINK model <-> code: the differential harness (`real_*`, `model_*`, `run_differential`) evaluates the REAL Python
     functions and the z3 model on the same concrete inputs (hypothesis draws, boundary / NaN / inf values, adversarial
     advice) and asserts exact agreement; tests/test_i23_smt_refinement.py runs it.
  4. MUTANTS: representative bugs injected into private copies of the code (and as flags of the model).  The model
     mutant yields a concrete z3 counterexample; the same counterexample replayed on the mutated code shows the bug;
     the differential harness kills the mutated code.

Usage:  nice -n 19 python3 scripts/verify_advice_smt.py [--out experiments/results/smt_advice_proof.json] [--quick]
Trusted base of the result: z3, the CPython interpreter, and the TRANSCRIPTION (the model) -- see docs/paper/sec_formal.tex.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import itertools
import json
import math
import platform
import random
import sys
import time
import types
from fractions import Fraction
from pathlib import Path

import z3

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ----------------------------------------------------------------------------------------------------------------------
# constants copied from the code (and checked against it in the tests); the EXACT value of the IEEE double, since the code
# compares doubles (0.01 as a double is slightly above 1/100)
# ----------------------------------------------------------------------------------------------------------------------
TAU_STD = Fraction(0.05)           # advice.V36_TAU_H = 0.05: a caution threshold must lie in (0, 0.05)
TAU_CAUTION = Fraction(0.01)     # mission_memory.CAUTION_TAU_H = 0.01 (a scrutinised station must carry tau <= this)
TAU_SUS = Fraction(0.005)          # adaptive_views tau_sus = 0.005 (not needed by the proofs: the trigger is advice-free)
VIEWS = ('F', 'L', 'R', 'L2', 'R2', 'N')
STD_SIDE = ('L', 'R')
EXTRA = ('L2', 'R2', 'N')
MAX_VIEWS = 6                      # front + L + R + L2 + R2 + N  (PROOF_REVIEW 4.)
APPROVE, CONT, STOP = 0, 1, 2      # outcome classes of one station check in the mission loop
HAZ = 3                            # I-42: a REAL hazard refusal; STOP in v3.6, CONT under --hazard-continue (loop_run_hc)


def rv(x) -> z3.ArithRef:
    f = Fraction(x)
    return z3.RealVal(f"{f.numerator}/{f.denominator}")


def zmin(a, b):
    """Python's min(a, b) for non-NaN reals: a unless b < a."""
    return z3.If(b < a, b, a)


def timed(fn):
    t0 = time.perf_counter()
    r = fn()
    return r, time.perf_counter() - t0


def prove(name: str, claim, assumptions=(), timeout_ms: int = 120_000, record: list | None = None, meta=None) -> dict:
    """Check that `assumptions /\\ not claim` is unsat.  `claim` is a z3 Bool expression."""
    s = z3.Solver()
    s.set('timeout', timeout_ms)
    s.add(*assumptions)
    s.add(z3.Not(claim))
    t0 = time.perf_counter()
    res = s.check()
    dt = time.perf_counter() - t0
    out = {'name': name, 'result': str(res), 'proved': res == z3.unsat, 'seconds': round(dt, 4), **(meta or {})}
    if res == z3.sat:
        out['model'] = s.model()
    if record is not None:
        record.append({k: v for k, v in out.items() if k != 'model'})
    return out


def mval(m, e):
    """Python value of a z3 expression under model m."""
    v = m.eval(e, model_completion=True)
    if z3.is_true(v):
        return True
    if z3.is_false(v):
        return False
    if z3.is_int_value(v):
        return v.as_long()
    if z3.is_rational_value(v):
        f = v.as_fraction()
        return {'exact': str(f), 'float': float(f)}
    return str(v)


# ======================================================================================================================
# 1. THE PLAN MODEL  (rescuemind/advice.py, mode 'monotone').  Stations are 0..k-1; station 0 is the catalog station
#    (ss.default_order(item)[0]), so the default candidate order is [0, 1, ..., k-1].
# ======================================================================================================================
class PlanState:
    """A (symbolic or concrete) plan: first_station, candidate order, caution {t: tau}, scrutiny set, skip, deny.
    nan[t]: the caution threshold written at t is NaN (caution_tau_h = NaN); the strict range check then fails."""

    def __init__(self, first, order, cau, tau, nan, scr, skip, deny):
        self.first, self.order, self.cau, self.tau, self.nan, self.scr, self.skip, self.deny = (
            first, order, cau, tau, nan, scr, skip, deny)

    @staticmethod
    def fresh(prefix: str, k: int) -> 'PlanState':
        return PlanState(z3.Int(prefix + '_first'), [z3.Int(f'{prefix}_ord{i}') for i in range(k)],
                         [z3.Bool(f'{prefix}_cau{t}') for t in range(k)], [z3.Real(f'{prefix}_tau{t}') for t in range(k)],
                         [z3.Bool(f'{prefix}_nan{t}') for t in range(k)], [z3.Bool(f'{prefix}_scr{t}') for t in range(k)],
                         z3.Bool(prefix + '_skip'), z3.Bool(prefix + '_deny'))

    def leaves(self):
        return [self.first, *self.order, *self.cau, *self.tau, *self.nan, *self.scr, self.skip, self.deny]


def moved(st, k):
    """StationSet.order(item, st): st first, the others in default order."""
    return [st] + [z3.If(st >= i, z3.IntVal(i - 1), z3.IntVal(i)) for i in range(1, k)]


def is_perm(order, k):
    return z3.And(*[z3.And(o >= 0, o < k) for o in order], z3.Distinct(*order)) if k > 1 else z3.And(order[0] == 0)


def item_valid(kind, st, k):
    """advice.validate: kind in KINDS, station None or in ids, location/hazard need a station.  kind 0..3 =
    location, hazard, safe, skip; st -1 = None."""
    return z3.And(kind >= 0, kind <= 3, st >= -1, st < k, z3.Or(kind >= 2, st >= 0))


PLAN_MUTANTS = {
    # name -> (description, the model flag)
    'advice_loosens_tau_h': 'hazard/scrutiny advice overwrites an existing caution threshold with caution_tau_h (can loosen)',
    'caution_max_not_min': 'min(caution_tau_h, prev) replaced by max',
    'advice_skips_check': "'safe' / 'skip' advice honoured in monotone mode (skip_check = True)",
    'advice_marks_verified': 'location advice marks the advised station verified (skip_check = True)',
    'advice_refuses_unseen': "hazard advice at the first station sets deny_without_visit (refusal without looking)",
    'advice_drops_candidate': 'location advice leaves the last candidate out of the order',
}


def plan_step(s: PlanState, kind, st, tc, tcnan, S, k, mut=frozenset()) -> PlanState:
    """One item of advice.plan() in mode 'monotone' (scrutiny flag S)."""
    mv = moved(st, k)
    cond_loc = z3.And(kind == 0, s.first == 0, st != 0, z3.Not(s.skip))           # advice.py: location branch condition
    first = z3.If(cond_loc, st, s.first)
    order = [z3.If(cond_loc, mv[i], s.order[i]) for i in range(k)]
    if 'advice_drops_candidate' in mut:
        order[k - 1] = z3.If(cond_loc, z3.IntVal(-1), order[k - 1])
    scr_on = z3.And(cond_loc, S)                                                    # scrutiny: only on a reorder
    cau, tau, nan, scr = [], [], [], []
    for t in range(k):
        hit = z3.And(st == t, z3.Or(kind == 1, scr_on))                             # caution written at station t
        prev = s.tau[t]
        if 'advice_loosens_tau_h' in mut:
            new = tc
        elif 'caution_max_not_min' in mut:
            new = z3.If(s.cau[t], z3.If(prev > tc, prev, tc), tc)
        else:
            new = z3.If(s.cau[t], zmin(tc, prev), tc)                                # min(caution_tau_h, prev) / caution_tau_h
        cau.append(z3.Or(s.cau[t], hit))
        tau.append(z3.If(hit, new, prev))
        nan.append(z3.If(hit, tcnan, s.nan[t]))
        scr.append(z3.Or(s.scr[t], z3.And(scr_on, st == t)))
    skip = s.skip
    if 'advice_skips_check' in mut:
        skip = z3.Or(skip, kind >= 2)
    if 'advice_marks_verified' in mut:
        skip = z3.Or(skip, cond_loc)
    deny = s.deny
    if 'advice_refuses_unseen' in mut:
        deny = z3.Or(deny, z3.And(kind == 1, st == s.first))
    return PlanState(first, order, cau, tau, nan, scr, skip, deny)


def assert_ok(b: PlanState, a: PlanState, k: int):
    """advice.assert_monotone(before=b, after=a) does NOT raise (k > 2 stations, so 'order' exists)."""
    c = [z3.Implies(a.skip, b.skip), z3.Implies(a.deny, b.deny)]
    for t in range(k):
        c.append(z3.Implies(b.cau[t], a.cau[t]))                                     # no caution removed
        c.append(z3.Implies(a.cau[t], z3.And(z3.Not(a.nan[t]), a.tau[t] > 0, a.tau[t] < rv(TAU_STD))))   # _tau strict
        c.append(z3.Implies(z3.And(a.cau[t], b.cau[t]), a.tau[t] <= b.tau[t]))       # not loosened (NaN already excluded)
        c.append(z3.Implies(b.scr[t], a.scr[t]))                                     # scrutiny never dropped
        c.append(z3.Implies(a.scr[t], z3.And(a.cau[t], a.tau[t] <= rv(TAU_CAUTION))))
    c.append(is_perm(a.order, k))                                                    # sorted(before.order) == sorted(after.order)
    c.append(a.order[0] == a.first)
    return z3.And(*c)


def wf_base(b: PlanState, k: int):
    """What MissionMemory.plan / base_plan produce (the base plan is the baseline or verified memory)."""
    c = [is_perm(b.order, k), b.order[0] == b.first, z3.Implies(b.first == 0, z3.And(*[b.order[i] == i for i in range(k)]))]
    for t in range(k):
        c.append(z3.Not(b.nan[t]))
        c.append(z3.Implies(b.cau[t], z3.And(b.tau[t] > 0, b.tau[t] < rv(TAU_STD))))
        c.append(z3.Implies(b.scr[t], z3.And(b.cau[t], b.tau[t] <= rv(TAU_CAUTION))))
    return z3.And(*c)


def inv_safety(b: PlanState, s: PlanState, tc, k: int, core_only: bool = False):
    """Inductive invariant of the fold (everything Prop. 2 needs; no assumption on the range of caution_tau_h).
    core_only: I1, I2, I4, I5 (the parts that bear on approval and on the candidate set), without the scrutiny bookkeeping I3."""
    c = [z3.Implies(s.skip, b.skip), z3.Implies(s.deny, b.deny)]                    # I1 nothing relaxed
    for t in range(k):
        c.append(z3.Not(s.nan[t]))
        c.append(z3.Implies(b.cau[t], z3.And(s.cau[t], s.tau[t] <= b.tau[t])))        # I2 cautions only tighter
        if not core_only:
            c.append(z3.Implies(b.scr[t], s.scr[t]))                                 # I3 scrutiny never dropped
            c.append(z3.Implies(s.scr[t], z3.And(s.cau[t], z3.Or(b.scr[t], s.tau[t] <= tc))))
    c.append(is_perm(s.order, k))                                                    # I4 candidates kept, none repeated
    c.append(s.order[0] == s.first)
    mv = moved(s.first, k)
    c.append(z3.Or(z3.And(s.first == b.first, *[s.order[i] == b.order[i] for i in range(k)]),            # I5 at most one move-to-front
                   z3.And(b.first == 0, s.first != 0, *[s.order[i] == mv[i] for i in range(k)])))
    return z3.And(*c)


def inv_avail(b: PlanState, s: PlanState, k: int):
    """Extra invariant: with caution_tau_h in (0, 0.01] every caution lies in (0, 0.05) and a scrutinised one is <= 0.01."""
    c = []
    for t in range(k):
        c.append(z3.Implies(s.cau[t], z3.And(s.tau[t] > 0, s.tau[t] < rv(TAU_STD))))
        c.append(z3.Implies(s.scr[t], s.tau[t] <= rv(TAU_CAUTION)))
    return z3.And(*c)


# ======================================================================================================================
# 2. THE STATION MODEL: the approval predicate
# ======================================================================================================================
STATION_MUTANTS = {
    'caution_boundary_le': 'apply_memory_caution / peek_hazard: p == tau approves (p <= tau instead of p < tau)',
    'peek_ignores_caution': 'peek_hazard ignores the caution threshold (side views at the baseline rule only)',
    'invalid_score_clear': 'an invalid / NaN hazard score is treated as clear (the pre-I-19 behaviour)',
    'sides_ignored': 'combine_with_look_around ignores the side views',
    'scrutiny_extra_views_skipped': 'scrutiny adds no extra views',
}


class StationVars:
    def __init__(self, tag=''):
        n = lambda s: s + tag
        self.hz = {(w, i): z3.Bool(n(f'hz_{w}{i}')) for w in VIEWS for i in (1, 2)}      # scene == 'hazard'
        self.val = {(w, i): z3.Bool(n(f'val_{w}{i}')) for w in VIEWS for i in (1, 2)}    # scores_valid(call)
        self.p = {(w, i): z3.Real(n(f'p_{w}{i}')) for w in VIEWS for i in (1, 2)}
        self.bad = {w: z3.Bool(n(f'bad_{w}')) for w in VIEWS}                           # the call aborts the check (schema, threshold, conf)
        self.sup = [z3.Bool(n(f'sup{i}')) for i in (1, 2)]                              # supply == expected
        self.low = [z3.Bool(n(f'low{i}')) for i in (1, 2)]                              # supply confidence < 0.5 (non-NaN)
        self.LA = z3.Bool(n('LA'))                                                      # look-around configured (same for all arms)
        self.AD = z3.Bool(n('AD'))                                                      # adaptive views configured
        self.T = z3.Bool(n('T'))                                                        # suspicion trigger: a function of the frames only

    def domain(self):
        """Input domain: a valid score is a finite number in [0, 1]."""
        return z3.And(*[z3.Implies(self.val[k], z3.And(self.p[k] >= 0, self.p[k] <= 1)) for k in self.p])


def station_pred(o: StationVars, hasc, tau, scr, mut=frozenset()):
    """A(o; caution = (hasc, tau), scrutiny = scr) for one station.  Returns (approve, parts)."""
    P = lambda w, i: z3.If(o.val[(w, i)], o.p[(w, i)], z3.RealVal(1))               # _hazard_prob: invalid -> 1.0 (fail closed)
    if 'invalid_score_clear' in mut:
        P = lambda w, i: z3.If(o.val[(w, i)], o.p[(w, i)], z3.RealVal(0))           # noqa: E731
    viable = {w: (z3.Not(o.bad[w]) if 'invalid_score_clear' in mut else
                  z3.And(z3.Not(o.bad[w]), o.val[(w, 1)], o.val[(w, 2)])) for w in VIEWS}
    ge = (lambda a, b: a > b) if 'caution_boundary_le' in mut else (lambda a, b: a >= b)     # p >= tau  (refusal)
    # front: local_decision then apply_memory_caution
    local_ok = z3.And(z3.Not(o.hz[('F', 1)]), z3.Not(o.hz[('F', 2)]), o.sup[0], o.sup[1], z3.Not(o.low[0]), z3.Not(o.low[1]))
    front_cau = z3.Not(z3.And(hasc, z3.Or(ge(P('F', 1), tau), ge(P('F', 2), tau))))
    front = z3.And(viable['F'], local_ok, front_cau)

    def flag(w):                                                                     # peek_hazard(reason, first, second, tau)
        f = z3.Or(o.hz[(w, 1)], o.hz[(w, 2)], z3.Not(viable[w]))
        if 'peek_ignores_caution' not in mut:
            f = z3.Or(f, z3.And(hasc, z3.Or(ge(P(w, 1), tau), ge(P(w, 2), tau))))
        return f

    if 'sides_ignored' in mut:
        std_clear = z3.BoolVal(True)
    else:
        std_clear = z3.And(*[z3.Not(flag(w)) for w in STD_SIDE])
    scr_eff = z3.BoolVal(False) if 'scrutiny_extra_views_skipped' in mut else scr
    extra_taken = z3.And(o.LA, z3.Or(scr_eff, z3.And(o.AD, o.T)))                   # schedule_adaptive_views (given std views clear)
    extra_clear = z3.Implies(extra_taken, z3.And(*[z3.Not(flag(w)) for w in EXTRA]))
    if 'sides_ignored' in mut:
        extra_clear = z3.BoolVal(True)
    approve = z3.And(front, z3.Implies(o.LA, z3.And(std_clear, extra_clear)))
    return approve, {'front': front, 'std_clear': std_clear, 'extra_taken': extra_taken, 'flag': flag,
                     'extra_clear': extra_clear, 'P': P, 'viable': viable, 'ge': ge}


def station_pred_plan(o, skip, deny, isfirst, hasc, tau, scr, mut=frozenset()):
    """The decision at a station under a PLAN: refusal without a visit (naive deny) / approval without a check (naive
    skip) are only possible at the first station; otherwise A(o; plan caution, plan scrutiny)."""
    a, _ = station_pred(o, hasc, tau, scr, mut)
    return z3.If(z3.And(deny, isfirst), z3.BoolVal(False), z3.If(z3.And(skip, isfirst), z3.BoolVal(True), a))


def views_taken(o: StationVars, hasc, tau, scr):
    """Number of camera views of one check (front counts 1), given the frames: upper bound and exact (std views clear)."""
    _, parts = station_pred(o, hasc, tau, scr)
    n = z3.IntVal(1) + z3.If(o.LA, z3.IntVal(2), z3.IntVal(0)) + z3.If(parts['extra_taken'], z3.IntVal(3), z3.IntVal(0))
    return n


# ======================================================================================================================
# 3. THE MISSION-LOOP MODEL (ros/gazebo_waypoint_mission.py main loop + rescuemind/stations.py)
# ======================================================================================================================
LOOP_MUTANTS = {
    'advice_marks_checked': "advice marks its station 'verified': delivery from it without the check",
    'duplicate_candidate': 'the candidate order repeats a station and so leaves one out (not a permutation)',
}


def first_unchecked(order, checked, k):
    """stations.next_candidate(order, checked): the first station of `order` not yet checked, -1 if none."""
    e = z3.IntVal(-1)
    for i in reversed(range(k)):
        ci = z3.Or(*[z3.And(order[i] == t, z3.Not(checked[t])) for t in range(k)])
        e = z3.If(ci, order[i], e)
    return e


def select(arr, idx, k, default):
    e = default
    for t in reversed(range(k)):
        e = z3.If(idx == t, arr[t], e)
    return e


def loop_run(order, kind, k, mut=frozenset(), forced=None):
    """Unrolled mission loop: visit the first unchecked candidate, deliver on APPROVE, go on after CONT, stop on STOP.
    `kind[s]` is the outcome class of the check at s (a function of the frames and the plan); `forced` is the station an
    unsound mutant treats as approved without a check.  Returns a dict of z3 terms."""
    checked = [z3.BoolVal(False) for _ in range(k)]
    halted, stopped, deliv, visits = z3.BoolVal(False), z3.BoolVal(False), z3.IntVal(-1), z3.IntVal(0)
    seq = []
    for _ in range(k):
        cand = first_unchecked(order, checked, k)
        active = z3.And(z3.Not(halted), cand != -1)
        kc = select(kind, cand, k, z3.IntVal(STOP))
        if forced is not None and 'advice_marks_checked' in mut:
            kc = z3.If(cand == forced, z3.IntVal(APPROVE), kc)
        seq.append(z3.If(active, cand, z3.IntVal(-1)))
        checked = [z3.Or(checked[t], z3.And(active, cand == t)) for t in range(k)]
        deliv = z3.If(z3.And(active, kc == APPROVE), cand, deliv)
        stopped = z3.Or(stopped, z3.And(active, kc == STOP))
        halted = z3.Or(halted, z3.Not(active), kc != CONT)
        visits = visits + z3.If(active, z3.IntVal(1), z3.IntVal(0))
    return {'checked': checked, 'deliv': deliv, 'visits': visits, 'seq': seq, 'stopped': stopped, 'halted': halted}


HC_MUTANTS = {
    'hazard_refusal_is_approval': 'under the flag a hazard-refused station is treated as approved (delivery from it)',
    'skip_candidate_after_hazard': 'after a hazard refusal the next candidate is skipped without a check',
    'hazard_still_stops': 'the flag is read but a hazard still ends the search (availability not restored)',
}


def loop_run_hc(order, kind, k, flag, mut=frozenset()):
    """I-42: the mission loop with --hazard-continue.  Outcome classes: APPROVE, CONT (wrong supply: v3.6 recovery), STOP (anything
    else that ends the search: low confidence, broken view), HAZ (a real hazard refusal): with `flag` a HAZ moves on to the next
    candidate exactly like CONT, without it it stops.  `seq` lists the stations really visited (checked) in order."""
    seen = [z3.BoolVal(False) for _ in range(k)]         # visited
    halted, stopped, deliv, visits = z3.BoolVal(False), z3.BoolVal(False), z3.IntVal(-1), z3.IntVal(0)
    seq, skip = [], z3.BoolVal(False)
    for _ in range(k):
        cand = first_unchecked(order, seen, k)
        active = z3.And(z3.Not(halted), cand != -1)
        kc = select(kind, cand, k, z3.IntVal(STOP))
        hz = kc == HAZ
        if 'hazard_refusal_is_approval' in mut:
            kc = z3.If(z3.And(flag, hz), z3.IntVal(APPROVE), kc)
        eff = z3.If(kc == HAZ, z3.If(z3.And(flag, 'hazard_still_stops' not in mut), z3.IntVal(CONT), z3.IntVal(STOP)), kc)
        seq.append(z3.If(active, cand, z3.IntVal(-1)))
        seen = [z3.Or(seen[t], z3.And(active, cand == t)) for t in range(k)]
        if 'skip_candidate_after_hazard' in mut:         # the next candidate is marked visited without being visited
            nxt = first_unchecked(order, seen, k)
            seen = [z3.Or(seen[t], z3.And(active, hz, flag, nxt == t)) for t in range(k)]
        deliv = z3.If(z3.And(active, eff == APPROVE), cand, deliv)
        stopped = z3.Or(stopped, z3.And(active, eff == STOP))
        halted = z3.Or(halted, z3.Not(active), eff != CONT)
        visits = visits + z3.If(active, z3.IntVal(1), z3.IntVal(0))
    return {'seen': seen, 'deliv': deliv, 'visits': visits, 'seq': seq, 'stopped': stopped, 'halted': halted}


# ======================================================================================================================
# 4. PROOFS
# ======================================================================================================================
def proofs_plan(k: int, rec: list) -> list:
    out = []
    b, s, s2 = PlanState.fresh('b', k), PlanState.fresh('s', k), None
    kind, st, tc, tcnan, S = z3.Int('kind'), z3.Int('st'), z3.Real('tc'), z3.Bool('tcnan'), z3.Bool('S')
    wf = wf_base(b, k)
    meta = {'k': k, 'layer': 'plan'}
    # base case
    out.append(prove(f'plan k={k}: base plan satisfies the invariant (I1-I5)', inv_safety(b, b, tc, k), [wf, z3.Not(tcnan)], record=rec, meta=meta))
    # inductive step, any item (safety invariant)
    s2 = plan_step(s, kind, st, tc, tcnan, S, k)
    out.append(prove(f'plan k={k}: one item of advice preserves the invariant (=> any list length)',
                     inv_safety(b, s2, tc, k), [wf, z3.Not(tcnan), inv_safety(b, s, tc, k), item_valid(kind, st, k)],
                     record=rec, meta=meta))
    # availability: the planner never raises for valid advice (tc in (0, 0.01])
    ok_tc = z3.And(z3.Not(tcnan), tc > 0, tc <= rv(TAU_CAUTION))
    out.append(prove(f'plan k={k}: availability invariant is preserved (valid advice never makes the assertion fire)',
                     z3.And(inv_avail(b, s2, k), assert_ok(b, s2, k)),
                     [wf, ok_tc, inv_safety(b, s, tc, k), inv_avail(b, s, k), item_valid(kind, st, k)], record=rec, meta=meta))
    out.append(prove(f'plan k={k}: availability base case', z3.And(inv_avail(b, b, k), assert_ok(b, b, k)), [wf, ok_tc], record=rec, meta=meta))
    # footprint of one item: what an item can touch (cost bound: the only effects of advice are the order and the caution/scrutiny of ONE station)
    same_cau = z3.And(*[z3.And(s2.cau[t] == s.cau[t], s2.scr[t] == s.scr[t], z3.Or(z3.Not(s.cau[t]), s2.tau[t] == s.tau[t])) for t in range(k)],
                      s2.skip == s.skip, s2.deny == s.deny)
    out.append(prove(f'plan k={k}: a safe/skip item changes nothing; a location item without scrutiny changes only the order',
                     z3.Implies(z3.Or(kind >= 2, z3.And(kind == 0, z3.Not(S))), same_cau),
                     [item_valid(kind, st, k)], record=rec, meta=meta))
    out.append(prove(f'plan k={k}: a hazard item touches the caution of the named station only (no other station, no skip/deny)',
                     z3.Implies(kind == 1, z3.And(*[z3.Implies(st != t, z3.And(s2.cau[t] == s.cau[t], s2.scr[t] == s.scr[t], z3.Or(z3.Not(s.cau[t]), s2.tau[t] == s.tau[t])))
                                                    for t in range(k)], s2.skip == s.skip, s2.deny == s.deny, s2.first == s.first)),
                     [item_valid(kind, st, k)], record=rec, meta=meta))
    # unrolled n items, from the concrete code transcription (independent of the invariant)
    for n in (1, 2, 3) if k <= 4 else (2,):
        cur, assum = b, [wf, z3.Not(tcnan)]
        for i in range(n):
            ki, si = z3.Int(f'kind{i}'), z3.Int(f'st{i}')
            assum.append(item_valid(ki, si, k))
            cur = plan_step(cur, ki, si, tc, tcnan, S, k)
        out.append(prove(f'plan k={k}: unrolled n={n} items satisfy the invariant', inv_safety(b, cur, tc, k), assum, record=rec, meta={**meta, 'n': n}))
    return out


def proofs_station(rec: list) -> list:
    out = []
    o = StationVars()
    dom = o.domain()
    # parameters of two plans at one station: base b (baseline / verified memory) and after-advice a
    hb, ha = z3.Bool('hasc_b'), z3.Bool('hasc_a')
    tb, ta = z3.Real('tau_b'), z3.Real('tau_a')
    sb, sa = z3.Bool('scr_b'), z3.Bool('scr_a')
    # what the plan invariant (I1-I3) gives at a station: no skip, no deny, caution only tighter, scrutiny only added
    rel = z3.And(z3.Implies(hb, z3.And(ha, ta <= tb)), z3.Implies(sb, sa), z3.Implies(sa, ha))
    A_a, _ = station_pred(o, ha, ta, sa)
    A_b, _ = station_pred(o, hb, tb, sb)
    A_0, _ = station_pred(o, z3.BoolVal(False), z3.RealVal(0), z3.BoolVal(False))
    meta = {'layer': 'station'}
    out.append(prove('station: approve_with_advice => approve_without_advice (v3.6 rule, no memory, no advice)', z3.Implies(A_a, A_0), [dom, rel], record=rec, meta=meta))
    out.append(prove('station: approve_with_advice => approve_under_base_plan (relative to verified memory)', z3.Implies(A_a, A_b), [dom, rel], record=rec, meta=meta))
    out.append(prove('station: base plan => v3.6 rule', z3.Implies(A_b, A_0), [dom], record=rec, meta=meta))
    # the plan-level decision with skip/deny/isfirst: a monotone plan has skip = deny = False
    isf = z3.Bool('isfirst')
    Aplan = station_pred_plan(o, z3.BoolVal(False), z3.BoolVal(False), isf, ha, ta, sa)
    out.append(prove('station: decision under a monotone plan (skip = deny = False) => v3.6 rule', z3.Implies(Aplan, A_0), [dom, rel], record=rec, meta=meta))
    # advice with no hazard station and no scrutiny changes NOTHING (equivalence), including on a station whose base caution it keeps
    eq = z3.Implies(z3.And(ha == hb, ta == tb, sa == sb), A_a == A_b)
    out.append(prove('station: unchanged parameters => identical decision', eq, [dom], record=rec, meta=meta))
    # where an approval can be lost to advice: only through the caution threshold, or the scrutiny extra views
    P = lambda w, i: z3.If(o.val[(w, i)], o.p[(w, i)], z3.RealVal(1))
    over = lambda w, t: z3.Or(P(w, 1) >= t, P(w, 2) >= t)
    caution_hit = z3.Or(*[over(w, ta) for w in VIEWS])
    _, parts = station_pred(o, ha, ta, sa)
    scr_extra = z3.And(sa, z3.Or(*[z3.Or(o.hz[(w, 1)], o.hz[(w, 2)], o.bad[w], z3.Not(o.val[(w, 1)]), z3.Not(o.val[(w, 2)])) for w in EXTRA]))
    lost = z3.And(A_0, z3.Not(A_a))
    # A_0 here is the baseline WITHOUT any plan; the baseline also uses the base caution -> compare with the base plan too
    out.append(prove('station C: an approval lost to advice (vs no advice) needs p >= caution tau in some view OR a scrutiny extra view that flags',
                     z3.Implies(lost, z3.Or(z3.And(ha, caution_hit), scr_extra)), [dom, rel], record=rec, meta=meta))
    out.append(prove('station C: without scrutiny, an approval lost to advice (vs the base plan) needs p >= tau_a in some view',
                     z3.Implies(z3.And(A_b, z3.Not(A_a), z3.Not(sa)), z3.And(ha, caution_hit)), [dom, rel, z3.Not(sb)], record=rec, meta=meta))
    # views: <= 6 per station; advice adds at most the 3 scrutiny views
    nv_a = views_taken(o, ha, ta, sa)
    nv_0 = views_taken(o, z3.BoolVal(False), z3.RealVal(0), z3.BoolVal(False))
    out.append(prove('station C: views per station <= 6', nv_a <= MAX_VIEWS, [dom, rel], record=rec, meta=meta))
    out.append(prove('station C: views with advice <= views without + 3, and + 0 unless scrutiny', z3.And(nv_a <= nv_0 + 3, z3.Implies(z3.Not(sa), nv_a == nv_0)), [dom, rel], record=rec, meta=meta))
    return out


def proofs_station_plan_linked(k: int, n: int, rec: list) -> list:
    """End to end, unrolled: base plan -> n items of arbitrary advice -> plan -> the decision at an arbitrary station s."""
    b = PlanState.fresh('b', k)
    tc, tcnan, S = z3.Real('tc'), z3.Bool('tcnan'), z3.Bool('S')
    cur, assum = b, [wf_base(b, k), z3.Not(tcnan)]
    for i in range(n):
        ki, si = z3.Int(f'kind{i}'), z3.Int(f'st{i}')
        assum.append(item_valid(ki, si, k))
        cur = plan_step(cur, ki, si, tc, tcnan, S, k)
    s = z3.Int('s')
    assum.append(z3.And(s >= 0, s < k))
    o = StationVars()
    assum.append(o.domain())
    sel = lambda arr: select(arr, s, k, z3.BoolVal(False))
    selr = lambda arr: select(arr, s, k, z3.RealVal(0))
    # base plan has no skip / deny (baseline or verified memory)
    assum += [z3.Not(b.skip), z3.Not(b.deny)]
    A_a = station_pred_plan(o, cur.skip, cur.deny, s == cur.first, sel(cur.cau), selr(cur.tau), sel(cur.scr))
    A_b = station_pred_plan(o, b.skip, b.deny, s == b.first, sel(b.cau), selr(b.tau), sel(b.scr))
    A_0, _ = station_pred(o, z3.BoolVal(False), z3.RealVal(0), z3.BoolVal(False))
    meta = {'layer': 'plan+station', 'k': k, 'n': n}
    return [prove(f'end-to-end k={k} n={n}: approve under planned advice => approve without advice', z3.Implies(A_a, A_0), assum, record=rec, meta=meta),
            prove(f'end-to-end k={k} n={n}: approve under planned advice => approve under the base plan', z3.Implies(A_a, A_b), assum, record=rec, meta=meta)]


def proofs_loop(k: int, rec: list) -> list:
    out = []
    order = [z3.Int(f'O{i}') for i in range(k)]
    kind = [z3.Int(f'kind{t}') for t in range(k)]
    abase = [z3.Bool(f'abase{t}') for t in range(k)]        # A_theta(o_t): the check without advice would approve
    unsafe = [z3.Bool(f'M{t}') for t in range(k)]           # must-refuse
    assum = [is_perm(order, k), *[z3.And(x >= 0, x <= 2) for x in kind],
             *[z3.Implies(kind[t] == APPROVE, abase[t]) for t in range(k)]]          # the station lemma: approve with advice => approve without
    r = loop_run(order, kind, k)
    meta = {'layer': 'loop', 'k': k}
    dl = r['deliv']
    out.append(prove(f'loop k={k}: every delivery is preceded by an approving check at that station',
                     z3.Implies(dl >= 0, z3.And(*[z3.Implies(dl == t, z3.And(r['checked'][t], kind[t] == APPROVE)) for t in range(k)])),
                     assum, record=rec, meta=meta))
    out.append(prove(f'loop k={k}: an unsafe delivery implies the event E_w (some must-refuse station is approved by the unadvised check)',
                     z3.Implies(z3.And(dl >= 0, select(unsafe, dl, k, z3.BoolVal(False))), z3.Or(*[z3.And(unsafe[t], abase[t]) for t in range(k)])),
                     assum, record=rec, meta=meta))
    out.append(prove(f'loop k={k}: visits <= k and each station is checked at most once',
                     z3.And(r['visits'] <= k, r['visits'] == z3.Sum([z3.If(c, 1, 0) for c in r['checked']])), assum, record=rec, meta=meta))
    out.append(prove(f'loop k={k}: the visited stations are a prefix of the candidate order (no candidate skipped)',
                     z3.And(*[z3.Implies(z3.IntVal(i) < r['visits'], r['seq'][i] == order[i]) for i in range(k)],
                            *[z3.Implies(z3.IntVal(i) >= r['visits'], r['seq'][i] == -1) for i in range(k)]), assum, record=rec, meta=meta))
    out.append(prove(f'loop k={k}: without a hazard stop and without a delivery every candidate was checked (recovery reaches all stations)',
                     z3.Implies(z3.And(dl < 0, z3.Not(r['stopped'])), z3.And(*r['checked'])), assum, record=rec, meta=meta))
    # reorder cost: same outcomes, default order vs the order after ONE move-to-front
    j = z3.Int('j')
    dflt = [z3.IntVal(i) for i in range(k)]
    r0 = loop_run(dflt, kind, k)
    r1 = loop_run(moved(j, k), kind, k)
    out.append(prove(f'loop k={k}: location advice costs <= 1 extra station visit (same outcomes) and never more than k',
                     z3.And(r1['visits'] <= r0['visits'] + 1, r1['visits'] <= k),
                     [z3.And(j >= 0, j < k), *[z3.And(x >= 0, x <= 2) for x in kind]], record=rec, meta=meta))
    out.append(prove(f'loop k={k}: location advice cannot create a delivery from a station that never approves',
                     z3.Implies(r1['deliv'] >= 0, select(kind, r1['deliv'], k, z3.IntVal(STOP)) == APPROVE),
                     [z3.And(j >= 0, j < k), *[z3.And(x >= 0, x <= 2) for x in kind]], record=rec, meta=meta))
    return out


def hc_assumptions(order, kind, abase, k):
    """Loop inputs under the flag: any permutation, any outcome class per station, and the station lemma (an approval with advice
    is an approval without)."""
    return [is_perm(order, k), *[z3.And(x >= 0, x <= 3) for x in kind], *[z3.Implies(kind[t] == APPROVE, abase[t]) for t in range(k)]]


def proofs_hazard_continue(k: int, rec: list) -> list:
    """I-42: the loop with --hazard-continue.  Everything of Proposition 2 survives (per-station rule, delivery only after an approving
    check, visited stations a prefix of the order), and a hazard stops being a way to lose a delivery that another station would make."""
    out = []
    order = [z3.Int(f'O{i}') for i in range(k)]
    kind = [z3.Int(f'kind{t}') for t in range(k)]
    abase = [z3.Bool(f'abase{t}') for t in range(k)]
    unsafe = [z3.Bool(f'M{t}') for t in range(k)]
    on = z3.BoolVal(True)
    assum = hc_assumptions(order, kind, abase, k)
    r = loop_run_hc(order, kind, k, on)
    meta = {'layer': 'loop_hazard_continue', 'k': k}
    dl = r['deliv']
    out.append(prove(f'hazard-continue k={k}: every delivery is preceded by an approving check at that station',
                     z3.Implies(dl >= 0, z3.And(*[z3.Implies(dl == t, z3.And(r['seen'][t], kind[t] == APPROVE)) for t in range(k)])),
                     assum, record=rec, meta=meta))
    out.append(prove(f'hazard-continue k={k}: an unsafe delivery implies the event E_w (some must-refuse station is approved by the unadvised check)',
                     z3.Implies(z3.And(dl >= 0, select(unsafe, dl, k, z3.BoolVal(False))), z3.Or(*[z3.And(unsafe[t], abase[t]) for t in range(k)])),
                     assum, record=rec, meta=meta))
    out.append(prove(f'hazard-continue k={k}: visits <= k, each station at most once, visited stations are a prefix of the candidate order',
                     z3.And(r['visits'] <= k, r['visits'] == z3.Sum([z3.If(c, 1, 0) for c in r['seen']]),
                            *[z3.Implies(z3.IntVal(i) < r['visits'], r['seq'][i] == order[i]) for i in range(k)],
                            *[z3.Implies(z3.IntVal(i) >= r['visits'], r['seq'][i] == -1) for i in range(k)]), assum, record=rec, meta=meta))
    out.append(prove(f'hazard-continue k={k}: a hazard refusal is never a delivery station, and without a delivery or another stop every candidate was visited',
                     z3.And(*[z3.Implies(kind[t] == HAZ, dl != t) for t in range(k)],
                            z3.Implies(z3.And(dl < 0, z3.Not(r['stopped'])), z3.And(*r['seen']))), assum, record=rec, meta=meta))
    # availability: a hazard cannot take away a delivery that another station makes (no other stop class)
    nostop = [x != STOP for x in kind]
    out.append(prove(f'hazard-continue k={k}: if some station approves and nothing else stops the search, the mission delivers (hazards cannot cost it)',
                     z3.Implies(z3.Or(*[x == APPROVE for x in kind]), dl >= 0), assum + nostop, record=rec, meta=meta))
    # the same loop WITHOUT the flag loses it: the contrast (a counterexample is the expected answer)
    r0 = loop_run_hc(order, kind, k, z3.BoolVal(False))
    res = prove(f'CONTRAST hazard-continue k={k}: v3.6 (flag off) can lose a delivery that another station makes (expected: counterexample)',
                z3.Implies(z3.Or(*[x == APPROVE for x in kind]), r0['deliv'] >= 0), assum + nostop, meta=meta)
    d = {'name': res['name'], 'result': res['result'], 'proved': res['result'] == 'sat', 'seconds': res['seconds'], **meta}
    rec.append(d); out.append(d)
    # advice, availability: advice moves any station's outcome only from APPROVE to HAZ (apply_memory_caution / combine_with_look_around
    # are the identity on a refusal: a differential test on the real functions), at the stations it tightened.
    kind_adv = [z3.Int(f'kadv{t}') for t in range(k)]
    tight = [z3.Bool(f'tight{t}') for t in range(k)]
    o_adv = [z3.Int(f'OA{i}') for i in range(k)]
    H = [z3.Or(kind_adv[t] == kind[t], z3.And(tight[t], kind[t] == APPROVE, kind_adv[t] == HAZ)) for t in range(k)]
    avail = assum + [is_perm(o_adv, k), *H, *[z3.Implies(kind_adv[t] == APPROVE, kind[t] == APPROVE) for t in range(k)], *nostop]
    ra = loop_run_hc(o_adv, kind_adv, k, on)
    rn = loop_run_hc(order, kind, k, on)
    out.append(prove(f'hazard-continue k={k}: advice (any order, any tightened set) loses a delivery only if EVERY station that approves without advice was tightened',
                     z3.Implies(z3.And(rn['deliv'] >= 0, ra['deliv'] < 0), z3.And(*[z3.Implies(kind[t] == APPROVE, tight[t]) for t in range(k)])),
                     avail, record=rec, meta=meta))
    j = z3.Int('j')
    only_j = [z3.Implies(tight[t], j == t) for t in range(k)]
    out.append(prove(f'hazard-continue k={k}: with ONE tightened station (location advice + scrutiny) a second approving station always delivers',
                     z3.Implies(z3.Or(*[z3.And(kind[t] == APPROVE, j != t) for t in range(k)]), ra['deliv'] >= 0),
                     avail + only_j + [z3.And(j >= 0, j < k)], record=rec, meta=meta))
    return out


def hc_mutant_cex(name: str, k: int = 4) -> dict:
    mut = frozenset([name])
    order = [z3.Int(f'O{i}') for i in range(k)]
    kind = [z3.Int(f'kind{t}') for t in range(k)]
    abase = [z3.Bool(f'abase{t}') for t in range(k)]
    assum = hc_assumptions(order, kind, abase, k)
    r = loop_run_hc(order, kind, k, z3.BoolVal(True), mut)
    dl = r['deliv']
    if name == 'hazard_still_stops':
        claim = z3.Implies(z3.Or(*[x == APPROVE for x in kind]), dl >= 0)
        assum = assum + [x != STOP for x in kind]
    elif name == 'hazard_refusal_is_approval':
        claim = z3.And(*[z3.Implies(kind[t] == HAZ, dl != t) for t in range(k)])
    else:      # skip_candidate_after_hazard: the visited stations are no longer a prefix of the order
        claim = z3.And(r['visits'] == z3.Sum([z3.If(c, 1, 0) for c in r['seen']]),
                       *[z3.Implies(z3.IntVal(i) < r['visits'], r['seq'][i] == order[i]) for i in range(k)])
    res = prove(f'MUTANT {name}', claim, assum)
    out = {'mutant': name, 'description': HC_MUTANTS[name], 'z3': res['result'], 'seconds': res['seconds'], 'k': k}
    if res['result'] == 'sat':
        m = res['model']
        out['counterexample'] = {'order': [mval(m, x) for x in order], 'outcome_class(0=approve,1=continue,2=stop,3=hazard)': [mval(m, x) for x in kind],
                                 'delivered_from': mval(m, dl), 'visited': [mval(m, x) for x in r['seq']]}
    return out


# ---------------------------------------------------------------------------------------------------------------------
# mutants: z3 counterexamples
# ---------------------------------------------------------------------------------------------------------------------
GRID_TAU = [Fraction(x) for x in (0.0025, 0.005, 0.0099, 0.01, 0.02, 0.03, 0.04)]          # exactly representable doubles
GRID_P = sorted(set(GRID_TAU) | {Fraction(x) for x in (0.0, 0.001, 0.0075, 0.015, 0.05, 0.3, 1.0)})


def on_grid(x, grid):
    return z3.Or(*[x == rv(g) for g in grid])


def plan_mutant_cex(name: str, k: int = 3, n: int = 2) -> dict:
    """Search an advice list of length <= n that makes the mutated plan violate the safety invariant."""
    mut = frozenset([name])
    b = PlanState.fresh('b', k)
    tc, S = z3.Real('tc'), z3.Bool('S')
    items = [(z3.Int(f'kind{i}'), z3.Int(f'st{i}')) for i in range(n)]
    cur = b
    # replayable: thresholds are IEEE doubles from a small grid (a rational like 1/100 + 1e-30 does not exist as a double)
    assum = [wf_base(b, k), z3.Not(b.skip), z3.Not(b.deny), on_grid(tc, GRID_TAU), tc <= rv(TAU_CAUTION),
             *[z3.Implies(b.cau[t], on_grid(b.tau[t], GRID_TAU)) for t in range(k)]]
    for ki, si in items:
        assum.append(item_valid(ki, si, k))
        cur = plan_step(cur, ki, si, tc, z3.BoolVal(False), S, k, mut)
    res = prove(f'MUTANT {name}', inv_safety(b, cur, tc, k, core_only=True), assum)
    out = {'mutant': name, 'description': PLAN_MUTANTS[name], 'z3': res['result'], 'seconds': res['seconds'], 'k': k, 'n': n}
    if res['result'] == 'sat':
        m = res['model']
        out['counterexample'] = {
            'tc': mval(m, tc), 'scrutiny': mval(m, S),
            'base': {'first': mval(m, b.first), 'order': [mval(m, x) for x in b.order], 'caution': {t: mval(m, b.tau[t]) for t in range(k) if mval(m, b.cau[t])},
                     'scrutiny': [t for t in range(k) if mval(m, b.scr[t])]},
            'items': [{'kind': ['location', 'hazard', 'safe', 'skip'][mval(m, ki)], 'station': (None if mval(m, si) < 0 else mval(m, si))} for ki, si in items],
            'after': {'first': mval(m, cur.first), 'order': [mval(m, x) for x in cur.order], 'skip': mval(m, cur.skip), 'deny': mval(m, cur.deny),
                      'caution': {t: mval(m, cur.tau[t]) for t in range(k) if mval(m, cur.cau[t])}}}
        out['model'] = m
    return out


def t_tie(o: StationVars):
    """For REPLAYABLE counterexamples only: tie the free trigger T to the scores it is computed from (round(max p, 4) >= 0.005).
    The proofs leave T free (a stronger statement)."""
    ps = [z3.If(o.val[(w, i)], o.p[(w, i)], z3.RealVal(1)) for w in ('F', *STD_SIDE) for i in (1, 2)]
    m = ps[0]
    for x in ps[1:]:
        m = z3.If(x > m, x, m)
    return z3.Or(z3.And(o.T, m >= rv(Fraction(6, 1000))), z3.And(z3.Not(o.T), m <= rv(Fraction(4, 1000))))


def station_mutant_cex(name: str, against: str) -> dict:
    """Does the mutated approval predicate (with plan parameters ha/ta/sa) approve something the specification refuses?"""
    mut = frozenset([name])
    o = StationVars()
    hb, ha = z3.Bool('hasc_b'), z3.Bool('hasc_a')
    tb, ta = z3.Real('tau_b'), z3.Real('tau_a')
    sb, sa = z3.Bool('scr_b'), z3.Bool('scr_a')
    rel = z3.And(z3.Implies(hb, z3.And(ha, ta <= tb)), z3.Implies(sb, sa), z3.Implies(sa, ha))
    rng = [z3.And(t > 0, t < rv(TAU_STD)) for t in (ta, tb)]
    A_mut, _ = station_pred(o, ha, ta, sa, mut)
    if against == 'v36':
        A_ref, _ = station_pred(o, z3.BoolVal(False), z3.RealVal(0), z3.BoolVal(False))
    elif against == 'spec':
        A_ref, _ = station_pred(o, ha, ta, sa)
    else:
        A_ref, _ = station_pred(o, hb, tb, sb)
    # replayable counterexamples: no schema/threshold abort, the plan's cautions are real thresholds in (0, 0.05)
    res = prove(f'MUTANT {name} vs {against}', z3.Implies(A_mut, A_ref),
                [o.domain(), rel, *rng, z3.Implies(ha, ta > 0), *[z3.Not(o.bad[w]) for w in VIEWS], t_tie(o),
                 *([] if name == 'invalid_score_clear' else [o.val[k_] for k_ in o.val]),
                 on_grid(ta, GRID_TAU), on_grid(tb, GRID_TAU), *[z3.Implies(o.val[k_], on_grid(o.p[k_], GRID_P)) for k_ in o.p]])
    out = {'mutant': name, 'description': STATION_MUTANTS[name], 'against': against, 'z3': res['result'], 'seconds': res['seconds']}
    if res['result'] == 'sat':
        m = res['model']
        out['counterexample'] = {
            'plan_params': {k_: mval(m, v) for k_, v in (('base_has_caution', hb), ('base_tau', tb), ('base_scrutiny', sb), ('has_caution', ha), ('tau', ta), ('scrutiny', sa))},
            'LA': mval(m, o.LA), 'AD': mval(m, o.AD), 'T': mval(m, o.T),
            'views': {w: {'scene_hazard': [mval(m, o.hz[(w, i)]) for i in (1, 2)], 'score_valid': [mval(m, o.val[(w, i)]) for i in (1, 2)],
                          'p': [mval(m, o.p[(w, i)]) for i in (1, 2)], 'aborts': mval(m, o.bad[w])} for w in VIEWS},
            'supply_ok': [mval(m, x) for x in o.sup], 'low_conf': [mval(m, x) for x in o.low]}
        out['model'] = m
        out['vars'] = o
    return out


def loop_mutant_cex(name: str, k: int = 4) -> dict:
    mut = frozenset([name])
    order = [z3.Int(f'O{i}') for i in range(k)]
    kind = [z3.Int(f'kind{t}') for t in range(k)]
    abase = [z3.Bool(f'abase{t}') for t in range(k)]
    forced = z3.Int('forced')
    assum = [*[z3.And(x >= 0, x <= 2) for x in kind], *[z3.Implies(kind[t] == APPROVE, abase[t]) for t in range(k)], z3.And(forced >= 0, forced < k)]
    if name == 'duplicate_candidate':
        assum += [*[z3.And(o_ >= 0, o_ < k) for o_ in order]]          # NOT Distinct: the mutant's order may repeat a station
        r = loop_run(order, kind, k, mut, forced)
        claim = z3.Implies(z3.And(r['deliv'] < 0, z3.Not(r['stopped'])), z3.And(*r['checked']))
    else:
        assum += [is_perm(order, k)]
        r = loop_run(order, kind, k, mut, forced)
        claim = z3.Implies(r['deliv'] >= 0, z3.And(*[z3.Implies(r['deliv'] == t, abase[t]) for t in range(k)]))
    res = prove(f'MUTANT {name}', claim, assum)
    out = {'mutant': name, 'description': LOOP_MUTANTS[name], 'z3': res['result'], 'seconds': res['seconds'], 'k': k}
    if res['result'] == 'sat':
        m = res['model']
        out['counterexample'] = {'order': [mval(m, x) for x in order], 'outcome_class(0=approve,1=continue,2=stop)': [mval(m, x) for x in kind],
                                 'unadvised_check_approves': [mval(m, x) for x in abase], 'advised_station': mval(m, forced),
                                 'delivered_from': mval(m, r['deliv']), 'checked': [mval(m, c) for c in r['checked']]}
    return out


# ======================================================================================================================
# 5. THE LINK: concrete evaluation of the models, the REAL code, and the differential harness
# ======================================================================================================================
def _vars_in(e, acc):
    if z3.is_const(e) and e.decl().kind() == z3.Z3_OP_UNINTERPRETED:
        acc[e.decl().name()] = e
    else:
        for c in e.children():
            _vars_in(c, acc)


class Compiled:
    """A z3 term (tuple of terms) compiled once; `.eval(env)` substitutes concrete values and lets z3 simplify to a constant."""

    def __init__(self, terms: dict):
        self.terms = terms
        self.vars: dict = {}
        for t in terms.values():
            _vars_in(t, self.vars)

    def eval(self, env: dict) -> dict:
        sub = [(self.vars[n], v) for n, v in env.items() if n in self.vars]
        out = {}
        for name, t in self.terms.items():
            r = z3.simplify(z3.substitute(t, *sub))
            out[name] = r
        return out


def zbool(r) -> bool:
    if z3.is_true(r):
        return True
    if z3.is_false(r):
        return False
    raise ValueError(f'not a constant: {r}')


def zint(r) -> int:
    return r.as_long()


def zfrac(r) -> Fraction:
    return r.as_fraction() if z3.is_rational_value(r) else Fraction(r.as_long())


def zreal_of(x: float):
    """A finite float as an exact z3 real."""
    return rv(Fraction(x))


BIG = Fraction(10) ** 30


def real_of_float(x: float):
    """+-inf are mapped to +-1e30 (they only matter through a comparison with numbers < 1)."""
    if x == math.inf:
        return rv(BIG)
    if x == -math.inf:
        return rv(-BIG)
    return rv(Fraction(x))


def _simp_state(st: PlanState) -> PlanState:
    f = z3.simplify
    return PlanState(f(st.first), [f(x) for x in st.order], [f(x) for x in st.cau], [f(x) for x in st.tau], [f(x) for x in st.nan],
                     [f(x) for x in st.scr], f(st.skip), f(st.deny))


def eval_plan_model(env: dict, k: int, n: int, mut=frozenset()) -> dict:
    """The plan model evaluated on concrete values: the SAME plan_step / assert_ok terms as in the proofs, built over
    constants and reduced by z3 (simplify) after every item.  Returns python values."""
    cur = PlanState(env['b_first'], [env[f'b_ord{i}'] for i in range(k)], [env[f'b_cau{i}'] for i in range(k)], [env[f'b_tau{i}'] for i in range(k)],
                    [env[f'b_nan{i}'] for i in range(k)], [env[f'b_scr{i}'] for i in range(k)], env['b_skip'], env['b_deny'])
    base = cur
    ivalid = []
    for i in range(n):
        cur = _simp_state(plan_step(cur, env[f'kind{i}'], env[f'st{i}'], env['tc'], env['tcnan'], env['S'], k, mut))
        ivalid.append(env[f'ivalid{i}'])
    defined = z3.simplify(z3.And(*ivalid, assert_ok(base, cur, k))) if n else z3.BoolVal(True)
    r = {'defined': defined, 'first': cur.first, 'skip': cur.skip, 'deny': cur.deny}
    for i in range(k):
        r[f'ord{i}'], r[f'cau{i}'], r[f'tau{i}'], r[f'scr{i}'] = cur.order[i], cur.cau[i], cur.tau[i], cur.scr[i]
    return r


_STATION_CACHE: dict = {}


def compiled_station(mut=frozenset()):
    if mut not in _STATION_CACHE:
        o = StationVars()
        hasc, tau, scr = z3.Bool('hasc'), z3.Real('tau'), z3.Bool('scr')
        A, parts = station_pred(o, hasc, tau, scr, mut)
        _STATION_CACHE[mut] = (Compiled({'A': A, 'extra_taken': parts['extra_taken']}), o)
    return _STATION_CACHE[mut]


# ---- alpha: the abstraction from raw Python values to model values.  Written from the SPECIFICATION (a usable hazard
# score is a finite real number in [0, 1], not a bool), NOT by calling the code under test.
def alpha_valid(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and 0.0 <= x <= 1.0


def alpha_thr_ok(thr) -> bool:
    return isinstance(thr, (int, float)) and not isinstance(thr, bool) and math.isfinite(thr) and abs(float(thr) - 0.05) <= 1e-9


MISSING = '<missing>'


def make_call(case_view: dict, pass_i: int, sha: str, expected: str = 'water') -> dict:
    """A structurally valid local-model response whose scalar fields are the drawn raw values."""
    from rescuemind.local_vision import PRIMARY_MODEL
    v = case_view
    scores = {}
    if v['p'][pass_i] is not MISSING:
        scores['hazard_prob'] = v['p'][pass_i]
    if v['thr'][pass_i] is not MISSING:
        scores['hazard_threshold'] = v['thr'][pass_i]
    probs = {'water': 0.9, 'medicine': 0.05, 'other': 0.05}
    c = v['conf'][pass_i]
    probs[expected] = c
    scores['supply_probs'] = probs
    return {'backend': 'local_transformers', 'real_inference': True, 'model': PRIMARY_MODEL, 'image_sha256': sha, 'pass_id': pass_i + 1,
            'result': {'supply': v['supply'][pass_i], 'scene': 'hazard' if v['hz'][pass_i] else 'clear'}, 'scores': scores}


def view_env(w: str, v: dict, env: dict) -> None:
    """alpha for one view: fills the model's variables."""
    for i in (0, 1):
        raw = v['p'][i]
        ok = alpha_valid(raw)
        env[f'val_{w}{i + 1}'] = z3.BoolVal(ok)
        env[f'p_{w}{i + 1}'] = rv(Fraction(raw)) if ok else rv(0)
        env[f'hz_{w}{i + 1}'] = z3.BoolVal(bool(v['hz'][i]))
    # code (local_vision._confidence, after the F2/F3 fix): a bool, a non-number, a non-finite or out-of-range value aborts
    conf_bad = any(isinstance(c, bool) or not isinstance(c, (int, float)) or not math.isfinite(c) or not 0.0 <= c <= 1.0
                   for c in v['conf'])
    thr_bad = any(not alpha_thr_ok(t) for t in v['thr'])
    env[f'bad_{w}'] = z3.BoolVal(conf_bad or thr_bad)


def station_env(case: dict) -> dict:
    env = {}
    for w in VIEWS:
        view_env(w, case['views'][w], env)
    f = case['views']['F']
    for i in (0, 1):
        env[f'sup{i + 1}'] = z3.BoolVal(f['supply'][i] == 'water')
        c = f['conf'][i]
        isnum = isinstance(c, (int, float)) and not isinstance(c, bool) and math.isfinite(c)
        # code: `c < 0.5`; a malformed value (bool, NaN, inf, out of range) aborts the check (bad, F2/F3 fix)
        env[f'low{i + 1}'] = z3.BoolVal(bool(isnum and c < 0.5))
    env['LA'], env['AD'] = z3.BoolVal(case['LA']), z3.BoolVal(case['AD'])
    env['T'] = z3.BoolVal(case['T'])
    return env


# ---- the REAL code, assembled the way the mission node assembles it -----------------------------------------------------
class Impl:
    """The functions of the decision path.  `real()` binds the repository code; mutants override single members."""

    def __init__(self, **kw):
        self.__dict__.update(kw)

    @staticmethod
    def real() -> 'Impl':
        from rescuemind import advice, mission_memory as mm, local_vision as lv, adaptive_views as av
        return Impl(plan=advice.plan, assert_monotone=advice.assert_monotone, AdviceError=advice.AdviceError,
                    apply_memory_caution=mm.apply_memory_caution, peek_hazard=mm.peek_hazard, scores_valid=mm.scores_valid,
                    local_decision=lv.local_decision, check_hazard_threshold=lv.check_hazard_threshold,
                    combine_with_look_around=lv.combine_with_look_around, suspicion=av.suspicion,
                    require_valid_scores=lv.require_valid_scores, LocalInferenceError=lv.LocalInferenceError)


def suspicion_trigger(impl, front_calls, peeks) -> float:
    return impl.suspicion({'model_calls': {'first': front_calls[0], 'second': front_calls[1]}}, peeks)


def real_approve(impl: Impl, case: dict, hasc: bool, tau, scr: bool, record: dict | None = None) -> bool:
    """The recorded decision of one station check with caution (hasc, tau) and scrutiny `scr`, computed by composing the real
    functions as ros/gazebo_waypoint_mission.py does: onsite_check (verify_station_local: require_valid_scores,
    check_hazard_threshold, local_decision) -> apply_memory_caution -> look_around_peek (peek_hazard, combine_with_look_around)
    -> schedule_adaptive_views (suspicion; extra views when --adaptive-views is on or the station is scrutinised).
    Any exception (the node aborts the mission) is a refusal."""
    expected = 'water'
    rec = record if record is not None else {}
    try:
        def ingest(w):
            v = case['views'][w]
            sha = hashlib.sha256(w.encode()).hexdigest()
            a, b = make_call(v, 0, sha), make_call(v, 1, sha)
            for c in (a, b):
                impl.require_valid_scores(c)
                impl.check_hazard_threshold(c, 0.05)
            return a, b, impl.local_decision(expected, a, b), sha

        fa, fb, dec, fsha = ingest('F')
        rec.update({'front': (fa, fb), 'front_sha': fsha})
        if hasc:
            dec = impl.apply_memory_caution(dec, fa, fb, tau)
        rec['dec_front'] = dec
        if not dec['allow']:
            return False
        if not case['LA']:
            rec['decision'] = dec
            return True
        peeks = []
        rec['peeks'] = peeks
        tau_p = tau if hasc else None

        def look(w):
            pa, pb, pd, sha = ingest(w)
            hz = impl.peek_hazard(pd['reason'], pa, pb, tau_p)
            peeks.append({'side': w, 'hazard': hz, 'model_calls': {'first': pa, 'second': pb}, 'image_sha256': sha})
            return hz

        for w in STD_SIDE:
            if look(w):
                rec['decision'] = impl.combine_with_look_around(dec, peeks)
                return bool(rec['decision']['allow'])
        # schedule_adaptive_views (ros/gazebo_waypoint_mission.py): extra views when off > 0 and (suspicious or scrutinised)
        off = case['AD'] or scr
        if off:
            p_max = suspicion_trigger(impl, (fa, fb), peeks)
            triggered = p_max >= float(TAU_SUS) or scr
            rec['adaptive'] = {'p_max': p_max, 'tau_sus': float(TAU_SUS), 'triggered': triggered, 'offset_m': 0.8, 'near_m': 0.3}
            if scr:
                rec['adaptive']['scrutiny'] = True
            if triggered:
                for w in EXTRA:
                    if look(w):
                        rec['decision'] = impl.combine_with_look_around(dec, peeks)
                        return bool(rec['decision']['allow'])
        rec['decision'] = impl.combine_with_look_around(dec, peeks)
        return bool(rec['decision']['allow'])
    except Exception as e:           # noqa: BLE001  -- the node aborts: no approval
        rec['aborted'] = f'{type(e).__name__}: {e}'
        return False


def trigger_from_case(case: dict) -> bool:
    """alpha for T: the suspicion trigger is a function of the frames only (round(max p, 4) >= 0.005, invalid = 1.0)."""
    ps = []
    for w in ('F', *STD_SIDE):
        for i in (0, 1):
            raw = case['views'][w]['p'][i]
            ps.append(float(raw) if alpha_valid(raw) else 1.0)
    return round(max(ps), 4) >= float(TAU_SUS)


def model_approve(case: dict, hasc: bool, tau, scr: bool, mut=frozenset()) -> bool:
    comp, _ = compiled_station(mut)
    env = station_env(case)
    env['hasc'], env['scr'] = z3.BoolVal(bool(hasc)), z3.BoolVal(bool(scr))
    env['tau'] = rv(Fraction(tau)) if hasc else rv(0)
    return zbool(comp.eval(env)['A'])


def audit_approve(impl_audit, case: dict, rec: dict, hasc: bool, tau, scr: bool) -> bool | None:
    """The interlock's independent recomputation (local_run_audit.audit_local_checkpoint) on the record the harness built.
    None if there is no record (the check aborted)."""
    if 'aborted' in rec or ('decision' not in rec and not rec.get('dec_front')):
        return None            # the node aborted the mission: there is no checkpoint to audit
    dec = rec.get('decision', rec['dec_front'])
    fa, fb = rec['front']
    cp = {'checkpoint_type': 'local_on_site_camera_supply_check', 'backend': 'LOCAL_ONLY_NO_CLOUD_API', 'mode': 'single',
          'image_sha256': rec['front_sha'], 'model_calls': {'first': fa, 'second': fb}, 'decision': dec}
    if hasc:
        cp['memory_caution_tau_h'] = float(tau)
    if 'peeks' in rec:
        la = {'peeks': [dict(p) for p in rec['peeks']]}
        if 'adaptive' in rec:
            la['adaptive'] = dict(rec['adaptive'])
        cp['look_around'] = la
    try:
        r = impl_audit(cp, rec['front_sha'], expected='water', hazard_threshold=0.05, require_threshold=True)
        return bool(r['allow'])
    except Exception as e:                       # noqa: BLE001
        rec['audit_error'] = f'{type(e).__name__}: {e}'
        return False


def diff_station_case(case: dict, impl: Impl | None = None, mut=frozenset(), with_audit: bool = True) -> list:
    """Compare the real code and the z3 model on one station case, for the parameter sets (none / base / planned).
    Returns the list of disagreements (empty = refinement holds on this input)."""
    from rescuemind.local_run_audit import audit_local_checkpoint
    impl = impl or Impl.real()
    bad = []
    case = dict(case, T=trigger_from_case(case))
    for hasc, tau, scr in case['params']:
        rec: dict = {}
        r = real_approve(impl, case, hasc, tau, scr, rec)
        m = model_approve(case, hasc, tau, scr, mut)
        if r != m:
            bad.append({'kind': 'real!=model', 'params': (hasc, tau, scr), 'real': r, 'model': m, 'aborted': rec.get('aborted')})
        if with_audit and impl is not None and getattr(impl, 'audit_ok', True):
            a = audit_approve(audit_local_checkpoint, case, rec, hasc, tau, scr)
            # the audit may refuse more than the node (it also checks consistency), but it must never approve what the model refuses,
            # and must approve what the node approved and the model approves
            if hasc and not (0 < tau < 0.05):
                continue                         # not a legal caution (the plan assertion rejects it); the audit rightly refuses it
            if a is True and not m:
                bad.append({'kind': 'audit approves, model refuses', 'params': (hasc, tau, scr)})
            if a is False and r and m and 'aborted' not in rec:
                bad.append({'kind': 'audit refuses an approved check', 'params': (hasc, tau, scr), 'err': rec.get('audit_error')})
    return bad


def p2_property_case(case: dict, impl: Impl | None = None) -> list:
    """Proposition 2 as a property of the REAL code: with the planned parameters (a result of the real advice.plan), approve
    => approve under the base parameters => approve under the plain v3.6 rule.  No model involved."""
    impl = impl or Impl.real()
    (h0, t0, s0), (hb, tb, sb), (ha, ta, sa) = case['params'][:3]
    case = dict(case, T=trigger_from_case(case))
    a0 = real_approve(impl, case, False, None, False)
    ab = real_approve(impl, case, hb, tb, sb)
    aa = real_approve(impl, case, ha, ta, sa)
    bad = []
    if aa and not a0:
        bad.append('approve with advice but not without advice')
    if aa and not ab:
        bad.append('approve with advice but not under the base plan')
    return bad


# ---- plan layer ---------------------------------------------------------------------------------------------------------
def station_set(kind: str):
    from rescuemind.stations import StationSet
    if kind == 'legacy':
        return StationSet.legacy()
    if kind == 'k2':
        return StationSet.build(['A1', 'B1'], {'A1': 'medicine', 'B1': 'water'})
    k = int(kind[1:])
    ids = [f'S{i}' for i in range(k)]
    return StationSet.build(ids, {s: ('water' if i % 2 == 0 else 'medicine') for i, s in enumerate(ids)})


def spec_order(ss, item, first):
    """Candidate order from the specification (stations.StationSet.order): `first` to the front, the others in default order."""
    d = list(ss.default_order(item))
    return [first] + [x for x in d if x != first]


def plan_env(pc: dict, k: int, n: int) -> dict:
    """alpha for a plan case: base plan, items, caution_tau_h, scrutiny flag -> model inputs."""
    ss, item = pc['ss'], pc['item']
    dflt = ss.default_order(item)
    idx = {s: i for i, s in enumerate(dflt)}
    base = pc['base']
    env = {'b_first': z3.IntVal(idx[base['first_station']]), 'b_skip': z3.BoolVal(bool(base.get('skip_check'))),
           'b_deny': z3.BoolVal(bool(base.get('deny_without_visit'))), 'S': z3.BoolVal(bool(pc['S']))}
    order = base.get('order') or spec_order(ss, item, base['first_station'])
    for i in range(k):
        env[f'b_ord{i}'] = z3.IntVal(idx[order[i]])
    cau = base.get('caution') or {}
    scr = set(base.get('scrutiny') or [])
    for sid, i in idx.items():
        c = cau.get(sid)
        env[f'b_cau{i}'] = z3.BoolVal(c is not None)
        env[f'b_tau{i}'] = rv(Fraction(c['tau_h'])) if c is not None else rv(0)
        env[f'b_nan{i}'] = z3.BoolVal(False)
        env[f'b_scr{i}'] = z3.BoolVal(sid in scr)
    tc = pc['tc']
    env['tcnan'] = z3.BoolVal(isinstance(tc, float) and math.isnan(tc))
    env['tc'] = rv(0) if env['tcnan'] else real_of_float(float(tc))
    for i in range(n):
        it = pc['items'][i]
        valid, kd, st = alpha_item(it, ss.ids)
        env[f'ivalid{i}'] = z3.BoolVal(valid)
        env[f'kind{i}'] = z3.IntVal(kd)
        env[f'st{i}'] = z3.IntVal(-1 if st is None else idx[st] if valid else 0)
    return env


def alpha_item(it, ids):
    """Specification of advice.validate for one item: (valid, kind code, station)."""
    kinds = ('location', 'hazard', 'safe', 'skip')
    sources = ('memory', 'peer', 'inventory', 'operator')
    if not isinstance(it, dict):
        return False, 2, None
    kd, src, st = it.get('kind'), it.get('source'), it.get('station')
    ok_kind = isinstance(kd, str) and kd in kinds
    ok_src = isinstance(src, str) and src in sources
    ok_st = st is None or (isinstance(st, str) and st in ids)
    ok = ok_kind and ok_src and ok_st and not (ok_kind and kd in ('location', 'hazard') and st is None)
    return ok, (kinds.index(kd) if ok_kind else 2), (st if ok_st else None)


def real_plan(impl: Impl, pc: dict):
    base = copy.deepcopy(pc['base'])
    try:
        out = impl.plan(pc['item'], pc['items'], 'monotone', base=base, caution_tau_h=pc['tc'], stations=pc['ss'], scrutiny=pc['S'])
    except Exception as e:                       # noqa: BLE001  (a mutant module has its own AdviceError class)
        if type(e).__name__ == 'AdviceError':
            return None
        raise
    return out


def diff_plan_case(pc: dict, impl: Impl | None = None, mut=frozenset()) -> list:
    """Real advice.plan(mode='monotone') against the z3 plan model on one input.  Disagreements = []."""
    impl = impl or Impl.real()
    ss, item = pc['ss'], pc['item']
    k, n = ss.k, len(pc['items']) if isinstance(pc['items'], (list, tuple)) else 0
    if not isinstance(pc['items'], (list, tuple)):
        out = real_plan(impl, pc)
        return [] if out is None else [{'kind': 'non-list advice accepted'}]
    r = eval_plan_model(plan_env(pc, k, n), k, n, mut)
    defined = zbool(r['defined'])
    out = real_plan(impl, pc)
    if out is None or not defined:
        return [] if (out is None) == (not defined) else [{'kind': 'defined mismatch', 'real_defined': out is not None, 'model_defined': defined}]
    dflt = ss.default_order(item)
    idx = {s: i for i, s in enumerate(dflt)}
    bad = []
    order = out.get('order') or spec_order(ss, item, out['first_station'])
    got = {'first': idx[out['first_station']], 'order': [idx[s] for s in order], 'skip': bool(out['skip_check']), 'deny': bool(out['deny_without_visit']),
           'cau': [dflt[i] in (out.get('caution') or {}) for i in range(k)],
           'tau': [Fraction(out['caution'][dflt[i]]['tau_h']) if dflt[i] in (out.get('caution') or {}) else None for i in range(k)],
           'scr': [dflt[i] in (out.get('scrutiny') or []) for i in range(k)]}
    want = {'first': zint(r['first']), 'order': [zint(r[f'ord{i}']) for i in range(k)], 'skip': zbool(r['skip']), 'deny': zbool(r['deny']),
            'cau': [zbool(r[f'cau{i}']) for i in range(k)],
            'tau': [zfrac(r[f'tau{i}']) if zbool(r[f'cau{i}']) else None for i in range(k)],
            'scr': [zbool(r[f'scr{i}']) for i in range(k)]}
    for key in got:
        if key == 'tau':
            for i in range(k):
                if want['cau'][i] and got['cau'][i] and got['tau'][i] != want['tau'][i]:
                    bad.append({'kind': 'tau', 'station': i, 'real': float(got['tau'][i]), 'model': float(want['tau'][i])})
        elif got[key] != want[key]:
            bad.append({'kind': key, 'real': got[key], 'model': want[key]})
    return bad


def p2_plan_property(pc: dict, impl: Impl | None = None) -> list:
    """Safety properties of the REAL plan, checked independently of the model (and of assert_monotone):
    nothing relaxed, every base caution kept and not looser, candidates a permutation, scrutiny only added."""
    impl = impl or Impl.real()
    return plan_properties(pc, real_plan(impl, pc))


def plan_properties(pc: dict, out) -> list:
    if out is None:
        return []
    ss, item = pc['ss'], pc['item']
    base = pc['base']
    bad = []
    if (out['skip_check'] and not base.get('skip_check')) or (out['deny_without_visit'] and not base.get('deny_without_visit')):
        bad.append('relaxed: skip / refuse without visit')
    for sid, c in (base.get('caution') or {}).items():
        nc = (out.get('caution') or {}).get(sid)
        if nc is None or not nc['tau_h'] <= c['tau_h']:
            bad.append(f'caution at {sid} removed or loosened')
    order = out.get('order') or spec_order(ss, item, out['first_station'])
    if sorted(order) != sorted(ss.ids) or order[0] != out['first_station']:
        bad.append('candidates dropped / repeated')
    if not set(base.get('scrutiny') or []) <= set(out.get('scrutiny') or []):
        bad.append('scrutiny dropped')
    return bad


# ---- loop layer: the real stations.* against the model ---------------------------------------------------------------
def diff_loop_case(order: list, checked: set, k: int) -> list:
    from rescuemind.stations import next_candidate
    real = next_candidate(order, checked)
    oz = [z3.IntVal(x) for x in order]
    ck = [z3.BoolVal(t in checked) for t in range(k)]
    m = z3.simplify(first_unchecked(oz, ck, k)).as_long()
    want = None if m == -1 else m
    return [] if real == want else [{'kind': 'next_candidate', 'order': order, 'checked': sorted(checked), 'real': real, 'model': want}]


def simulate_loop(order, kind, k):
    """Plain-Python mission loop (the transcription, executable) for the BMC cross-check."""
    checked, deliv, visits, stopped, seq = set(), -1, 0, False, []
    for _ in range(k):
        cand = next((s for s in order if s not in checked), None)
        if cand is None:
            break
        checked.add(cand)
        visits += 1
        seq.append(cand)
        if kind[cand] == APPROVE:
            deliv = cand
            break
        if kind[cand] == STOP:
            stopped = True
            break
    return {'deliv': deliv, 'visits': visits, 'stopped': stopped, 'seq': seq, 'checked': checked}


def diff_loop_run(order, kind, k) -> list:
    sim = simulate_loop(order, kind, k)
    r = loop_run([z3.IntVal(x) for x in order], [z3.IntVal(x) for x in kind], k)
    got = {'deliv': z3.simplify(r['deliv']).as_long(), 'visits': z3.simplify(r['visits']).as_long(), 'stopped': zbool(z3.simplify(r['stopped'])),
           'checked': {t for t in range(k) if zbool(z3.simplify(r['checked'][t]))}}
    want = {key: sim[key] for key in got}
    return [] if got == want else [{'kind': 'loop', 'order': order, 'outcomes': kind, 'model': got, 'sim': want}]


def check_real_stations(order, visited, k) -> list:
    """stations.validate_visits on the real code agrees with the prefix property the model proves."""
    from rescuemind.stations import validate_visits
    try:
        validate_visits(order, visited)
        real_ok = True
    except ValueError:
        real_ok = False
    spec_ok = len(set(visited)) == len(visited) and list(visited) == list(order)[:len(visited)]
    return [] if real_ok == spec_ok else [{'kind': 'validate_visits', 'order': order, 'visited': visited, 'real': real_ok, 'spec': spec_ok}]


# ======================================================================================================================
# 6. hypothesis strategies shared by the CLI and the tests
# ======================================================================================================================
def strategies():
    from hypothesis import strategies as hs
    NAN, INF = float('nan'), float('inf')
    taus = hs.sampled_from([0.01, 0.005, 0.0099, 0.0001, 0.0499, 0.02, 0.03, 0.05, 0.049999999999999996, 0.07, 1e-9, 0.0025, 0.0075, 0.009999999999999998])
    score_pool = hs.one_of(
        hs.sampled_from([0.0, 1.0, 0.01, 0.005, 0.0099, 0.0001, 0.05, 0.049999999999999996, 0.0499, 0.02, 0.0075, 0.0025, 0.5, 0.009999999999999998,
                         0.010000000000000002, 0.00495, 0.004949999999999999, -0.0, 1e-300, 5e-324,
                         # invalid / hostile
                         NAN, INF, -INF, -0.1, 1.0000001, 2.0, 1e308, True, False, None, 'x', MISSING, [0.0], {'a': 1}, 1, 0]),
        hs.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        hs.floats(min_value=0.0, max_value=0.06, allow_nan=False))
    conf_pool = hs.one_of(hs.sampled_from([0.9, 0.5, 0.4999999999999999, 0.0, 1.0, 0.1, 0.51, NAN, INF, -INF, 'bad', None, True]),
                          hs.floats(min_value=0.0, max_value=1.0, allow_nan=False))
    thr_pool = hs.one_of(hs.just(0.05), hs.just(0.05), hs.just(0.05), hs.just(0.05), hs.sampled_from([0.5, MISSING, NAN, 0.050000000001, 0.05000000000001, 'x', None, True]))
    view = hs.fixed_dictionaries({
        'p': hs.tuples(score_pool, score_pool),
        'hz': hs.tuples(hs.booleans(), hs.booleans()),
        'thr': hs.tuples(thr_pool, thr_pool),
        'conf': hs.tuples(conf_pool, conf_pool),
        'supply': hs.tuples(hs.sampled_from(['water'] * 6 + ['medicine', 'other']), hs.sampled_from(['water'] * 6 + ['medicine', 'other']))})
    calm_p = hs.one_of(hs.sampled_from([0.0, 0.001, 0.004, 0.005, 0.0049, 0.0099, 0.01, 0.0101, 0.02, 0.0499, 0.05, 0.3, 1.0]),
                       hs.floats(min_value=0.0, max_value=0.06, allow_nan=False))
    calm_view = hs.fixed_dictionaries({
        'p': hs.tuples(calm_p, calm_p), 'hz': hs.tuples(hs.just(False), hs.just(False)), 'thr': hs.tuples(hs.just(0.05), hs.just(0.05)),
        'conf': hs.tuples(hs.just(0.9), hs.just(0.9)), 'supply': hs.tuples(hs.just('water'), hs.just('water'))})
    hostile_views = hs.fixed_dictionaries({w: view for w in VIEWS})
    calm_views = hs.fixed_dictionaries({w: calm_view for w in VIEWS})
    mixed_views = hs.fixed_dictionaries({w: hs.one_of(calm_view, calm_view, calm_view, calm_view, view) for w in VIEWS})

    @hs.composite
    def single_fault_views(draw):
        """All views calm except ONE field of ONE view/pass replaced by a hostile value: the case that separates a gate that
        fails closed from one that does not."""
        v = draw(calm_views)
        w = draw(hs.sampled_from(VIEWS))
        i = draw(hs.sampled_from([0, 1]))
        field = draw(hs.sampled_from(['p', 'p', 'p', 'hz', 'thr', 'conf']))
        new = {'p': score_pool, 'hz': hs.booleans(), 'thr': thr_pool, 'conf': conf_pool}[field]
        val = draw(new)
        pair = list(v[w][field])
        pair[i] = val
        v[w] = dict(v[w], **{field: tuple(pair)})
        return v
    # mostly calm frames (so approvals happen and the interesting boundaries are reached), some hostile, many mixed
    views = hs.one_of(calm_views, calm_views, mixed_views, single_fault_views(), single_fault_views(), single_fault_views(), hostile_views)
    param = hs.tuples(hs.booleans(), taus, hs.booleans())
    station_case = hs.fixed_dictionaries({'LA': hs.booleans(), 'AD': hs.booleans(), 'views': views, 'params': hs.lists(param, min_size=1, max_size=3)})

    kinds = hs.sampled_from(['small'] * 1)
    ss_kind = hs.sampled_from(['legacy', 'k2', 'k3', 'k4', 'k5'])

    @hs.composite
    def plan_case(draw, ss_kinds=ss_kind, max_items=6):
        sk = draw(ss_kinds)
        ss = station_set(sk)
        item = draw(hs.sampled_from(['water', 'medicine']))
        ids = list(ss.default_order(item))
        k = len(ids)
        cat = ids[0]
        hostile = draw(hs.sampled_from([False, False, False, True]))       # a quarter of the cases carry malformed items / thresholds
        legacy = ss.is_legacy()
        naive_base = draw(hs.sampled_from([False] * 6 + [True])) if hostile else False
        first = draw(hs.sampled_from([cat] * 5 + ids))
        if first == cat:
            order = list(ids)
        else:
            rest = draw(hs.permutations([s for s in ids if s != first]))
            order = [first] + list(rest)
        cau_ids = draw(hs.lists(hs.sampled_from(ids), unique=True, max_size=k))
        good_tau = [0.01] * 3 + [0.005, 0.0099, 0.0001, 0.0499, 0.0025, 0.0075, 0.009999999999999998, 0.02]
        bad_tau = [0.07, 0.0, 0.05, 0.0500001]
        caution = {s: {'tau_h': draw(hs.sampled_from(good_tau + (bad_tau if hostile else []))), 'first_side': None, 'seen_in': 'm'} for s in cau_ids}
        scr_ids = [s for s in draw(hs.lists(hs.sampled_from(ids), unique=True, max_size=2)) if s in caution and (hostile or caution[s]['tau_h'] <= 0.01)]
        base = {'mode': 'verified', 'catalog_station': cat, 'first_station': first, 'n_records': 0, 'caution': caution,
                'skip_check': bool(naive_base and draw(hs.booleans())), 'deny_without_visit': bool(naive_base and draw(hs.booleans())), 'rationale': []}
        if scr_ids:
            base['scrutiny'] = sorted(scr_ids)
        if not legacy:
            base['order'] = order
        elif first != cat:
            base['first_station'] = first
        item_station = hs.sampled_from(ids * 6 + ([None, 'nowhere', 'water ', 7] if hostile else []))
        valid_kind_item = hs.fixed_dictionaries({'source': hs.sampled_from(['memory', 'peer', 'inventory', 'operator']),
                                                 'kind': hs.sampled_from(['location', 'hazard', 'safe', 'skip']),
                                                 'station': item_station, 'text': hs.text(max_size=5)})
        good_item = hs.one_of(
            hs.fixed_dictionaries({'source': hs.sampled_from(['memory', 'peer', 'inventory', 'operator']), 'kind': hs.sampled_from(['location', 'hazard']),
                                   'station': hs.sampled_from(ids), 'text': hs.just('')}),
            hs.fixed_dictionaries({'source': hs.sampled_from(['memory', 'peer', 'inventory', 'operator']), 'kind': hs.sampled_from(['safe', 'skip']),
                                   'station': hs.sampled_from(ids + [None]), 'text': hs.just('')}))
        hostile_item = hs.one_of(valid_kind_item, hs.sampled_from([{'kind': 'teleport', 'source': 'peer'}, None, 5, 'skip', [], {'kind': ['skip'], 'source': 'peer'}, {}]))
        items = draw(hs.lists(hostile_item if hostile else good_item, max_size=max_items))
        tc = draw(hs.sampled_from([0.01] * 14 + [0.005, 0.0099, 0.0001, 0.009999999999999998] + ([0.02, 0.05, 0.04, 0.0, -1.0, 1e-9, NAN, INF, -INF, 0.0100000001] if hostile else [])))
        S = draw(hs.booleans())
        return {'ss': ss, 'item': item, 'base': base, 'items': items, 'tc': tc, 'S': S, 'naive_base': naive_base}

    @hs.composite
    def p2_pair(draw):
        """A plan case whose planned parameters at a station feed a station case (the real plan -> the real approval)."""
        pc = draw(plan_case(ss_kinds=hs.sampled_from(['legacy', 'k2', 'k3', 'k4']), max_items=5))
        sc = draw(station_case)
        return pc, sc

    return {'station_case': station_case, 'plan_case': plan_case(), 'p2_pair': p2_pair(), 'taus': taus}


def loop_cases(n: int, seed: int = 23):
    """Random mission-loop inputs: k in 2..6, a permutation (or a prefix-violating visit list), checked sets, outcome classes."""
    rng = random.Random(seed)
    for _ in range(n):
        k = rng.randint(2, 6)
        order = list(range(k))
        rng.shuffle(order)
        checked = {t for t in range(k) if rng.random() < 0.4}
        kinds = [rng.choice([APPROVE, CONT, CONT, STOP]) for _ in range(k)]
        visited = list(order[:rng.randint(0, k)])
        if rng.random() < 0.4 and len(visited) > 1:
            rng.shuffle(visited)
        if rng.random() < 0.2 and visited:
            visited.append(rng.choice(visited))
        yield k, order, checked, kinds, visited


def check_plan_order(order, k) -> list:
    """stations.plan_order: a plan 'order' that is a permutation of the station set is followed; one that dropped a candidate is rejected."""
    from rescuemind.stations import plan_order
    ss = station_set(f'k{k}') if k > 2 else station_set('k2')
    ids = list(ss.default_order('water'))
    perm = [ids[i] for i in order]
    bad = []
    got = plan_order({'order': perm}, ss, 'water')
    if got != perm:
        bad.append({'kind': 'plan_order follows', 'order': perm, 'got': got})
    if k > 2:
        try:
            plan_order({'order': perm[:-1] + [perm[0]]}, ss, 'water')
            bad.append({'kind': 'plan_order accepted a dropped candidate', 'order': perm})
        except ValueError:
            pass
    return bad


def run_loop_differential(n: int) -> dict:
    bad, cnt = [], 0
    for k, order, checked, kinds, visited in loop_cases(n):
        cnt += 1
        bad += diff_loop_case(order, checked, k) + diff_loop_run(order, kinds, k) + check_real_stations(order, visited, k)
        bad += check_plan_order(order, k)
    assert not bad, bad[:3]
    return {'n': cnt, 'disagreements': 0}


def run_differential(kind: str, max_examples: int) -> dict:
    """Run one differential family under hypothesis with `max_examples` draws; returns counts (raises on a disagreement).
    families: station (real approval predicate vs z3 model, plus the audit), plan (real advice.plan vs z3 plan model),
    p2 / p2_noassert (Proposition 2 on the real code, end to end, without any model; _noassert = assert_monotone disabled)."""
    from hypothesis import given, settings, HealthCheck, Phase
    S = strategies()
    count = {'n': 0, 'approved': 0, 'plan_defined': 0, 'plan_raised': 0, 'reordered': 0, 'cautioned': 0, 'scrutinised': 0}
    impl = Impl.real()
    plan_impl = plan_noassert() if kind == 'p2_noassert' else impl
    st = {'station': S['station_case'], 'plan': S['plan_case'], 'p2': S['p2_pair'], 'p2_noassert': S['p2_pair']}[kind]

    @settings(max_examples=max_examples, deadline=None, derandomize=True, database=None, print_blob=True,
              suppress_health_check=list(HealthCheck), phases=[Phase.generate])
    @given(st)
    def run(case):
        count['n'] += 1
        if kind == 'station':
            bad = diff_station_case(case, impl)
            ca = dict(case)
            ca['T'] = trigger_from_case(ca)
            count['approved'] += int(real_approve(impl, ca, *case['params'][0]))
        elif kind == 'plan':
            bad = diff_plan_case(case, impl)
            out = real_plan(impl, case)
            count['plan_defined' if out is not None else 'plan_raised'] += 1
            if out is not None:
                count['reordered'] += int(out['first_station'] != case['base']['first_station'])
                count['cautioned'] += int(len(out.get('caution') or {}) > len(case['base'].get('caution') or {}))
                count['scrutinised'] += int(bool(out.get('scrutiny')) and not case['base'].get('scrutiny'))
            bad += [{'kind': 'property', 'what': w} for w in p2_plan_property(case, impl) if not case['naive_base']]
        else:
            pc, sc = case
            bad = p2_end_to_end(pc, sc, impl, plan_impl)
            out = real_plan(plan_impl, pc)
            count['plan_defined' if out is not None else 'plan_raised'] += 1
            if out is not None and not pc['naive_base']:
                ca = dict(sc, T=trigger_from_case(sc))
                count['approved'] += int(real_approve(impl, ca, False, None, False))
                count['cautioned'] += int(any(station_params(out, sid)[0] for sid in pc['ss'].ids))
                count['scrutinised'] += int(bool(out.get('scrutiny')))
        assert not bad, bad

    run()
    return count


# ======================================================================================================================
# 7. code mutants
# ======================================================================================================================
def load_variant(module: str, edits=(), patch=None):
    """A private copy of rescuemind/<module>.py with source edits (each anchor must occur exactly once)."""
    src = (ROOT / 'rescuemind' / f'{module}.py').read_text(encoding='utf8')
    for old, new in edits:
        assert src.count(old) == 1, f'mutation anchor not unique ({src.count(old)}x): {old!r}'
        src = src.replace(old, new)
    mod = types.ModuleType(f'rescuemind._{module}_mutant')
    mod.__package__ = 'rescuemind'
    mod.__file__ = f'<mutant {module}.py>'
    exec(compile(src, mod.__file__, 'exec', dont_inherit=True), mod.__dict__)
    for k_, v in (patch or {}).items():
        setattr(mod, k_, v)
    return mod


def _noop(*_a, **_k):
    return None


def code_mutants():
    """name -> dict(kind='plan'|'gate', impl=Impl, model_flag=..., against=...).  Plan mutants run with the in-plan
    assert_monotone DISABLED so that the model / property harness (not the runtime assertion) has to catch them."""
    real = Impl.real()
    out = {}

    def plan_mut(name, edits, flag, desc):
        mod = load_variant('advice', edits)
        mod.assert_monotone = _noop
        out[name] = {'kind': 'plan', 'impl': Impl(**{**real.__dict__, 'plan': mod.plan}), 'flag': flag, 'desc': desc}

    plan_mut('advice_loosens_tau_h',
             [("tau = min(caution_tau_h, prev) if prev is not None else caution_tau_h\n                out['caution'][st] =",
               "tau = caution_tau_h\n                out['caution'][st] ="),
             ("tau = min(caution_tau_h, prev['tau_h']) if prev.get('tau_h') is not None else caution_tau_h", "tau = caution_tau_h")], 'advice_loosens_tau_h', PLAN_MUTANTS['advice_loosens_tau_h'])
    plan_mut('caution_max_not_min', [("tau = min(caution_tau_h, prev) if prev is not None else caution_tau_h\n                out['caution'][st] =",
                                       "tau = max(caution_tau_h, prev) if prev is not None else caution_tau_h\n                out['caution'][st] ="),
                                      ("tau = min(caution_tau_h, prev['tau_h']) if prev.get('tau_h') is not None else caution_tau_h",
                                       "tau = max(caution_tau_h, prev['tau_h']) if prev.get('tau_h') is not None else caution_tau_h")],
             'caution_max_not_min', PLAN_MUTANTS['caution_max_not_min'])
    plan_mut('advice_skips_check', [("            if follow:\n                out['skip_check'] = True", "            if True:\n                out['skip_check'] = True")],
             'advice_skips_check', PLAN_MUTANTS['advice_skips_check'])
    plan_mut('advice_marks_verified', [("                rec['applied'].append(dict(a, effect='reorder', **({'scrutiny': True} if scrutiny else {})))",
                                         "                out['skip_check'] = True\n                rec['applied'].append(dict(a, effect='reorder', **({'scrutiny': True} if scrutiny else {})))")],
             'advice_marks_verified', PLAN_MUTANTS['advice_marks_verified'])
    plan_mut('advice_refuses_unseen', [("            if follow and st == out['first_station']:", "            if st == out['first_station']:")],
             'advice_refuses_unseen', PLAN_MUTANTS['advice_refuses_unseen'])
    # the measured baseline of an advice-following agent: mode 'naive' (real code, no mutation of the source)
    out['mode_naive'] = {'kind': 'plan', 'flag': 'advice_skips_check', 'desc': "advice-following baseline (advice.plan mode='naive')",
                         'impl': Impl(**{**real.__dict__, 'plan': (lambda item, items, mode, **kw: real.plan(item, items, 'naive', **kw))})}
    from unittest import mock
    from rescuemind.stations import StationSet
    _orig_order = StationSet.order
    out['advice_drops_candidate'] = {'kind': 'plan', 'flag': 'advice_drops_candidate', 'desc': PLAN_MUTANTS['advice_drops_candidate'], 'impl': plan_noassert(),
                                     'ctx': lambda: mock.patch.object(StationSet, 'order', lambda self, item, first=None: _orig_order(self, item, first)[:-1] if first else _orig_order(self, item, first))}

    def gate_mut(name, mm_edits=(), lv_patch=None, flag=None, against='v36', desc=''):
        mm = load_variant('mission_memory', mm_edits)
        kw = dict(real.__dict__)
        kw.update(apply_memory_caution=mm.apply_memory_caution, peek_hazard=mm.peek_hazard, scores_valid=mm.scores_valid)
        kw['require_valid_scores'] = (lambda call, _sv=mm.scores_valid: None if _sv(call) else (_ for _ in ()).throw(real.LocalInferenceError('invalid score')))
        kw.update(lv_patch or {})
        out[name] = {'kind': 'gate', 'impl': Impl(**kw), 'flag': flag, 'against': against, 'desc': desc}

    gate_mut('caution_boundary_le', [("    if p < tau_h:\n        return decision", "    if p <= tau_h:\n        return decision")], flag='caution_boundary_le', against='base',
             desc=STATION_MUTANTS['caution_boundary_le'])
    gate_mut('peek_ignores_caution', [("    return tau_h is not None and max(_hazard_prob(first), _hazard_prob(second)) >= tau_h", "    return False")], flag='peek_ignores_caution',
             against='base', desc=STATION_MUTANTS['peek_ignores_caution'])
    gate_mut('invalid_score_clear',
             [("    return float(call['scores']['hazard_prob']) if scores_valid(call) else 1.0", "    return float(call['scores']['hazard_prob']) if scores_valid(call) else 0.0"),
              ("    if not (scores_valid(first) and scores_valid(second)):\n        return True\n    return tau_h", "    return tau_h"),
              ("    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0.0 <= v <= 1.0",
               "    return True")],
             flag='invalid_score_clear', against='v36', desc=STATION_MUTANTS['invalid_score_clear'])
    gate_mut('sides_ignored', lv_patch={'combine_with_look_around': lambda front_decision, peeks: front_decision}, flag='sides_ignored', against='v36',
             desc=STATION_MUTANTS['sides_ignored'])
    return out




# ---------------------------------------------------------------------------------------------------------------------
# necessity (supplement S10, "Necessity"): a relaxing interface has a generator law and a clairvoyant advisor above eps_any
# ---------------------------------------------------------------------------------------------------------------------
def necessity(rec: list | None = None, k: int = 3, n: int = 2) -> list:
    """Two-world law: with probability q the world has a must-refuse station s* that produces the frame o*; with probability 1-q a
    world on which the rest of the budget e0 is spent (q = 1/2 > e0 = 1/10).  The advisor is clairvoyant: it sends a* exactly in
    the first world.  Unsafe rate = q [advice approves o*] + (1-q) e0;  eps_any = q [the check ALONE approves o*] + (1-q) e0.
    Claim "unsafe <= eps_any": unsat for the tighten-only plan (the only-if half is the P2a proof), sat for every relaxing
    interface, and the model is the counterexample (a*, o*, s*) of the necessity argument."""
    q, e0 = Fraction(1, 2), Fraction(1, 10)
    out = []
    cases = [('tighten-only (the code)', frozenset(), frozenset())]
    cases += [(f'relaxing: {PLAN_MUTANTS[m]}', frozenset([m]), frozenset()) for m in ('advice_skips_check', 'advice_marks_verified')]
    cases += [(f'relaxing: {STATION_MUTANTS[m]}', frozenset(), frozenset([m])) for m in ('sides_ignored', 'invalid_score_clear')]
    for name, pm, sm in cases:
        b = PlanState.fresh('b', k)
        tc, S = z3.Real('tc'), z3.Bool('S')
        its = [(z3.Int(f'kind{i}'), z3.Int(f'st{i}')) for i in range(n)]
        cur, assum = b, [wf_base(b, k), z3.Not(b.skip), z3.Not(b.deny), tc > 0, tc <= rv(TAU_CAUTION)]
        for ki, si in its:
            assum.append(item_valid(ki, si, k))
            cur = plan_step(cur, ki, si, tc, z3.BoolVal(False), S, k, pm)
        sidx = z3.Int('sstar')
        o = StationVars()
        assum += [sidx >= 0, sidx < k, o.domain()] + ([z3.Not(o.bad[w]) for w in VIEWS] if sm else [])
        sel = lambda arr: select(arr, sidx, k, z3.BoolVal(False))
        selr = lambda arr: select(arr, sidx, k, z3.RealVal(0))
        A_with = station_pred_plan(o, cur.skip, cur.deny, sidx == cur.first, sel(cur.cau), selr(cur.tau), sel(cur.scr), sm)
        A_0, _ = station_pred(o, z3.BoolVal(False), z3.RealVal(0), z3.BoolVal(False))
        unsafe = rv(q) * z3.If(A_with, 1, 0) + rv(1 - q) * rv(e0)
        eps_any = rv(q) * z3.If(A_0, 1, 0) + rv(1 - q) * rv(e0)
        res = prove(f'NECESSITY {name}: unsafe <= eps_any under the two-world law', unsafe <= eps_any, assum)
        d = {'name': res['name'], 'interface': name, 'result': res['result'], 'proved': res['result'] == ('unsat' if not (pm or sm) else 'sat'),
             'seconds': res['seconds'], 'q': str(q), 'e0': str(e0)}
        if res['result'] == 'sat':
            m = res['model']
            d['counterexample'] = {'advice': [{'kind': ['location', 'hazard', 'safe', 'skip'][mval(m, ki)], 'station': (None if mval(m, si) < 0 else mval(m, si))} for ki, si in its],
                                   'station_s_star': mval(m, sidx), 'LA': mval(m, o.LA),
                                   'frame_o_star': {w: {'scene_hazard': [mval(m, o.hz[(w, i)]) for i in (1, 2)], 'score_valid': [mval(m, o.val[(w, i)]) for i in (1, 2)],
                                                        'p': [mval(m, o.p[(w, i)]) for i in (1, 2)]} for w in VIEWS},
                                   'check_alone_approves_o_star': False, 'unsafe_rate': float(q + (1 - q) * e0), 'eps_any': float((1 - q) * e0)}
        out.append(d)
        if rec is not None:
            rec.append({k_: v_ for k_, v_ in d.items() if k_ != 'counterexample'})
    return out

# ---------------------------------------------------------------------------------------------------------------------
# non-vacuity: the assumptions are satisfiable and the interesting cases are reachable (so `unsat` is not an accident)
# ---------------------------------------------------------------------------------------------------------------------
def nonvacuity(rec: list) -> list:
    out = []

    def sat(name, *conds, **meta):
        s_ = z3.Solver()
        s_.set('timeout', 60_000)
        s_.add(*conds)
        t0 = time.perf_counter()
        r = s_.check()
        d = {'name': 'NONVACUITY ' + name, 'result': str(r), 'proved': r == z3.sat, 'seconds': round(time.perf_counter() - t0, 4), **meta}
        rec.append(d)
        out.append(d)

    k = 4
    b, s0 = PlanState.fresh('b', k), PlanState.fresh('s', k)
    tc, S, kind, st = z3.Real('tc'), z3.Bool('S'), z3.Int('kind'), z3.Int('st')
    tcnan = z3.BoolVal(False)
    base_ok = [wf_base(b, k), z3.tc if False else tc > 0, tc <= rv(TAU_CAUTION)]
    s1 = plan_step(s0, kind, st, tc, tcnan, S, k)
    sat('plan: invariant state, valid item', wf_base(b, k), inv_safety(b, s0, tc, k), item_valid(kind, st, k), tc > 0, tc <= rv(TAU_CAUTION), k=k)
    sat('plan: a location item reorders (first changes)', wf_base(b, k), inv_safety(b, s0, tc, k), item_valid(kind, st, k), s1.first != s0.first, k=k)
    sat('plan: a hazard item tightens an existing caution strictly', wf_base(b, k), inv_safety(b, s0, tc, k), item_valid(kind, st, k), tc > 0, tc <= rv(TAU_CAUTION),
        z3.Or(*[z3.And(s0.cau[t], s1.tau[t] < s0.tau[t]) for t in range(k)]), k=k)
    sat('plan: scrutiny adds a scrutinised station', wf_base(b, k), inv_safety(b, s0, tc, k), item_valid(kind, st, k), S,
        z3.Or(*[z3.And(z3.Not(s0.scr[t]), s1.scr[t]) for t in range(k)]), k=k)
    o = StationVars()
    ha, ta, sa = z3.Bool('hasc_a'), z3.Real('tau_a'), z3.Bool('scr_a')
    A_a, parts = station_pred(o, ha, ta, sa)
    A_0, _ = station_pred(o, z3.BoolVal(False), z3.RealVal(0), z3.BoolVal(False))
    sat('station: the check can approve', o.domain(), A_a)
    sat('station: advice really can cost an approval (A_0 and not A_a)', o.domain(), z3.Implies(ha, ta > 0), ta < rv(TAU_STD), A_0, z3.Not(A_a), ha)
    sat('station: scrutiny extra views are taken and the check still approves', o.domain(), A_a, sa, parts['extra_taken'], o.LA)
    sat('station: scrutiny costs an approval through an extra view only', o.domain(), A_0, z3.Not(A_a), sa, z3.Not(ha))
    kk = 4
    order = [z3.Int(f'O{i}') for i in range(kk)]
    kinds = [z3.Int(f'kind{t}') for t in range(kk)]
    r = loop_run(order, kinds, kk)
    base = [is_perm(order, kk), *[z3.And(x >= 0, x <= 2) for x in kinds]]
    sat('loop: a delivery after two recovery hops', *base, r['deliv'] >= 0, r['visits'] == 3)
    sat('loop: exhaustion (all candidates checked, no delivery)', *base, r['deliv'] < 0, r['visits'] == kk, z3.Not(r['stopped']))
    j = z3.Int('j')
    r0 = loop_run([z3.IntVal(i) for i in range(kk)], kinds, kk)
    r1 = loop_run(moved(j, kk), kinds, kk)
    sat('loop: the reorder bound is tight (one extra visit occurs)', z3.And(j >= 0, j < kk), *base[1:], r1['visits'] == r0['visits'] + 1, r0['deliv'] >= 0)
    return out


# ---------------------------------------------------------------------------------------------------------------------
# end-to-end property of the REAL code (no model), and the code-mutant runs
# ---------------------------------------------------------------------------------------------------------------------
def station_params(plan: dict, sid: str):
    c = (plan.get('caution') or {}).get(sid)
    return (c is not None, float(c['tau_h']) if c is not None else None, sid in (plan.get('scrutiny') or []))


def plan_noassert() -> Impl:
    """The real advice.plan with assert_monotone disabled: shows the planning RULE (not the runtime assertion) is monotone."""
    mod = load_variant('advice', [])
    mod.assert_monotone = _noop
    return Impl(**{**Impl.real().__dict__, 'plan': mod.plan})


def p2_end_to_end(pc: dict, sc: dict, impl: Impl | None = None, plan_impl: Impl | None = None) -> list:
    """Real advice.plan -> real approval predicate at every station: approve with advice => approve under the base plan
    => approve under the plain v3.6 rule.  Skipped for naive bases (Prop. 2 is for a baseline or verified-memory base)."""
    impl = impl or Impl.real()
    plan_impl = plan_impl or impl
    if pc['naive_base']:
        return []
    out = real_plan(plan_impl, pc)
    if out is None:
        return []
    bad = []
    if out['skip_check'] or out['deny_without_visit']:
        return ['plan skips / refuses without visit']
    from rescuemind.advice import skip_source, denial_source
    if skip_source(out) is not None or denial_source(out) is not None:       # the node's naive-baseline switches (skip the check / refuse unseen)
        return ['the mission node would take the naive path (skip_source / denial_source)']
    for sid in pc['ss'].ids:
        case = dict(sc, params=[(False, None, False), station_params(pc['base'], sid), station_params(out, sid)])
        bad += [f'{sid}: {w}' for w in p2_property_case(case, impl)]
    return bad


def credit_case(pc: dict) -> list:
    """I-24: advice.plan on the items a credit ledger admits (advice_credit.plan_with_credit) keeps every plan property, for ledgers
    from empty to full (the credit layer only removes items, so it is a sub-list of the advice the invariant already covers)."""
    from rescuemind import advice_credit as ac
    if pc['naive_base'] or not isinstance(pc['items'], list):
        return []
    bad = []
    for c in (0.0, 1.0, 2.0):
        try:
            out = ac.plan_with_credit(ac.new_ledger(c_loc=c, c_haz=c), pc['item'], pc['items'], 'monotone', copy.deepcopy(pc['base']),
                                      caution_tau_h=pc['tc'], stations=pc['ss'], scrutiny=pc['S'])
        except Exception as e:                        # noqa: BLE001
            if type(e).__name__ in ('AdviceError', 'CreditError'):
                continue
            raise
        bad += [f'credit {c}: {w}' for w in plan_properties(pc, out)]
        bad += [f'credit {c}: relaxed' for _ in [0] if out['skip_check'] or out['deny_without_visit']]
    return bad


def hypo_search(fn, strategy, max_examples: int, seed_note: str = '') -> dict:
    """Run `fn(case) -> list of problems` under hypothesis; report whether a problem was found, after how many examples, and the
    shrunk falsifying example."""
    from hypothesis import given, settings, HealthCheck, Phase
    n = {'n': 0}
    found: dict = {}

    @settings(max_examples=max_examples, deadline=None, derandomize=True, database=None, suppress_health_check=list(HealthCheck),
              phases=[Phase.generate, Phase.shrink])
    @given(strategy)
    def run(case):
        n['n'] += 1
        bad = fn(case)
        if bad:
            found['bad'], found['case'], found['at'] = bad, case, n['n']
        assert not bad

    try:
        run()
        return {'detected': False, 'examples': n['n']}
    except AssertionError:
        return {'detected': True, 'examples_until_first': found.get('at'), 'examples_total': n['n'], 'problem': str(found.get('bad'))[:300],
                'case': _compact(found.get('case'))}


def _compact(c, depth=0):
    if isinstance(c, dict):
        return {k_: _compact(v, depth + 1) for k_, v in c.items() if k_ not in ('ss',)}
    if isinstance(c, (list, tuple)):
        return [_compact(v, depth + 1) for v in c]
    if isinstance(c, float) and not math.isfinite(c):
        return str(c)
    if c is MISSING:
        return '<missing>'
    return c


def case_from_plan_cex(cex: dict, k: int):
    ss = station_set(f'k{k}')
    item = 'water'
    ids = list(ss.default_order(item))
    base = {'mode': 'verified', 'catalog_station': ids[0], 'first_station': ids[cex['base']['first']], 'n_records': 0, 'rationale': [], 'skip_check': False,
            'deny_without_visit': False, 'order': [ids[i] for i in cex['base']['order']],
            'caution': {ids[int(t)]: {'tau_h': v['float'], 'first_side': None, 'seen_in': 'm'} for t, v in cex['base']['caution'].items()}}
    if cex['base']['scrutiny']:
        base['scrutiny'] = [ids[i] for i in cex['base']['scrutiny']]
    items = [{'source': 'peer', 'kind': it['kind'], 'station': (None if it['station'] is None else ids[it['station']]), 'text': ''} for it in cex['items']]
    return {'ss': ss, 'item': item, 'base': base, 'items': items, 'tc': cex['tc']['float'], 'S': cex['scrutiny'], 'naive_base': False}


def case_from_station_cex(cex: dict) -> dict:
    def fl(x):
        return x['float'] if isinstance(x, dict) else x
    views = {}
    for w in VIEWS:
        v = cex['views'][w]
        views[w] = {'p': tuple((fl(v['p'][i]) if v['score_valid'][i] else float('nan')) for i in (0, 1)), 'hz': tuple(v['scene_hazard']), 'thr': (0.05, 0.05),
                    'conf': (0.9, 0.9), 'supply': ('water', 'water')}
    f = views['F']
    f['supply'] = tuple('water' if ok else 'medicine' for ok in cex['supply_ok'])
    f['conf'] = tuple(0.1 if lo else 0.9 for lo in cex['low_conf'])
    pp = cex['plan_params']
    return {'LA': cex['LA'], 'AD': cex['AD'], 'views': views,
            'params': [(False, None, False), (pp['base_has_caution'], fl(pp['base_tau']) if pp['base_has_caution'] else None, pp['base_scrutiny']),
                       (pp['has_caution'], fl(pp['tau']) if pp['has_caution'] else None, pp['scrutiny'])]}


def run_code_mutants(max_examples: int = 1500) -> list:
    """For each code mutant: (1) the z3 counterexample from the mutated model, (2) its replay on the mutated code and on the real code,
    (3) detection by the differential harness (code vs spec model) and by the model-free property tests."""
    S = strategies()
    results = []
    real = Impl.real()
    for name, m in code_mutants().items():
        r = {'mutant': name, 'description': m['desc'], 'kind': m['kind']}
        ctx = m.get('ctx')
        import contextlib
        cm = ctx() if ctx else contextlib.nullcontext()
        with cm:
            if m['kind'] == 'plan':
                cx = plan_mutant_cex(m['flag'])
                r['z3_model_mutant'] = cx['z3']
                if cx['z3'] == 'sat':
                    r['counterexample'] = cx['counterexample']
                    pc = case_from_plan_cex(cx['counterexample'], 3)
                    r['replay_mutant_code_violates'] = bool(p2_plan_property(pc, m['impl']))
                    r['replay_mutant_violations'] = p2_plan_property(pc, m['impl'])
                else:
                    r['replay_mutant_code_violates'] = None
                flag = m['flag']
                r['detect_differential'] = hypo_search(lambda pc: diff_plan_case(pc, m['impl']), S['plan_case'], max_examples)
                r['detect_property'] = hypo_search(lambda pc: [] if pc['naive_base'] else p2_plan_property(pc, m['impl']), S['plan_case'], max_examples)
            else:
                cx = station_mutant_cex(m['flag'], m['against'])
                r['z3_model_mutant'] = cx['z3']
                if cx['z3'] == 'sat':
                    r['counterexample'] = cx['counterexample']
                    case = case_from_station_cex(cx['counterexample'])
                    # replay: the mutated code approves what the specification model refuses; the real code agrees with the model
                    case['T'] = trigger_from_case(case)
                    hasc, tau, scr = case['params'][2]
                    r['replay_mutant_code_approves'] = real_approve(m['impl'], case, hasc, tau, scr)
                    r['replay_real_code_approves'] = real_approve(real, case, hasc, tau, scr)
                    r['replay_spec_model_approves'] = model_approve(case, hasc, tau, scr)
                r['detect_differential'] = hypo_search(lambda sc: diff_station_case(sc, m['impl'], with_audit=False), S['station_case'], max_examples)
        results.append(r)
    return results


# ======================================================================================================================
# 8. driver
# ======================================================================================================================
def run_all(quick: bool = False, diff_n: int = 1500, mutant_n: int = 1500, loop_n: int = 1500, with_link: bool = True) -> dict:
    t_all = time.perf_counter()
    rec: list = []
    ks = (2, 3, 4) if quick else (2, 3, 4, 5, 6, 8)
    for k in ks:
        proofs_plan(k, rec)
    proofs_station(rec)
    for k, n in ((2, 3), (3, 3), (4, 3)) if not quick else ((3, 2),):
        proofs_station_plan_linked(k, n, rec)
    for k in ((2, 3, 4, 5, 6) if not quick else (3, 4)):
        proofs_loop(k, rec)
        proofs_hazard_continue(k, rec)
    nonvacuity(rec)
    nec = necessity(rec)
    mutants = {'plan': [], 'station': [], 'loop': []}
    for name in PLAN_MUTANTS:
        r = plan_mutant_cex(name)
        r.pop('model', None)
        mutants['plan'].append(r)
    for name, against in (('caution_boundary_le', 'base'), ('peek_ignores_caution', 'base'), ('invalid_score_clear', 'v36'), ('sides_ignored', 'v36'),
                          ('scrutiny_extra_views_skipped', 'spec')):
        r = station_mutant_cex(name, against)
        for key in ('model', 'vars'):
            r.pop(key, None)
        mutants['station'].append(r)
    for name in LOOP_MUTANTS:
        mutants['loop'].append(loop_mutant_cex(name))
    for name in HC_MUTANTS:
        mutants['loop'].append(hc_mutant_cex(name))
    res = {'proofs': rec, 'mutants_model': mutants, 'necessity': nec}
    if with_link:
        diff = {}
        for fam in ('plan', 'station', 'p2', 'p2_noassert'):
            t0 = time.perf_counter()
            diff[fam] = run_differential(fam, diff_n)
            diff[fam]['disagreements'] = 0
            diff[fam]['seconds'] = round(time.perf_counter() - t0, 1)
        t0 = time.perf_counter()
        r = hypo_search(credit_case, strategies()['plan_case'], diff_n)
        assert not r['detected'], r
        diff['credit'] = {'n': r['examples'], 'disagreements': 0, 'seconds': round(time.perf_counter() - t0, 1)}
        t0 = time.perf_counter()
        diff['loop'] = run_loop_differential(loop_n)
        diff['loop']['seconds'] = round(time.perf_counter() - t0, 1)
        res['differential'] = diff
        res['differential_total_cases'] = sum(v['n'] for v in diff.values())
        t0 = time.perf_counter()
        res['code_mutants'] = run_code_mutants(mutant_n)
        res['code_mutants_seconds'] = round(time.perf_counter() - t0, 1)
    res['seconds_total'] = round(time.perf_counter() - t_all, 3)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(ROOT / 'experiments' / 'results' / 'smt_advice_proof.json'))
    ap.add_argument('--quick', action='store_true')
    ap.add_argument('--diff', type=int, default=1500, help='hypothesis examples per differential family')
    ap.add_argument('--no-link', action='store_true', help='proofs only (skip the differential runs and the code mutants)')
    a = ap.parse_args()
    res = run_all(a.quick, diff_n=a.diff, mutant_n=a.diff, loop_n=a.diff, with_link=not a.no_link)
    res['env'] = {'z3': z3.get_version_string(), 'python': platform.python_version(), 'platform': platform.platform()}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=1, default=str, ensure_ascii=False) + '\n', encoding='utf8')
    n_ok = sum(1 for p in res['proofs'] if p['proved'])
    if 'differential' in res:
        print('differential:', {k_: v_['n'] for k_, v_ in res['differential'].items()}, 'total', res['differential_total_cases'])
        print('code mutants:', [(m['mutant'], m.get('z3_model_mutant'), m['detect_differential']['detected']) for m in res['code_mutants']])
    print(f"{n_ok}/{len(res['proofs'])} checks as expected; mutants (model): "
          + ', '.join(f"{k}={sum(1 for m in v if m['z3'] == 'sat')}/{len(v)}" for k, v in res['mutants_model'].items()) + f"; {res['seconds_total']} s")
    return 0 if n_ok == len(res['proofs']) else 1


if __name__ == '__main__':
    sys.exit(main())
