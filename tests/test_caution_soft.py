"""R5 #5: soft refusal of caution-only refusals (--caution-soft, default off).  The mission node is run through the real
run_ros with simulated ROS messages and a mocked checkpoint model (NOT Gazebo), as in test_i21_recovery_run."""
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
from rescuemind import caution_soft as cs  # noqa: E402
from rescuemind.local_run_audit import audit_local_checkpoint  # noqa: E402
from rescuemind.local_vision import local_decision  # noqa: E402
from rescuemind.mission_memory import apply_memory_caution, CAUTION_TAU_H  # noqa: E402
from rescuemind.recovery_evidence import RecoveryEvidenceError, audit_recovery  # noqa: E402
from rescuemind.stations import next_candidate  # noqa: E402

SS4 = rr.SS4


def calls(p1, p2=0.002):
    return {'model_calls': {'first': {'scores': {'hazard_prob': p1}}, 'second': {'scores': {'hazard_prob': p2}}}}


CAUT = ('on_site_supply_confirmed', True, calls(.03))        # approved by the v3.6 rule (p < 0.05), refused at tau_mem = 0.01
CLEAR = ('on_site_supply_confirmed', True, calls(.001))
WRONG = ('local_vlm_disagree_or_wrong_supply', False, calls(.001))
HAZARD = ('visible_hazard_at_checkpoint', False, calls(.3))     # the standard rule saw a hazard (p >= tau_h)
SIDE_CAUT = ('local_vlm_disagree_or_wrong_supply', False, calls(.03))   # a side view: supply out of view, p(hazard) in the gap
SIDE_HAZ = ('visible_hazard_at_checkpoint', False, calls(.3))
SIDE_CLEAR = ('local_vlm_disagree_or_wrong_supply', False, calls(.001))
SOFT = {'caution_soft': True}


def mem(*stations):
    return {'caution': {s: {'tau_h': CAUTION_TAU_H, 'first_side': None, 'seen_in': 'advice'} for s in stations},
            'first_station': 'W1', 'skip_check': False, 'deny_without_visit': False}


def checks(r):
    return rr.checks(r)


