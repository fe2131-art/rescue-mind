"""I-23: link between the z3 model (scripts/verify_advice_smt.py) and the code, and the mutation checks.

The proofs say things about the MODEL.  These tests are what ties the model to the REAL functions:

  * proofs        every z3 check of the script returns the expected result (unsat for the properties, sat for the
                  non-vacuity checks and for the mutants), for a reduced set of k;
  * differential  hypothesis draws (boundary values, NaN / inf / bool / None / out-of-range scores, malformed and adversarial
                  advice, naive base plans, hostile caution thresholds) are evaluated by the real Python functions and by
                  the z3 model on the same concrete values; they must agree exactly:
                    plan      advice.plan(mode='monotone') incl. its AdviceError          <-> z3 plan model
                    station   require_valid_scores . check_hazard_threshold . local_decision . apply_memory_caution .
                              peek_hazard . combine_with_look_around . suspicion (assembled as the mission node does)
                              <-> z3 approval predicate; the interlock's recomputation (audit_local_checkpoint) must not
                              approve what the model refuses
                    loop      stations.next_candidate / validate_visits / plan_order <-> z3 loop model, z3 loop <-> executable loop
  * property      Proposition 2 on the real code, with no model: approve with advice => approve under the base plan =>
                  approve under the v3.6 rule, also with the plan assertion (assert_monotone) switched off;
  * mutants       representative bugs in private copies of the code are killed (z3 counterexample for the mutated model,
                  the counterexample replayed on the mutated code, the differential harness finds a disagreement);
  * tripwire      the mission node still composes these functions (the node itself needs ROS and is not executed).

Examples per family: I23_EXAMPLES (default 600).  Pure Python + z3 + hypothesis; no ROS / GPU / docker.
"""
import ast
import importlib.util
import math
import os
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import z3  # noqa: F401
    import hypothesis  # noqa: F401
    HAVE = True
except ImportError:                                  # pragma: no cover
    HAVE = False

N = int(os.environ.get('I23_EXAMPLES', '600'))


