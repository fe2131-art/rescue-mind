"""I-19 fixes #26 (fail-open side view), #27 (hazard threshold not verified), #28 (caution self-fixation).
Pure logic; the interlock/audit tests use genuine fixtures from test_i22_delivery_interlock."""
import copy
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
import test_i22_delivery_interlock as t22  # noqa: E402
from rescuemind import adaptive_views as av  # noqa: E402
from rescuemind import caution_soft as cs  # noqa: E402
from rescuemind import mission_memory as mm  # noqa: E402
from rescuemind.delivery_interlock import Policy, decide  # noqa: E402
from rescuemind.local_run_audit import audit_local_checkpoint, LocalReceiptError  # noqa: E402

HZ = 'visible_hazard_at_checkpoint'
BROKEN = [None, 'x', float('nan'), float('inf'), -0.1, 1.5, True, [], {}]


def call(p=0.001, **kw):
    c = {'scores': {'hazard_prob': p}}
    c.update(kw)
    return c


class FailClosedScore(unittest.TestCase):
    def test_hazard_prob_invalid_is_one(self):
        for bad in BROKEN:
            with self.subTest(bad=bad):
                self.assertEqual(mm._hazard_prob({'scores': {'hazard_prob': bad}}), 1.0)
                self.assertEqual(av._p({'scores': {'hazard_prob': bad}}), 1.0)
        for c in (None, {}, {'scores': None}, {'scores': {}}, {'scores': 3}, 'x'):
            with self.subTest(call=c):
                self.assertEqual(mm._hazard_prob(c), 1.0)
                self.assertEqual(av._p(c), 1.0)
        self.assertEqual(mm._hazard_prob(call(0.0)), 0.0)
        self.assertEqual(mm._hazard_prob(call(0.02)), 0.02)

    def test_peek_broken_view_is_a_hazard_with_and_without_caution(self):
        for bad in BROKEN:
            for tau in (None, 0.01, 0.03):
                with self.subTest(bad=bad, tau=tau):
                    broken = {'scores': {'hazard_prob': bad}}
                    self.assertTrue(mm.peek_hazard('on_site_supply_confirmed', broken, call(), tau))
                    self.assertTrue(mm.peek_hazard('on_site_supply_confirmed', call(), broken, tau))
        self.assertFalse(mm.peek_hazard('on_site_supply_confirmed', call(), call(), None))   # unchanged for valid views
        self.assertFalse(mm.peek_hazard('on_site_supply_confirmed', call(.005), call(.005), .01))

    def test_front_caution_refuses_on_broken_score(self):
        d = {'allow': True, 'reason': 'on_site_supply_confirmed'}
        for bad in BROKEN:
            out = mm.apply_memory_caution(dict(d), {'scores': {'hazard_prob': bad}}, call(), .01)
            self.assertFalse(out['allow'], bad)
            self.assertEqual(out['reason'], HZ)

    def test_soft_refusal_never_applies_to_a_broken_view(self):
        self.assertEqual(cs.classify_view('on_site_supply_confirmed', call(), {}, .01), 'hazard')
        self.assertEqual(cs.classify_view('on_site_supply_confirmed', call(), call(), .01), 'clear')
        self.assertEqual(cs.classify_view('on_site_supply_confirmed', call(.02), call(), .01), 'caution_only')

    def test_suspicion_of_missing_scores(self):
        self.assertEqual(av.suspicion({'model_calls': {'first': call(), 'second': {}}}, []), 1.0)