class PureFunctions(unittest.TestCase):
    def test_front_caution_only_needs_an_approval_that_only_the_threshold_removed(self):
        base = {'allow': True, 'reason': 'on_site_supply_confirmed', 'expected': 'water'}
        a, b = {'scores': {'hazard_prob': .03}}, {'scores': {'hazard_prob': .001}}
        d = apply_memory_caution(base, a, b, CAUTION_TAU_H)
        self.assertTrue(cs.front_caution_only(d))
        self.assertFalse(cs.front_caution_only(base))
        # a real hazard (the standard rule refused) or a wrong supply is never caution-only, with or without caution
        real = {'allow': False, 'reason': 'visible_hazard_at_checkpoint', 'expected': 'water'}
        self.assertFalse(cs.front_caution_only(apply_memory_caution(real, a, b, CAUTION_TAU_H)))
        wrong = {'allow': False, 'reason': 'local_vlm_disagree_or_wrong_supply'}
        self.assertFalse(cs.front_caution_only(apply_memory_caution(wrong, a, b, CAUTION_TAU_H)))
        self.assertFalse(cs.front_caution_only(None))

    def test_classify_view_three_way(self):
        lo, mid, hi = {'scores': {'hazard_prob': .001}}, {'scores': {'hazard_prob': .03}}, {'scores': {'hazard_prob': .3}}
        self.assertEqual(cs.classify_view('on_site_supply_confirmed', lo, lo, .01), 'clear')
        self.assertEqual(cs.classify_view('local_vlm_disagree_or_wrong_supply', mid, lo, .01), 'caution_only')
        self.assertEqual(cs.classify_view('visible_hazard_at_checkpoint', hi, lo, .01), 'hazard')
        self.assertEqual(cs.classify_view('visible_hazard_at_checkpoint', mid, lo, .01), 'hazard')   # the standard rule decided
        self.assertEqual(cs.classify_view('on_site_supply_confirmed', mid, lo, None), 'clear')       # no caution, no refusal

    def test_property_a_soft_search_only_delivers_where_the_standard_check_approves(self):
        """Random frames and cautions over the k = 4 order.  Simulated node logic with the real helpers.  For every outcome:
        the delivery station passes the plain v3.6 check on the same frames; stations visited are a prefix of the order;
        a real hazard stops at once; a caution-only refusal is never delivered from; without the flag any refusal at a
        caution station stops the mission (v3.6 behaviour)."""
        rng = random.Random(7)
        order = SS4.order('water')

        def decide(frame, tau_mem):
            p = frame['p']
            if p >= .05:
                base = {'allow': False, 'reason': 'visible_hazard_at_checkpoint', 'expected': 'water'}
            elif not frame['supply_ok']:
                base = {'allow': False, 'reason': 'local_vlm_disagree_or_wrong_supply', 'expected': 'water'}
            else:
                base = {'allow': True, 'reason': 'on_site_supply_confirmed', 'expected': 'water'}
            h = {'scores': {'hazard_prob': p}}
            return base, apply_memory_caution(base, h, h, tau_mem)

        def search(frames, caution, soft):
            checked, visited, log = [], [], []
            while (st := next_candidate(order, checked)) is not None:
                visited.append(st); checked.append(st)
                base, d = decide(frames[st], caution.get(st))
                if d['allow']:
                    return {'delivered': st, 'visited': visited, 'log': log}
                if cs.front_caution_only(d) and soft:
                    log.append((st, 'caution_only'))
                    continue
                if d['reason'] == 'local_vlm_disagree_or_wrong_supply':
                    continue                                    # the v3.6 recovery search
                log.append((st, d['reason']))
                return {'delivered': None, 'visited': visited, 'log': log, 'stopped_at': st}
            return {'delivered': None, 'visited': visited, 'log': log}

        n_deliv = n_soft_gain = 0
        for _ in range(3000):
            frames = {s: {'p': rng.choice([0., .002, .02, .03, .2]), 'supply_ok': rng.random() < .6} for s in order}
            caution = {s: CAUTION_TAU_H for s in order if rng.random() < .5}
            for soft in (False, True):
                out = search(frames, caution, soft)
                self.assertEqual(out['visited'], order[:len(out['visited'])])
                if out['delivered']:
                    n_deliv += 1
                    base, _ = decide(frames[out['delivered']], None)
                    self.assertTrue(base['allow'], 'delivery must pass the plain v3.6 check at the same frames')
                    self.assertTrue(frames[out['delivered']]['p'] < .05)
                    self.assertNotIn(out['delivered'], [s for s, _ in out['log']])
                if out.get('stopped_at'):
                    self.assertTrue(frames[out['stopped_at']]['p'] >= .05 or (not soft and caution.get(out['stopped_at']) is not None
                                                                              and frames[out['stopped_at']]['p'] >= CAUTION_TAU_H))
            hard = search(frames, caution, True)
            if hard.get('stopped_at'):          # a real hazard stops even with the flag
                self.assertGreaterEqual(frames[hard['stopped_at']]['p'], .05)
            if search(frames, caution, False)['delivered'] is None and hard['delivered'] is not None:
                n_soft_gain += 1
        self.assertGreater(n_deliv, 100)
        self.assertGreater(n_soft_gain, 10)       # the flag does recover missions that caution alone would have stopped


