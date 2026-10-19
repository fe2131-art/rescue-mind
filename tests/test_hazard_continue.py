"""I-42: continue after a REAL hazard refusal (--hazard-continue, default off).  The mission node is run through the real run_ros
with simulated ROS messages and a mocked checkpoint model (NOT Gazebo), as in test_caution_soft."""
import hashlib
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'ros'))
from PIL import Image  # noqa: E402
import test_i21_recovery_run as rr  # noqa: E402
from test_i21_stations import resp  # noqa: E402
from test_caution_soft import CAUT, CLEAR, HAZARD, SIDE_CAUT, SIDE_CLEAR, SIDE_HAZ, WRONG, calls, mem, checks  # noqa: E402
from rescuemind import hazard_continue as hc  # noqa: E402
from rescuemind.local_run_audit import audit_local_checkpoint  # noqa: E402
from rescuemind.local_vision import local_decision  # noqa: E402
from rescuemind.mission_memory import apply_memory_caution, observations  # noqa: E402
from rescuemind.recovery_evidence import RecoveryEvidenceError, audit_recovery  # noqa: E402

SS4 = rr.SS4
HC = {'hazard_continue': True}
BROKEN = ('visible_hazard_at_checkpoint', False, {'model_calls': {'first': {'scores': {'hazard_prob': float('nan')}},
                                                                   'second': {'scores': {'hazard_prob': .3}}}})


class PureFunctions(unittest.TestCase):
    def dec(self, **kw):
        return dict({'allow': False, 'reason': hc.HAZARD, 'expected': 'water'}, **kw)

    def test_front_real_hazard_needs_the_standard_rule_and_valid_scores(self):
        ok = {'scores': {'hazard_prob': .3}}
        self.assertTrue(hc.real_front_hazard(self.dec(), ok, ok))
        self.assertFalse(hc.real_front_hazard(self.dec(pre_caution_reason='on_site_supply_confirmed'), ok, ok))   # caution only
        self.assertFalse(hc.real_front_hazard(self.dec(allow=True), ok, ok))
        self.assertFalse(hc.real_front_hazard(self.dec(reason='local_vlm_disagree_or_wrong_supply'), ok, ok))
        for bad in ({'scores': {'hazard_prob': float('nan')}}, {'scores': {}}, None, {'scores': {'hazard_prob': True}}):
            self.assertFalse(hc.real_front_hazard(self.dec(), bad, ok))        # a broken view never continues
            self.assertFalse(hc.real_front_hazard(self.dec(), ok, bad))

    def test_side_real_hazard(self):
        hi, lo, mid = {'scores': {'hazard_prob': .3}}, {'scores': {'hazard_prob': .001}}, {'scores': {'hazard_prob': .03}}
        self.assertTrue(hc.real_side_hazard(hc.HAZARD, hi, lo, .01))
        self.assertFalse(hc.real_side_hazard('local_vlm_disagree_or_wrong_supply', mid, lo, .01))   # caution-only is --caution-soft
        self.assertFalse(hc.real_side_hazard(hc.HAZARD, {'scores': {'hazard_prob': float('nan')}}, lo, .01))

    def test_audit_rules(self):
        base = {'hazard_continue': True, 'recovery': {'first_kind': 'hazard', 'first_station': 'W1'},
                'hazard_refusals': [hc.refusal_record('W1', 'front', .3, True, 'W2')], 'checkpoint_station': 'W2',
                'checkpoint': {'decision': {'allow': True}}}
        self.assertEqual(hc.audit_hazard_refusals(base)['stations'], ['W1'])
        self.assertEqual(hc.audit_hazard_refusals({'events': []})['n_hazard_refusals'], 0)
        for name, bad in (('flag off', dict(base, hazard_continue=False)),
                          ('delivered from the refused station', dict(base, checkpoint_station='W1')),
                          ('hop count', dict(base, hazard_refusals=[hc.refusal_record('W1', 'front', .3, False, None)])),
                          ('twice', dict(base, hazard_refusals=base['hazard_refusals'] * 2))):
            with self.subTest(name), self.assertRaises(hc.HazardContinueError):
                hc.audit_hazard_refusals(bad)