class Audit(t22.Base):
    def broken_peek(self, bad, *, flag, key='L'):
        fx = self.fx(tau=t22.CAUTION_TAU_H, plan=t22.monotone_plan())
        pk = next(p for p in fx.cp['look_around']['peeks'] if p['side'] == key)
        pk['model_calls']['first']['scores']['hazard_prob'] = bad
        pk['hazard'] = flag
        return fx

    def test_audit_rejects_a_broken_view_recorded_as_clear(self):
        for bad in (None, float('nan'), 'x', 7.0):
            fx = self.broken_peek(bad, flag=False)
            with self.subTest(bad=bad):
                with self.assertRaises(LocalReceiptError):
                    audit_local_checkpoint(fx.cp, fx.cp['image_sha256'], expected='water')
                d = decide(fx.raw(), Policy(require_look_around=True))
                self.assertFalse(d.permit)

    def test_audit_accepts_a_broken_view_recorded_as_hazard_but_never_approves(self):
        fx = self.broken_peek(float('nan'), flag=True)
        # the refusal record must itself be what the rule recomputes
        from rescuemind.local_vision import combine_with_look_around
        base = mm.apply_memory_caution(t22.local_decision('water', *fx.cp['model_calls'].values()),
                                       *fx.cp['model_calls'].values(), t22.CAUTION_TAU_H)
        fx.cp['decision'] = combine_with_look_around(base, [{'side': p['side'], 'hazard': p['hazard']} for p in fx.cp['look_around']['peeks']])
        res = audit_local_checkpoint(fx.cp, fx.cp['image_sha256'], expected='water')
        self.assertFalse(res['allow'])
        self.assertFalse(res['caution_only'])         # a broken view is a hard stop, not a soft (caution-only) refusal

    def test_interlock_no_permit_for_broken_adaptive_or_standard_view(self):
        fx = self.fx(adaptive=True, scrutiny=True, tau=t22.CAUTION_TAU_H, plan=t22.monotone_plan(scrutiny=['water']))
        fx.plan['advice']['applied'][0]['scrutiny'] = True
        fx.plan['advice']['scrutiny'] = True
        pol = Policy(require_look_around=True, require_adaptive=True)
        self.assertTrue(decide(fx.raw(), pol).permit)
        for side in ('L', 'R', 'L2', 'R2', 'N'):
            fx2 = copy.deepcopy(fx)
            for pk in fx2.cp['look_around']['peeks']:
                if pk['side'] == side:
                    del pk['model_calls']['second']['scores']['hazard_prob']       # broken view, still recorded as clear
            with self.subTest(side=side):
                d = decide(fx2.raw(), pol)
                self.assertFalse(d.permit)

    def test_front_without_scores_is_rejected(self):
        fx = self.fx()
        del fx.cp['model_calls']['first']['scores']
        with self.assertRaises(LocalReceiptError):
            audit_local_checkpoint(fx.cp, fx.cp['image_sha256'], expected='water')


class Client(unittest.TestCase):
    """Front-check path: verify_station_local rejects (-> the mission aborts, no delivery) any call without a valid score."""

    def test_front_path_rejects_broken_scores(self):
        import hashlib
        from PIL import Image
        from rescuemind.local_vision import verify_station_local, LocalInferenceError, PRIMARY_MODEL
        with tempfile.TemporaryDirectory() as d:
            img = Path(d) / 'c.jpg'
            Image.new('RGB', (512, 384), (120, 150, 170)).save(img, 'JPEG')
            sha = hashlib.sha256(img.read_bytes()).hexdigest()

            def transport(bad):
                def f(url, payload):
                    sc = {'supply_probs': {'water': .9, 'medicine': .05, 'other': .05}, 'hazard_threshold': .05}
                    if bad is not None:
                        sc['hazard_prob'] = bad
                    return {'backend': 'local_transformers', 'real_inference': True, 'model': PRIMARY_MODEL, 'image_sha256': sha,
                            'pass_id': payload['pass_id'], 'result': {'supply': 'water', 'scene': 'clear'}, 'scores': sc}
                return f
            out = verify_station_local(img, 'water', transport=transport(.001))
            self.assertTrue(out['decision']['allow'])
            for bad in (None, float('nan'), 'x', 2.0):
                with self.subTest(bad=bad), self.assertRaises(LocalInferenceError):
                    verify_station_local(img, 'water', transport=transport(bad))