class NodeFront(unittest.TestCase):
    def go(self, verdicts, *, soft=True, memory=None, **kw):
        extra = dict(SOFT) if soft else {}
        return rr.run(SS4.order('water'), verdicts, stations=SS4, memory=memory or mem('W1'), extra_args=extra, **kw)

    def test_default_off_a_caution_refusal_still_stops_the_mission(self):
        r, err = self.go([CAUT, CLEAR], soft=False)
        self.assertIn('checkpoint DENIED: visible_hazard_at_checkpoint', err)
        self.assertEqual(checks(r), ['W1']); self.assertNotIn('recovery', r); self.assertNotIn('caution_refusals', r)
        self.assertIs(r['caution_soft'], False)

    def test_soft_continues_to_the_next_candidate_and_delivers_there(self):
        r, err = self.go([CAUT, CLEAR])
        self.assertIsNone(err); self.assertTrue(r['success'])
        self.assertEqual(checks(r), ['W1', 'W2']); self.assertEqual(r['checkpoint_station'], 'W2')
        self.assertEqual(r['recovery']['first_kind'], 'caution_only')
        (c,) = r['caution_refusals']
        self.assertEqual((c['station'], c['where'], c['continued'], c['next_station'], c['kind']), ('W1', 'front', True, 'W2', 'caution_only'))
        self.assertEqual((c['tau_mem'], c['base_reason']), (CAUTION_TAU_H, 'on_site_supply_confirmed'))
        self.assertTrue(r['checkpoint']['decision']['allow'])
        self.assertIn('caution_refusal', [e['stage'] for e in r['events']] + [e['stage'][9:] for e in r['events']])
        self.assertEqual(cs.audit_caution_refusals(r)['stations'], ['W1'])
        self.assertEqual([e['target'] for e in r['events'] if e.get('stage') == 'shelter_approach'], ['B'])

    def test_a_real_hazard_still_stops_immediately_with_the_flag(self):
        r, err = self.go([HAZARD, CLEAR])
        self.assertIn('checkpoint DENIED: visible_hazard_at_checkpoint', err)
        self.assertEqual(checks(r), ['W1']); self.assertNotIn('caution_refusals', r)

    def test_caution_then_real_hazard_at_the_next_station_stops(self):
        r, err = self.go([CAUT, HAZARD, CLEAR])
        self.assertIn('checkpoint DENIED: visible_hazard_at_checkpoint', err)
        self.assertEqual(checks(r), ['W1', 'W2']); self.assertEqual(len(r['caution_refusals']), 1)
        self.assertFalse(r['checkpoint']['decision']['allow'])

    def test_every_station_caution_refused_ends_with_a_refusal_after_k_checks(self):
        r, err = self.go([CAUT] * 5, memory=mem('W1', 'W2', 'M1', 'M2'))
        self.assertIn('checkpoint DENIED', err)
        self.assertEqual(checks(r), ['W1', 'W2', 'M1', 'M2']); self.assertEqual(len(r['_calls']), 4)
        self.assertEqual([c['continued'] for c in r['caution_refusals']], [True, True, True, False])
        self.assertEqual(r['caution_refusals'][-1]['next_station'], None)
        self.assertEqual(cs.audit_caution_refusals(r)['n_caution_refusals'], 4)

    def test_the_next_station_gets_its_own_caution_and_full_check(self):
        r, err = self.go([CAUT, CAUT, CLEAR], memory=mem('W1', 'W2'))
        self.assertIsNone(err); self.assertEqual(checks(r), ['W1', 'W2', 'M1']); self.assertEqual(r['checkpoint_station'], 'M1')
        self.assertEqual(len(r['recovery']['hops']), 1)
        self.assertEqual(r['recovery']['hops'][0]['kind'], 'caution_only')

    def test_wrong_supply_search_is_unchanged_and_mixes_with_soft_hops(self):
        r, err = self.go([WRONG, CAUT, CLEAR], memory=mem('W2'))
        self.assertIsNone(err); self.assertEqual(checks(r), ['W1', 'W2', 'M1'])
        self.assertNotIn('first_kind', r['recovery']); self.assertEqual(r['recovery']['hops'][0]['kind'], 'caution_only')

    def test_soft_does_not_need_the_recovery_flag(self):
        r, err = self.go([CAUT, CLEAR], recovery=False)
        self.assertIsNone(err); self.assertEqual(checks(r), ['W1', 'W2'])
        r, err = self.go([WRONG, CLEAR], recovery=False)           # the wrong-supply search still needs --recovery
        self.assertIn('DENIED', err); self.assertEqual(checks(r), ['W1'])

    def test_arena_two_stations(self):
        cfg, ct = rr.ArenaUnchanged.CFG, rr.ArenaUnchanged.CT
        m = {'caution': {'water': {'tau_h': CAUTION_TAU_H}}, 'first_station': 'water', 'skip_check': False, 'deny_without_visit': False}
        r, err = rr.run(['water', 'medicine'], [CAUT, CLEAR], config=cfg, centers=ct, memory=m, extra_args=SOFT)
        self.assertIsNone(err); self.assertEqual(checks(r), ['water', 'medicine']); self.assertEqual(r['checkpoint_station'], 'medicine')
        r, err = rr.run(['water', 'medicine'], [CAUT, CAUT, CLEAR], config=cfg, centers=ct, memory=dict(m, caution={
            'water': {'tau_h': CAUTION_TAU_H}, 'medicine': {'tau_h': CAUTION_TAU_H}}), extra_args=SOFT)
        self.assertIn('DENIED', err); self.assertEqual(checks(r), ['water', 'medicine'])