class NodeFront(unittest.TestCase):
    def go(self, verdicts, *, on=True, memory=None, **kw):
        extra = dict(HC) if on else {}
        return rr.run(SS4.order('water'), verdicts, stations=SS4, memory=memory, extra_args=extra, **kw)

    def test_default_off_a_real_hazard_stops_the_mission_exactly_as_v36(self):
        r, err = self.go([HAZARD, CLEAR], on=False)
        self.assertIn('checkpoint DENIED: visible_hazard_at_checkpoint', err)
        self.assertEqual(checks(r), ['W1']); self.assertNotIn('recovery', r); self.assertNotIn('hazard_refusals', r)
        self.assertIs(r['hazard_continue'], False)

    def test_with_the_flag_the_search_goes_on_and_delivers_from_the_next_station(self):
        r, err = self.go([HAZARD, CLEAR])
        self.assertIsNone(err); self.assertTrue(r['success'])
        self.assertEqual(checks(r), ['W1', 'W2']); self.assertEqual(r['checkpoint_station'], 'W2')
        self.assertEqual(r['recovery']['first_kind'], 'hazard')
        (h,) = r['hazard_refusals']
        self.assertEqual((h['station'], h['where'], h['continued'], h['next_station'], h['kind']), ('W1', 'front', True, 'W2', 'hazard'))
        self.assertGreaterEqual(h['p_max'], .05)
        self.assertTrue(r['checkpoint']['decision']['allow'])
        self.assertEqual(hc.audit_hazard_refusals(r)['stations'], ['W1'])
        self.assertEqual([e['target'] for e in r['events'] if e.get('stage') == 'shelter_approach'], ['B'])

    def test_a_hazard_at_every_station_ends_with_a_refusal_after_k_checks_and_no_delivery(self):
        r, err = self.go([HAZARD] * 5)
        self.assertIn('checkpoint DENIED', err)
        self.assertEqual(checks(r), ['W1', 'W2', 'M1', 'M2'])
        self.assertEqual([h['continued'] for h in r['hazard_refusals']], [True, True, True, False])
        self.assertFalse(r['checkpoint']['decision']['allow'])
        self.assertNotIn('shelter_approach', [e.get('stage') for e in r['events']])

    def test_hazard_then_wrong_supply_then_clear_visits_each_candidate_once_in_order(self):
        r, err = self.go([HAZARD, WRONG, CLEAR])
        self.assertIsNone(err); self.assertEqual(checks(r), ['W1', 'W2', 'M1'])
        self.assertEqual(r['recovery']['first_kind'], 'hazard'); self.assertNotIn('kind', r['recovery']['hops'][0])
        self.assertEqual(r['checkpoint_station'], 'M1')

    def test_caution_and_hazard_hops_mix_when_both_flags_are_on(self):
        r, err = rr.run(SS4.order('water'), [CAUT, HAZARD, CLEAR], stations=SS4, memory=mem('W1'), extra_args={'caution_soft': True, **HC})
        self.assertIsNone(err); self.assertEqual(checks(r), ['W1', 'W2', 'M1'])
        self.assertEqual(r['recovery']['first_kind'], 'caution_only'); self.assertEqual(r['recovery']['hops'][0]['kind'], 'hazard')
        self.assertEqual(len(r['caution_refusals']), 1); self.assertEqual(len(r['hazard_refusals']), 1)

    def test_a_caution_refusal_alone_is_not_continued_by_this_flag(self):
        r, err = rr.run(SS4.order('water'), [CAUT, CLEAR], stations=SS4, memory=mem('W1'), extra_args=dict(HC))
        self.assertIn('checkpoint DENIED: visible_hazard_at_checkpoint', err)
        self.assertEqual(checks(r), ['W1']); self.assertNotIn('hazard_refusals', r)

    def test_a_broken_front_view_is_never_a_hazard_to_continue_past(self):
        r, err = self.go([BROKEN, CLEAR])
        self.assertIsNotNone(err)
        self.assertEqual(checks(r)[:1], ['W1']); self.assertNotIn('W2', checks(r))

    def test_memory_records_the_refused_station_as_a_real_hazard(self):
        r, err = self.go([HAZARD, CLEAR])
        obs = observations(r, 'r1')
        self.assertEqual([(o['station'], o['hazard'], o['hazard_views']) for o in obs], [('W1', True, ['front']), ('W2', False, [])])

    def test_arena_two_stations(self):
        cfg, ct = rr.ArenaUnchanged.CFG, rr.ArenaUnchanged.CT
        r, err = rr.run(['water', 'medicine'], [HAZARD, CLEAR], config=cfg, centers=ct, extra_args=dict(HC))
        self.assertIsNone(err); self.assertEqual(checks(r), ['water', 'medicine']); self.assertEqual(r['checkpoint_station'], 'medicine')
        r, err = rr.run(['water', 'medicine'], [HAZARD, HAZARD], config=cfg, centers=ct, extra_args=dict(HC))
        self.assertIn('DENIED', err); self.assertEqual(checks(r), ['water', 'medicine'])