class ThresholdVerification(t22.Base):
    """#27: tau_h is the server's flag (default 0.5); the client must verify every call's recorded hazard_threshold."""

    def setvals(self, fx, thr, *, where='front'):
        calls = list(fx.cp['model_calls'].values()) if where == 'front' else \
            list(fx.cp['look_around']['peeks'][0]['model_calls'].values())
        for c in calls[:1]:
            if thr == 'del':
                del c['scores']['hazard_threshold']
            else:
                c['scores']['hazard_threshold'] = thr

    def test_matching_threshold_is_permitted_and_reported(self):
        fx = self.fx()
        self.ok(fx, Policy(require_look_around=True))
        res = audit_local_checkpoint(fx.cp, fx.cp['image_sha256'], expected='water')
        self.assertTrue(res['hazard_threshold_verified'])
        self.assertEqual(res['hazard_threshold'], 0.05)

    def test_server_default_or_any_other_threshold_is_refused(self):
        for where in ('front', 'side'):
            for thr in (0.5, 0.3, 0.049, 0.051, float('nan'), True, 'x'):
                fx = self.fx()
                self.setvals(fx, thr, where=where)
                with self.subTest(where=where, thr=thr):
                    with self.assertRaises(LocalReceiptError):
                        audit_local_checkpoint(fx.cp, fx.cp['image_sha256'], expected='water')
                    self.assertFalse(decide(fx.raw(), Policy(require_look_around=True)).permit)

    def test_missing_record_denied_by_interlock_and_unverified_in_run_audit(self):
        for where in ('front', 'side'):
            fx = self.fx()
            self.setvals(fx, 'del', where=where)
            d = decide(fx.raw(), Policy(require_look_around=True))
            self.assertFalse(d.permit, where)
            self.assertIn('threshold', d.reason)
            res = audit_local_checkpoint(fx.cp, fx.cp['image_sha256'], expected='water')    # saved pre-fix runs
            self.assertFalse(res['hazard_threshold_verified'])
            with self.assertRaises(LocalReceiptError):
                audit_local_checkpoint(fx.cp, fx.cp['image_sha256'], expected='water', require_threshold=True)

    def test_policy_threshold_is_configurable_and_explicit(self):
        fx = self.fx()
        for c in fx.cp['model_calls'].values():
            c['scores']['hazard_threshold'] = 0.3
        for pk in fx.cp['look_around']['peeks']:
            for c in pk['model_calls'].values():
                c['scores']['hazard_threshold'] = 0.3
        self.assertFalse(decide(fx.raw(), Policy(require_look_around=True)).permit)
        self.assertTrue(decide(fx.raw(), Policy(require_look_around=True, hazard_threshold=0.3)).permit)

    def test_live_client_refuses_other_thresholds(self):
        import hashlib
        from PIL import Image
        from rescuemind.local_vision import verify_station_local, LocalInferenceError, PRIMARY_MODEL
        with tempfile.TemporaryDirectory() as d:
            img = Path(d) / 'c.jpg'
            Image.new('RGB', (512, 384), (120, 150, 170)).save(img, 'JPEG')
            sha = hashlib.sha256(img.read_bytes()).hexdigest()

            def transport(thr):
                def f(url, payload):
                    sc = {'supply_probs': {'water': .9, 'medicine': .05, 'other': .05}, 'hazard_prob': .001}
                    if thr is not None:
                        sc['hazard_threshold'] = thr
                    return {'backend': 'local_transformers', 'real_inference': True, 'model': PRIMARY_MODEL, 'image_sha256': sha,
                            'pass_id': payload['pass_id'], 'result': {'supply': 'water', 'scene': 'clear'}, 'scores': sc}
                return f
            self.assertTrue(verify_station_local(img, 'water', transport=transport(.05))['decision']['allow'])
            for thr in (0.5, None, 0.3):               # the server default, an unreported threshold, another value
                with self.subTest(thr=thr), self.assertRaises(LocalInferenceError):
                    verify_station_local(img, 'water', transport=transport(thr))
            self.assertTrue(verify_station_local(img, 'water', transport=transport(.3), hazard_threshold=.3)['decision']['allow'])


class WiredIn(unittest.TestCase):
    def test_node_orchestrator_and_interlock_carry_the_threshold(self):
        for rel, needle in (('ros/gazebo_waypoint_mission.py', 'expected_hazard_threshold'),
                            ('ros/delivery_interlock.py', 'hazard_threshold=args.hazard_threshold'),
                            ('scripts/v32_orchestrate.py', "'--expected-hazard-threshold'")):
            self.assertIn(needle, (ROOT / rel).read_text(encoding='utf8'), rel)


if __name__ == '__main__':
    unittest.main()