class NodeSideViews(unittest.TestCase):
    LA = {'look_around': 0.4}

    def go(self, verdicts, soft=True, memory=None):
        return rr.run(SS4.order('water'), verdicts, stations=SS4, memory=memory or mem('W1'),
                      extra_args=dict(self.LA, **(SOFT if soft else {})))

    def test_default_off_a_caution_side_view_stops_as_before(self):
        r, err = self.go([CLEAR, SIDE_CAUT, SIDE_CLEAR, CLEAR], soft=False)
        self.assertIn('DENIED: visible_hazard_at_checkpoint (look-around', err)
        self.assertEqual(checks(r), ['W1']); self.assertNotIn('recovery', r)

    def test_soft_side_view_continues_with_a_fresh_look_around_at_the_next_station(self):
        r, err = self.go([CLEAR, SIDE_CAUT, CLEAR, SIDE_CLEAR, SIDE_CLEAR])
        self.assertIsNone(err); self.assertEqual(checks(r), ['W1', 'W2']); self.assertEqual(r['checkpoint_station'], 'W2')
        self.assertEqual(len(r['_calls']), 5)                       # W1 front + 1 side view (the other side view is dropped), W2 front + 2
        (c,) = r['caution_refusals']
        self.assertEqual((c['station'], c['where'], c['continued'], c['base_reason']), ('W1', 'side_L', True, 'on_site_supply_confirmed'))
        first = r['recovery']['first_checkpoint']
        self.assertEqual([(p['side'], p['hazard']) for p in first['look_around']['peeks']], [('L', True)])
        self.assertFalse(first['decision']['allow']); self.assertEqual(first['decision']['look_around_hazard_sides'], ['L'])
        self.assertEqual(r['look_around']['station'], 'W2')          # not the refused station's record
        self.assertEqual([p['side'] for p in r['look_around']['peeks']], ['L', 'R'])
        self.assertEqual(first['look_around']['peeks'][0]['image'], 'recovery_peek_L_checkpoint.jpg')
        self.assertIn('recovery_peek_L_checkpoint.jpg', r['_files']); self.assertIn('peek_L_checkpoint.jpg', r['_files'])
        self.assertEqual(cs.audit_caution_refusals(r)['stations'], ['W1'])

    def test_a_real_hazard_in_a_side_view_stops_with_the_flag(self):
        r, err = self.go([CLEAR, SIDE_HAZ, SIDE_CLEAR, CLEAR])
        self.assertIn('DENIED: visible_hazard_at_checkpoint (look-around', err)
        self.assertEqual(checks(r), ['W1']); self.assertNotIn('caution_refusals', r)

    def test_side_view_caution_with_no_next_candidate_stops(self):
        r, err = rr.run(['W1'], [CLEAR, SIDE_CAUT, SIDE_CLEAR], stations=SS4, memory=mem('W1'), extra_args=dict(self.LA, **SOFT))
        # a one-station order has no next candidate (a station set always has k >= 2; the node follows the logged order)
        self.assertIn('DENIED', err)
        self.assertEqual([c['continued'] for c in r['caution_refusals']], [False])