class NodeSideViews(unittest.TestCase):
    LA = {'look_around': 0.4}

    def go(self, verdicts, on=True, memory=None):
        return rr.run(SS4.order('water'), verdicts, stations=SS4, memory=memory, extra_args=dict(self.LA, **(HC if on else {})))

    def test_default_off_a_real_side_hazard_stops_as_before(self):
        r, err = self.go([CLEAR, SIDE_HAZ, SIDE_CLEAR, CLEAR], on=False)
        self.assertIn('DENIED: visible_hazard_at_checkpoint (look-around', err)
        self.assertEqual(checks(r), ['W1']); self.assertNotIn('recovery', r)

    def test_a_side_hazard_continues_with_a_fresh_look_around_at_the_next_station(self):
        r, err = self.go([CLEAR, SIDE_HAZ, CLEAR, SIDE_CLEAR, SIDE_CLEAR])
        self.assertIsNone(err); self.assertEqual(checks(r), ['W1', 'W2']); self.assertEqual(r['checkpoint_station'], 'W2')
        (h,) = r['hazard_refusals']
        self.assertEqual((h['station'], h['where'], h['continued']), ('W1', 'side_L', True))
        first = r['recovery']['first_checkpoint']
        self.assertEqual([(p['side'], p['hazard']) for p in first['look_around']['peeks']], [('L', True)])
        self.assertFalse(first['decision']['allow'])
        self.assertEqual(r['look_around']['station'], 'W2')
        self.assertEqual(hc.audit_hazard_refusals(r)['stations'], ['W1'])
        obs = observations(r, 'r1')
        self.assertEqual([(o['station'], o['hazard'], o['hazard_views']) for o in obs], [('W1', True, ['L']), ('W2', False, [])])

    def test_a_caution_side_view_still_stops_with_only_this_flag(self):
        r, err = self.go([CLEAR, SIDE_CAUT, SIDE_CLEAR, CLEAR], memory=mem('W1'))
        self.assertIn('DENIED: visible_hazard_at_checkpoint (look-around', err)
        self.assertEqual(checks(r), ['W1']); self.assertNotIn('hazard_refusals', r)

    def test_a_broken_side_view_stops(self):
        r, err = self.go([CLEAR, BROKEN, SIDE_CLEAR, CLEAR])
        self.assertIn('DENIED', err); self.assertEqual(checks(r), ['W1']); self.assertNotIn('hazard_refusals', r)

    def test_side_hazard_with_no_next_candidate_stops(self):
        r, err = rr.run(['W1'], [CLEAR, SIDE_HAZ, SIDE_CLEAR], stations=SS4, extra_args=dict(self.LA, **HC))
        self.assertIn('DENIED', err)
        self.assertEqual([h['continued'] for h in r['hazard_refusals']], [False])