def _load():
    spec = importlib.util.spec_from_file_location('verify_advice_smt', ROOT / 'scripts' / 'verify_advice_smt.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules['verify_advice_smt'] = mod
    spec.loader.exec_module(mod)
    return mod


V = _load() if HAVE else None


@unittest.skipUnless(HAVE, 'z3-solver and hypothesis are required (pip install --user z3-solver hypothesis)')
class Proofs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = V.run_all(quick=True, with_link=False)

    def test_every_check_as_expected(self):
        bad = [p['name'] for p in self.res['proofs'] if not p['proved']]
        self.assertEqual(bad, [])
        self.assertGreaterEqual(len(self.res['proofs']), 60)

    def test_properties_are_unsat_and_nonvacuity_sat(self):
        for p in self.res['proofs']:
            want = 'sat' if p['name'].startswith('NONVACUITY') or p['name'].startswith('NECESSITY relaxing') else 'unsat'
            self.assertEqual(p['result'], want, p['name'])

    def test_necessity_counterexamples(self):
        nec = self.res['necessity']
        self.assertEqual(nec[0]['result'], 'unsat')                      # tighten-only: the bound holds in the two-world law
        for d in nec[1:]:                                                # every relaxing interface: unsafe > eps_any, with (a*, o*, s*)
            self.assertEqual(d['result'], 'sat', d['interface'])
            self.assertFalse(d['counterexample']['check_alone_approves_o_star'])
            self.assertGreater(d['counterexample']['unsafe_rate'], d['counterexample']['eps_any'])

    def test_all_model_mutants_have_a_counterexample(self):
        for group, ms in self.res['mutants_model'].items():
            for m in ms:
                self.assertEqual(m['z3'], 'sat', (group, m['mutant']))
                self.assertIn('counterexample', m)


@unittest.skipUnless(HAVE, 'z3-solver and hypothesis are required')
class Constants(unittest.TestCase):
    """The numbers copied into the model are the numbers of the code (as IEEE doubles)."""

    def test_constants(self):
        from rescuemind import advice, mission_memory as mm
        self.assertEqual(V.TAU_STD, Fraction(advice.V36_TAU_H))
        self.assertEqual(V.TAU_CAUTION, Fraction(mm.CAUTION_TAU_H))
        src = (ROOT / 'ros' / 'gazebo_waypoint_mission.py').read_text(encoding='utf8')
        self.assertIn("getattr(args,'adaptive_tau_sus',0.005)", src)
        self.assertEqual(V.TAU_SUS, Fraction(0.005))
        self.assertEqual(V.MAX_VIEWS, 1 + len(V.STD_SIDE) + len(V.EXTRA))
        self.assertEqual(len(V.VIEWS), 6)

    def test_station_ids_and_order_spec(self):
        for kind in ('legacy', 'k2', 'k3', 'k4', 'k5'):
            ss = V.station_set(kind)
            for item in ('water', 'medicine'):
                d = ss.default_order(item)
                self.assertEqual(sorted(d), sorted(ss.ids))
                for st in d:
                    self.assertEqual(ss.order(item, st), V.spec_order(ss, item, st))

    def test_mission_node_composes_the_modelled_functions(self):
        """Tripwire (not a proof): the ROS mission node is not executed here, but the functions the model is differentially
        tested against must still be the ones it calls, and no other approval path may appear."""
        tree = ast.parse((ROOT / 'ros' / 'gazebo_waypoint_mission.py').read_text(encoding='utf8'))
        calls = {}
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                f = n.func
                name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
                if name:
                    calls[name] = calls.get(name, 0) + 1
        for name in ('apply_memory_caution', 'peek_hazard', 'combine_with_look_around', 'schedule_adaptive_views', 'suspicion',
                     'next_candidate', 'begin_search', 'skip_source', 'denial_source', 'verify_station_local', 'classify_view',
                     'front_caution_only', 'onsite_check', 'look_around_peek'):
            self.assertIn(name, calls, f'{name} is no longer called by the mission node: re-check the model')
        self.assertEqual(calls['apply_memory_caution'], 1)
        self.assertEqual(calls['peek_hazard'], 1)
        self.assertEqual(calls['combine_with_look_around'], 1)
        src = (ROOT / 'ros' / 'gazebo_waypoint_mission.py').read_text(encoding='utf8')
        # the only way to a delivery without an on-site check is the naive-baseline switch, which a monotone plan never turns on
        self.assertEqual(src.count("'decision':{'allow':True,"), 1)
        self.assertEqual(src.count('route.insert('), 1)       # the recovery search inserts exactly one stage kind: a supply_station check


@unittest.skipUnless(HAVE, 'z3-solver and hypothesis are required')
class Differential(unittest.TestCase):
    def test_plan_real_vs_model(self):
        c = V.run_differential('plan', N)
        self.assertEqual(c['n'], N)
        self.assertGreater(c['plan_defined'], N // 4)
        self.assertGreater(c['plan_raised'], 0)            # the error path is exercised too
        self.assertGreater(c['cautioned'], 0)

    def test_station_real_vs_model_and_audit(self):
        c = V.run_differential('station', N)
        self.assertEqual(c['n'], N)
        self.assertGreater(c['approved'], N // 10)         # approvals, not only refusals, are compared

    def test_prop2_end_to_end_on_real_code(self):
        c = V.run_differential('p2', N)
        self.assertGreater(c['approved'], 0)
        self.assertGreater(c['cautioned'], 0)

    def test_prop2_end_to_end_without_the_plan_assertion(self):
        """The planning RULE is monotone by itself: switching assert_monotone off changes nothing."""
        c = V.run_differential('p2_noassert', N)
        self.assertGreater(c['scrutinised'], 0)

    def test_plan_with_credit_keeps_the_plan_properties(self):
        r = V.hypo_search(V.credit_case, V.strategies()['plan_case'], max(N // 2, 200))
        self.assertFalse(r['detected'], r)

    def test_loop_pieces(self):
        c = V.run_loop_differential(max(N // 2, 200))
        self.assertEqual(c['disagreements'], 0)

    def test_front_grid_boundaries(self):
        """Deterministic grid over the boundary values of the front scores and the caution threshold."""
        B = [0.0, 0.0049, 0.005, 0.0099, 0.01, 0.0101, 0.0499, 0.05, float('nan'), float('inf'), -0.1, 1.0]
        mk = lambda p1, p2: {'p': (p1, p2), 'hz': (False, False), 'thr': (0.05, 0.05), 'conf': (0.9, 0.9), 'supply': ('water', 'water')}
        calm = lambda: {'p': (0.0, 0.0), 'hz': (False, False), 'thr': (0.05, 0.05), 'conf': (0.9, 0.9), 'supply': ('water', 'water')}
        n = 0
        for p1 in B:
            for p2 in B:
                views = {w: calm() for w in V.VIEWS}
                views['F'] = mk(p1, p2)
                case = {'LA': False, 'AD': False, 'views': views, 'params': [(False, None, False), (True, 0.01, False), (True, 0.005, False)]}
                self.assertEqual(V.diff_station_case(case), [], (p1, p2))
                n += 1
        self.assertEqual(n, len(B) ** 2)

    def test_model_eval_with_a_solver_model_agrees_with_simplify(self):
        """The harness reduces model terms with z3.simplify; check that z3.Solver + Model.eval gives the same values."""
        import z3
        S = V.strategies()
        from hypothesis import given, settings, HealthCheck, Phase

        @settings(max_examples=60, deadline=None, derandomize=True, database=None, suppress_health_check=list(HealthCheck), phases=[Phase.generate])
        @given(S['station_case'])
        def run(case):
            case = dict(case, T=V.trigger_from_case(case))
            comp, _ = V.compiled_station()
            env = V.station_env(case)
            hasc, tau, scr = case['params'][0]
            env.update({'hasc': z3.BoolVal(bool(hasc)), 'scr': z3.BoolVal(bool(scr)), 'tau': V.rv(Fraction(tau)) if hasc else V.rv(0)})
            via_simplify = V.zbool(comp.eval(env)['A'])
            sol = z3.Solver()
            for name, val in env.items():
                if name in comp.vars:
                    sol.add(comp.vars[name] == val)
            self.assertEqual(sol.check(), z3.sat)
            via_model = z3.is_true(sol.model().eval(comp.terms['A'], model_completion=True))
            self.assertEqual(via_simplify, via_model)

        run()


@unittest.skipUnless(HAVE, 'z3-solver and hypothesis are required')
class Mutants(unittest.TestCase):
    """Representative bugs.  Plan mutants run with the in-plan assertion DISABLED so the harness, not the assertion, must catch them."""

    @classmethod
    def setUpClass(cls):
        cls.results = {r['mutant']: r for r in V.run_code_mutants(max(N, 800))}

    def test_at_least_ten_mutants(self):
        self.assertGreaterEqual(len(self.results), 10)

    def test_model_counterexample_for_each(self):
        for name, r in self.results.items():
            self.assertEqual(r['z3_model_mutant'], 'sat', name)

    def test_counterexample_replays_on_the_mutated_code_not_on_the_real_code(self):
        for name, r in self.results.items():
            if r['kind'] == 'plan':
                self.assertTrue(r['replay_mutant_code_violates'], (name, r.get('replay_mutant_violations')))
            else:
                self.assertTrue(r['replay_mutant_code_approves'], name)
                self.assertFalse(r['replay_real_code_approves'], name)
                self.assertFalse(r['replay_spec_model_approves'], name)

    def test_differential_harness_kills_each_mutant(self):
        for name, r in self.results.items():
            self.assertTrue(r['detect_differential']['detected'], f'{name} survived the differential harness')

    def test_model_free_property_kills_the_plan_mutants(self):
        for name, r in self.results.items():
            if r['kind'] == 'plan':
                self.assertTrue(r['detect_property']['detected'], f'{name} survived the property check')

    def test_real_code_survives_the_same_searches(self):
        S = V.strategies()
        real = V.Impl.real()
        self.assertFalse(V.hypo_search(lambda pc: V.diff_plan_case(pc, real), S['plan_case'], 300)['detected'])
        self.assertFalse(V.hypo_search(lambda sc: V.diff_station_case(sc, real), S['station_case'], 300)['detected'])


@unittest.skipUnless(HAVE, 'z3-solver and hypothesis are required')
class KnownFindings(unittest.TestCase):
    """Behaviours found while building the model.  They are not Proposition 2 violations (advice cannot cause them); they are
    recorded so that a change in either direction is noticed.  See docs/IMPROVEMENT_LOG.md I-23."""

    def test_F1_audit_raises_on_a_refusal_at_an_extra_view(self):
        """audit_local_checkpoint raises 'approved without the extra views' for a record that was REFUSED by the first or second
        extra view (the node stops there, so fewer than three extra views exist).  Fail-closed (the interlock denies anyway),
        but negative_evidence audits denied runs with it.  Fix: test `any hazard in peeks`, not only L/R."""
        from rescuemind.local_run_audit import audit_local_checkpoint
        mk = lambda p=0.0, hz=False: {'p': (p, p), 'hz': (hz, hz), 'thr': (0.05, 0.05), 'conf': (0.9, 0.9), 'supply': ('water', 'water')}
        views = {w: mk() for w in V.VIEWS}
        views['F'], views['L2'] = mk(0.006), mk(0.0, True)
        case = {'LA': True, 'AD': True, 'views': views, 'T': True}
        rec = {}
        self.assertFalse(V.real_approve(V.Impl.real(), case, False, None, False, rec))
        V.audit_approve(audit_local_checkpoint, case, rec, False, None, False)
        self.assertNotIn('without the extra views', rec.get('audit_error', '') or '')     # fixed: a refusal at L2 is legitimate

    def test_F2_nan_supply_confidence_counts_as_confident(self):
        """local_decision compares `c < min_confidence`; NaN compares False, so a NaN supply probability is not 'low confidence'.
        Perception-side (advice cannot set it); the hazard score has the fail-closed treatment, this one does not."""
        from rescuemind.local_vision import local_decision, PRIMARY_MODEL
        call = lambda: {'backend': 'local_transformers', 'real_inference': True, 'model': PRIMARY_MODEL, 'image_sha256': 'a',
                        'result': {'supply': 'water', 'scene': 'clear'}, 'scores': {'hazard_prob': 0.0, 'supply_probs': {'water': float('nan')}}}
        from rescuemind.local_vision import LocalInferenceError
        with self.assertRaises(LocalInferenceError):                 # fixed: a non-finite confidence is malformed
            local_decision('water', call(), call())

    def test_F3_bool_supply_confidence_is_accepted_as_a_number(self):
        """local_vision._confidence uses isinstance(x, (int, float)), which accepts True / False (the hazard score path rejects bool).
        True counts as 1.0, False as 0.0 (low confidence).  Perception-side; found by the first 1500-example run of the differential."""
        from rescuemind.local_vision import local_decision, PRIMARY_MODEL
        call = lambda c: {'backend': 'local_transformers', 'real_inference': True, 'model': PRIMARY_MODEL, 'image_sha256': 'a',
                          'result': {'supply': 'water', 'scene': 'clear'}, 'scores': {'hazard_prob': 0.0, 'supply_probs': {'water': c}}}
        from rescuemind.local_vision import LocalInferenceError
        for c in (True, False):                                      # fixed: a bool is not a probability
            with self.assertRaises(LocalInferenceError):
                local_decision('water', call(c), call(0.9))


if __name__ == '__main__':
    unittest.main()