class AuditOfSoftHops(unittest.TestCase):
    """audit_recovery accepts a caution-only hop only under the flag and only when the saved outputs show no real hazard."""

    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); self.addCleanup(self.t.cleanup)
        self.dir = Path(self.t.name)

    def hop(self, k, *, p=.03, scene='clear', tau=.01):
        img = self.dir / (('recovery_' if k == 0 else f'recovery{k + 1}_') + 'checkpoint.jpg')
        Image.new('RGB', (64, 48), (200, 30 + k * 20, 30)).save(img)
        sha = hashlib.sha256(img.read_bytes()).hexdigest()
        probs = {'water': 0.9, 'medicine': 0.01, 'other': 0.09}
        a, b = resp(1, 'water', sha, probs), resp(2, 'water', sha, probs)
        for c in (a, b):
            c['scores']['hazard_prob'] = p
            c['result']['scene'] = scene
        base = local_decision('water', a, b)
        cp = {'checkpoint_type': 'local_on_site_camera_supply_check', 'image_sha256': sha, 'backend': 'LOCAL_ONLY_NO_CLOUD_API',
              'mode': 'single', 'model_calls': {'first': a, 'second': b}, 'memory_caution_tau_h': tau,
              'decision': apply_memory_caution(base, a, b, tau)}
        return cp, img.name, sha

    def mission(self, **kw):
        cp, name, sha = self.hop(0, **kw)
        stages = ['recovery_supply_station', 'recovery_checkpoint_frame', 'recovery_checkpoint_decision',
                  'recovery_checkpoint_denial_dwell_finished', 'recovery_caution_refusal', 'recovery_search_started',
                  'supply_station', 'checkpoint_frame', 'checkpoint_decision']
        events = [{'stage': s, 't_wall_s': float(i)} for i, s in enumerate(stages)]
        events[1]['image_sha256'] = sha
        m = {'intent': {'item': 'water'}, 'checkpoint_station': 'W2', 'events': events, 'caution_soft': True,
             'checkpoint': {'decision': {'allow': True}},
             'recovery': {'first_station': 'W1', 'first_checkpoint': cp, 'first_checkpoint_image': name, 'first_kind': 'caution_only',
                          'searched_station': 'W2', 'candidates': ['W1', 'W2', 'M1', 'M2'], 'reason': 'visible_hazard_at_checkpoint'},
             'caution_refusals': [cs.refusal_record('W1', 'front', .03, .01, 'on_site_supply_confirmed', True, 'W2')]}
        return m

    def audit(self, m):
        # the 6th event per hop is the free-form caution record; the audit indexes the five hop events by name
        return audit_recovery(m, self.dir, completed=True)

    def test_a_genuine_caution_only_hop_passes(self):
        out = self.audit(self.mission())
        self.assertEqual(out['visited'], ['W1', 'W2']); self.assertEqual(out['caution']['stations'], ['W1'])

    def test_rejected_without_the_flag(self):
        m = self.mission(); m['caution_soft'] = False
        with self.assertRaises(RecoveryEvidenceError):
            self.audit(m)
        m = self.mission(); m.pop('caution_soft')
        with self.assertRaises(RecoveryEvidenceError):
            self.audit(m)

    def test_rejected_when_the_saved_outputs_show_a_real_hazard(self):
        # the model labelled the scene 'hazard' (the standard rule refuses): continuing would be a soft refusal of a real hazard
        with self.assertRaises(RecoveryEvidenceError):
            self.audit(self.mission(scene='hazard'))

    def test_rejected_when_marked_soft_but_it_was_a_wrong_supply_denial_or_an_approval(self):
        m = self.mission()
        m['recovery']['first_checkpoint']['decision'] = dict(m['recovery']['first_checkpoint']['decision'], allow=True)
        with self.assertRaises(RecoveryEvidenceError):
            self.audit(m)

    def test_hazard_hop_without_the_soft_mark_is_still_rejected(self):
        m = self.mission(); m['recovery'].pop('first_kind')
        with self.assertRaises(RecoveryEvidenceError):
            self.audit(m)

    def test_delivery_from_the_refused_station_fails_the_caution_audit(self):
        m = self.mission(); m['checkpoint_station'] = 'W1'; m['checkpoint'] = {'decision': {'allow': True}}
        with self.assertRaises(cs.CautionError):
            cs.audit_caution_refusals(m)

    def test_caution_audit_rules(self):
        m = self.mission()
        self.assertEqual(cs.audit_caution_refusals(m)['n_continued'], 1)
        bad = self.mission(); bad['caution_refusals'][0]['base_reason'] = 'visible_hazard_at_checkpoint'
        with self.assertRaises(cs.CautionError):
            cs.audit_caution_refusals(bad)
        bad = self.mission(); bad['caution_refusals'][0]['p_max'] = .001          # below tau_mem: not a caution refusal
        with self.assertRaises(cs.CautionError):
            cs.audit_caution_refusals(bad)
        bad = self.mission(); bad['caution_refusals'][0]['tau_mem'] = .06         # not a tightened threshold
        with self.assertRaises(cs.CautionError):
            cs.audit_caution_refusals(bad)
        self.assertEqual(cs.audit_caution_refusals({'events': []})['n_caution_refusals'], 0)

    def test_audit_local_checkpoint_reports_caution_only(self):
        cp, _, sha = self.hop(0)
        self.assertTrue(audit_local_checkpoint(cp, sha, expected='water')['caution_only'])
        cp, _, sha = self.hop(0, scene='hazard')
        self.assertFalse(audit_local_checkpoint(cp, sha, expected='water')['caution_only'])
        cp, _, sha = self.hop(0, p=.001)
        self.assertFalse(audit_local_checkpoint(cp, sha, expected='water')['caution_only'])