class AuditOfHazardHops(unittest.TestCase):
    """audit_recovery accepts a hazard hop only under the flag and only when the saved outputs show a real hazard on valid scores."""

    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); self.addCleanup(self.t.cleanup)
        self.dir = Path(self.t.name)

    def hop(self, *, p=.3, scene='hazard'):
        img = self.dir / 'recovery_checkpoint.jpg'
        Image.new('RGB', (64, 48), (200, 30, 30)).save(img)
        sha = hashlib.sha256(img.read_bytes()).hexdigest()
        probs = {'water': 0.9, 'medicine': 0.01, 'other': 0.09}
        a, b = resp(1, 'water', sha, probs), resp(2, 'water', sha, probs)
        for c in (a, b):
            c['scores']['hazard_prob'] = p
            c['result']['scene'] = scene
        base = local_decision('water', a, b)
        cp = {'checkpoint_type': 'local_on_site_camera_supply_check', 'image_sha256': sha, 'backend': 'LOCAL_ONLY_NO_CLOUD_API',
              'mode': 'single', 'model_calls': {'first': a, 'second': b}, 'memory_caution_tau_h': None,
              'decision': apply_memory_caution(base, a, b, None)}
        return cp, img.name, sha

    def mission(self, **kw):
        cp, name, sha = self.hop(**kw)
        stages = ['recovery_supply_station', 'recovery_checkpoint_frame', 'recovery_checkpoint_decision',
                  'recovery_checkpoint_denial_dwell_finished', 'recovery_hazard_refusal', 'recovery_search_started',
                  'supply_station', 'checkpoint_frame', 'checkpoint_decision']
        events = [{'stage': s, 't_wall_s': float(i)} for i, s in enumerate(stages)]
        events[1]['image_sha256'] = sha
        return {'intent': {'item': 'water'}, 'checkpoint_station': 'W2', 'events': events, 'hazard_continue': True,
                'checkpoint': {'decision': {'allow': True}},
                'recovery': {'first_station': 'W1', 'first_checkpoint': cp, 'first_checkpoint_image': name, 'first_kind': 'hazard',
                             'searched_station': 'W2', 'candidates': ['W1', 'W2', 'M1', 'M2'], 'reason': hc.HAZARD},
                'hazard_refusals': [hc.refusal_record('W1', 'front', .3, True, 'W2')]}

    def audit(self, m):
        return audit_recovery(m, self.dir, completed=True)

    def test_a_genuine_hazard_hop_passes(self):
        out = self.audit(self.mission())
        self.assertEqual(out['visited'], ['W1', 'W2']); self.assertEqual(out['hazard']['stations'], ['W1'])

    def test_rejected_without_the_flag(self):
        for drop in (False, None):
            m = self.mission()
            m['hazard_continue'] = drop
            if drop is None:
                m.pop('hazard_continue')
            with self.assertRaises(RecoveryEvidenceError):
                self.audit(m)

    def test_rejected_when_the_saved_outputs_show_no_real_hazard(self):
        with self.assertRaises(RecoveryEvidenceError):
            self.audit(self.mission(p=.001, scene='clear'))  # an approval, marked as a hazard hop

    def test_a_caution_only_outcome_is_not_a_hazard_hop(self):
        m = self.mission(p=.03, scene='clear')              # below tau_h = 0.05: the standard rule approves
        with self.assertRaises(RecoveryEvidenceError):
            self.audit(m)

    def test_delivery_from_the_refused_station_is_rejected(self):
        m = self.mission(); m['checkpoint_station'] = 'W1'
        with self.assertRaises((RecoveryEvidenceError, hc.HazardContinueError)):
            self.audit(m)

    def test_audit_local_checkpoint_reports_invalid_side_views(self):
        cp, _, sha = self.hop()
        self.assertFalse(audit_local_checkpoint(cp, sha, expected='water')['invalid_side'])