class MemoryOfSoftRefusals(unittest.TestCase):
    def test_side_view_caution_alert_of_a_caution_refused_station_is_remembered_as_caution_not_hazard(self):
        from rescuemind.mission_memory import observations
        r, err = rr.run(SS4.order('water'), [CLEAR, SIDE_CAUT, CLEAR, SIDE_CLEAR, SIDE_CLEAR], stations=SS4, memory=mem('W1'),
                        extra_args=dict(NodeSideViews.LA, **SOFT))
        self.assertIsNone(err)
        obs = observations(r, 'r1')
        # I-19 fix #28: a caution-only refusal is a caution alert, not a hazard (else it renews the caution forever)
        self.assertEqual([(o['station'], o['hazard'], o['hazard_views'], o['caution_views']) for o in obs],
                         [('W1', False, [], ['L']), ('W2', False, [], [])])


class OperatorReport(unittest.TestCase):
    def test_report_says_which_station_was_skipped_for_caution(self):
        from rescuemind import operator_report as opr
        r, err = rr.run(SS4.order('water'), [CAUT, CLEAR], stations=SS4, memory=mem('W1'), extra_args=SOFT)
        o = opr.outcome(r, {'state': 'COMPLETED'})
        self.assertEqual((o['kind'], o['caution_skipped']), ('delivered_after_search', ['W1']))
        self.assertIn('W1は警戒のため見送り', opr.headline(o)[0])


class Wiring(unittest.TestCase):
    def test_flag_reaches_node_and_orchestrator(self):
        import scripts.v32_orchestrate as orch
        plan = orch.build_plan('live', '避難所Bに飲料水を届けて', mission_timeout=900, evidence_dir=Path('/tmp/abcdef0123456789'),
                               caution_soft=True)
        self.assertIn(' --caution-soft ', ' '.join(plan['mission'].argv))
        plan = orch.build_plan('live', '避難所Bに飲料水を届けて', mission_timeout=900, evidence_dir=Path('/tmp/abcdef0123456789'))
        self.assertNotIn('--caution-soft', ' '.join(plan['mission'].argv))         # default off: the v3.6 command line is unchanged
        src = (ROOT / 'ros/gazebo_waypoint_mission.py').read_text()
        self.assertIn("'--caution-soft'", src)
        self.assertIn('def caution_refused', (ROOT / 'scripts/v32_orchestrate.py').read_text())


if __name__ == '__main__':
    unittest.main()