class ModelAgreesWithTheNode(unittest.TestCase):
    """The z3 loop model of --hazard-continue (scripts/verify_advice_smt.py loop_run_hc) against the real mission node, on random
    outcome sequences, with the flag on and off; and the lemma the availability proof assumes about advice."""

    CLASS = {'clear': (CLEAR, 0), 'wrong': (WRONG, 1), 'hazard': (HAZARD, 3)}

    def test_random_sequences_agree_with_the_model(self):
        import z3
        sys.path.insert(0, str(ROOT / 'scripts'))
        import verify_advice_smt as v
        rng = random.Random(42)
        n_gain = 0
        for _ in range(60):
            kinds = [rng.choice(['clear', 'wrong', 'hazard']) for _ in range(4)]
            for flag in (False, True):
                r, err = rr.run(SS4.order('water'), [self.CLASS[k][0] for k in kinds] + [CLEAR], stations=SS4,
                                extra_args=dict(HC) if flag else {})
                m = v.loop_run_hc([z3.IntVal(i) for i in range(4)], [z3.IntVal(self.CLASS[k][1]) for k in kinds], 4, z3.BoolVal(flag))
                want_deliv = z3.simplify(m['deliv']).as_long()
                want_visits = z3.simplify(m['visits']).as_long()
                got_deliv = SS4.order('water').index(r['checkpoint_station']) if err is None else -1
                self.assertEqual((got_deliv, len(checks(r))), (want_deliv, want_visits), (kinds, flag, err))
                if flag and err is None and 'hazard' in kinds[:got_deliv]:
                    n_gain += 1
        self.assertGreater(n_gain, 5)        # the sequences do exercise a delivery after a hazard refusal

    def test_advice_acts_only_on_approvals_so_a_refusal_keeps_its_class(self):
        from rescuemind.local_vision import combine_with_look_around
        rng = random.Random(7)
        for _ in range(400):
            dec = {'allow': False, 'reason': rng.choice([hc.HAZARD, 'local_vlm_disagree_or_wrong_supply', 'local_vlm_low_confidence']),
                   'expected': 'water'}
            a = {'scores': {'hazard_prob': rng.choice([0., .003, .02, .3])}}
            b = {'scores': {'hazard_prob': rng.choice([0., .003, .02, .3])}}
            self.assertEqual(apply_memory_caution(dec, a, b, rng.choice([None, .01, .02, .04])), dec)
            peeks = [{'side': 'L', 'hazard': rng.random() < .5}, {'side': 'R', 'hazard': rng.random() < .5}]
            self.assertEqual(combine_with_look_around(dec, peeks), dec)


class Wiring(unittest.TestCase):
    def test_flag_reaches_node_orchestrator_and_campaign_and_is_off_by_default(self):
        import scripts.v32_orchestrate as orch
        import scripts.run_campaign as rc
        plan = orch.build_plan('live', '避難所Bに飲料水を届けて', mission_timeout=900, evidence_dir=Path('/tmp/abcdef0123456789'),
                               hazard_continue=True)
        self.assertIn(' --hazard-continue ', ' '.join(plan['mission'].argv))
        plan = orch.build_plan('live', '避難所Bに飲料水を届けて', mission_timeout=900, evidence_dir=Path('/tmp/abcdef0123456789'))
        self.assertNotIn('--hazard-continue', ' '.join(plan['mission'].argv))        # default off: the v3.6 command line is unchanged
        self.assertIn('--hazard-continue', rc.advice_flags({'mode': 'monotone', 'file': 'experiments/advice_X/x.json', 'hazard_continue': True}))
        self.assertNotIn('--hazard-continue', rc.advice_flags({'mode': 'monotone', 'file': 'experiments/advice_X/x.json'}))
        self.assertIn("'--hazard-continue'", (ROOT / 'ros/gazebo_waypoint_mission.py').read_text())

    def test_orchestrator_treats_a_search_that_ran_out_as_an_expected_denial(self):
        import scripts.v32_orchestrate as orch
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / 'mission.json').write_text(json.dumps({'hazard_continue': True, 'hazard_refusals': [{'kind': 'hazard'}]}))
            self.assertTrue(orch.caution_refused(d))
            (d / 'mission.json').write_text(json.dumps({'hazard_continue': False, 'hazard_refusals': [{'kind': 'hazard'}]}))
            self.assertFalse(orch.caution_refused(d))


if __name__ == '__main__':
    unittest.main()
