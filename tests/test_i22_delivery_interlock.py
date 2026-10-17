"""I-22: delivery interlock.  Pure logic, a pure-python message-flow simulation, the guard node with fake ROS, and the
mission node (fake ROS, mocked model; NOT Gazebo).  Fixed key for the HMAC tests."""
import hashlib
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from PIL import Image  # noqa: E402
import test_i21_recovery_run as rr  # noqa: E402
from test_i21_stations import resp  # noqa: E402
from rescuemind import delivery_permit as dp  # noqa: E402
from rescuemind.delivery_interlock import Interlock, Policy, decide, summarise_log  # noqa: E402
from rescuemind.adaptive_views import suspicion  # noqa: E402
from rescuemind.local_vision import local_decision, combine_with_look_around  # noqa: E402
from rescuemind.mission_memory import apply_memory_caution, CAUTION_TAU_H  # noqa: E402

KEY = bytes.fromhex('00112233445566778899aabbccddeeff' * 2)
RUN = '0123456789abcdef'
PROBS = {'water': 0.9, 'medicine': 0.01, 'other': 0.09}


class Fixture:
    """A genuine saved approval: images on disk, two model passes per view, look-around (+ adaptive) and a plan."""

    def __init__(self, d, *, p_front=.001, p_side=.001, look_around=True, adaptive=False, extra=3, plan=None, tau=None,
                 scrutiny=False, station='water'):
        self.dir = Path(d)
        self.station = station
        self.n = 0
        a, b, sha = self.view('checkpoint.jpg', p_front)
        base = local_decision('water', a, b)
        self.cp = {'checkpoint_type': 'local_on_site_camera_supply_check', 'image_sha256': sha, 'backend': 'LOCAL_ONLY_NO_CLOUD_API',
                   'mode': 'single', 'model_calls': {'first': a, 'second': b}, 'decision': base}
        if tau is not None:
            self.cp['memory_caution_tau_h'] = tau
            self.cp['decision'] = apply_memory_caution(base, a, b, tau)
        self.plan = plan
        if look_around:
            la = {'offset_m': .4, 'station': station, 'points': [], 'peeks': []}
            for side in ('L', 'R'):
                la['peeks'].append(self.peek(side, p_side, tau))
            if adaptive:
                p_max = suspicion(self.cp, la['peeks'])
                la['adaptive'] = {'p_max': p_max, 'tau_sus': .005, 'triggered': p_max >= .005 or scrutiny, 'offset_m': .6, 'near_m': .3}
                if scrutiny:
                    la['adaptive']['scrutiny'] = True
                if p_max >= .005 or scrutiny:
                    for side in ('L2', 'R2', 'N')[:extra]:
                        la['peeks'].append(self.peek(side, p_side, tau))
            self.cp['look_around'] = la
        self.scrutiny_flag = scrutiny
        self.look = .4 if look_around else 0.
        self.adapt = .6 if adaptive else 0.

    def view(self, name, p):
        self.n += 1
        Image.new('RGB', (64, 48), (200, 30 + self.n * 9, 30)).save(self.dir / name)
        sha = hashlib.sha256((self.dir / name).read_bytes()).hexdigest()
        a, b = resp(1, 'water', sha, PROBS), resp(2, 'water', sha, PROBS)
        for c in (a, b):
            c['scores']['hazard_prob'] = p
        return a, b, sha

    def peek(self, side, p, tau):
        a, b, sha = self.view(f'peek_{side}_checkpoint.jpg', p)
        from rescuemind.mission_memory import peek_hazard
        hz = local_decision('water', a, b)['reason']
        return {'side': side, 'xy': [0, 0], 'image': f'peek_{side}_checkpoint.jpg', 'image_sha256': sha,
                'model_calls': {'first': a, 'second': b}, 'hazard': peek_hazard(hz, a, b, tau), 'reason': hz}

    def raw(self, **over):
        mission = {'run_id': RUN, 'checkpoint_station': self.station, 'intent': {'item': 'water'}, 'checkpoint': self.cp,
                   'memory': self.plan, 'advice_scrutiny': self.scrutiny_flag}
        mission.update(over)
        return dp.build_record(mission, image_dir=self.dir, front_name='checkpoint.jpg', look_around=self.look,
                               adaptive_views=self.adapt)


def monotone_plan(**kw):
    """A genuine monotone advice plan: location advice moved the station to the front, hazard advice added caution."""
    base = {'first_station': 'medicine', 'skip_check': False, 'deny_without_visit': False, 'caution': {}}
    plan = {'mode': 'verified', 'first_station': 'water', 'skip_check': False, 'deny_without_visit': False,
            'caution': {'water': {'tau_h': CAUTION_TAU_H, 'first_side': None, 'seen_in': 'advice'}},
            'advice': {'mode': 'monotone', 'base': base, 'items': [], 'rejected': [],
                       'applied': [{'effect': 'reorder', 'station': 'water'}, {'effect': 'caution', 'station': 'water'}]}}
    plan.update(kw)
    return plan


class Base(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); self.addCleanup(self.t.cleanup)
        self.dir = Path(self.t.name)

    def fx(self, **kw):
        return Fixture(self.dir, **kw)

    def ok(self, fx, policy=Policy()):
        d = decide(fx.raw(), policy)
        self.assertTrue(d.permit, d.reason)
        return d

    def denied(self, raw, why, policy=Policy()):
        d = decide(raw, policy)
        self.assertFalse(d.permit)
        self.assertIn(why, d.reason)
        return d


class Grant(Base):
    def test_valid_approval_is_permitted(self):
        d = self.ok(self.fx(), Policy(require_look_around=True))
        self.assertEqual((d.run_id, d.station), (RUN, 'water'))
        self.assertIn('recomputed_approve', d.checks)

    def test_valid_approval_without_look_around_when_not_required(self):
        self.ok(self.fx(look_around=False))

    def test_monotone_advice_plan_with_applied_caution_is_permitted(self):
        self.ok(self.fx(plan=monotone_plan(), tau=CAUTION_TAU_H), Policy(require_look_around=True))

    def test_scrutinised_station_with_caution_and_all_three_extra_views(self):
        fx = self.fx(adaptive=True, scrutiny=True, tau=CAUTION_TAU_H, plan=monotone_plan(scrutiny=['water']), p_side=.001)
        fx.plan['advice']['applied'][0]['scrutiny'] = True
        fx.plan['advice']['scrutiny'] = True
        d = self.ok(fx, Policy(require_look_around=True, require_adaptive=True))
        self.assertEqual(len([1 for pk in fx.cp['look_around']['peeks'] if pk['side'] in ('L2', 'R2', 'N')]), 3)
        self.assertIn('plan_monotone', d.checks)

    def test_rule_is_the_audit_not_the_node(self):
        import inspect
        import rescuemind.delivery_interlock as m
        src = inspect.getsource(m)
        self.assertIn('audit_local_checkpoint', src)
        self.assertNotIn('gazebo_waypoint_mission', src)


class Deny(Base):
    def test_tampered_model_scene_label(self):
        fx = self.fx()
        raw = json.loads(fx.raw())
        raw['checkpoint']['model_calls']['first']['result']['scene'] = 'hazard'       # decision still says allow
        self.denied(json.dumps(raw), 'recompute')

    def test_tampered_decision_flag(self):
        fx = self.fx(p_front=.001)
        raw = json.loads(fx.raw())
        raw['checkpoint']['model_calls']['first']['result']['supply'] = 'medicine'
        self.denied(json.dumps(raw), 'recompute')

    def test_recomputed_refusal_with_forged_allow(self):
        fx = self.fx()
        raw = json.loads(fx.raw())
        raw['checkpoint']['model_calls']['second']['result']['supply'] = 'medicine'
        raw['checkpoint']['decision']['allow'] = True
        self.denied(json.dumps(raw), 'recompute')

    def test_image_changed_after_the_check(self):
        fx = self.fx()
        raw = fx.raw()
        Image.new('RGB', (64, 48), (1, 2, 3)).save(self.dir / 'checkpoint.jpg')
        self.denied(raw, 'recompute')          # the model calls name the old hash

    def test_side_image_changed_after_the_check(self):
        fx = self.fx()
        raw = fx.raw()
        Image.new('RGB', (64, 48), (1, 2, 3)).save(self.dir / 'peek_L_checkpoint.jpg')
        self.denied(raw, 'side_image_hash_mismatch')

    def test_missing_image(self):
        fx = self.fx()
        raw = fx.raw()
        (self.dir / 'checkpoint.jpg').unlink()
        self.denied(raw, 'front_image_missing')

    def test_image_path_traversal_and_root(self):
        fx = self.fx()
        raw = json.loads(fx.raw()); raw['images']['front'] = '../checkpoint.jpg'
        self.denied(json.dumps(raw), 'bad_image_name')
        self.denied(fx.raw(), 'image_dir_outside_root', Policy(image_root=str(self.dir / 'elsewhere')))

    def test_trusted_checkpoint_without_model_calls(self):
        fx = self.fx()
        raw = json.loads(fx.raw())
        raw['checkpoint'] = {'memory_trusted': True, 'trusted_by': 'advice', 'decision': {'allow': True, 'reason': 'advice_trusted'}}
        self.denied(json.dumps(raw), 'recompute')

    def test_refusal_is_not_a_permit(self):
        fx = self.fx(p_front=.001)
        raw = json.loads(fx.raw())
        for k in ('first', 'second'):
            raw['checkpoint']['model_calls'][k]['result']['supply'] = 'medicine'
        raw['checkpoint']['decision'] = local_decision('water', *[raw['checkpoint']['model_calls'][k] for k in ('first', 'second')])
        raw['checkpoint'].pop('look_around')
        self.denied(json.dumps(raw), 'recomputed_decision_is_local_vlm_disagree_or_wrong_supply')

    def test_side_view_hazard_flag_forged(self):
        fx = self.fx()
        raw = json.loads(fx.raw())
        raw['checkpoint']['look_around']['peeks'][0]['model_calls']['first']['result']['scene'] = 'hazard'
        self.denied(json.dumps(raw), 'recompute')

    def test_plan_that_skips_the_check(self):
        for plan in (monotone_plan(skip_check=True), monotone_plan(deny_without_visit=True)):
            self.denied(self.fx(plan=plan, tau=CAUTION_TAU_H).raw(), 'plan_skips_or_refuses_without_visit')

    def test_plan_with_a_non_monotone_effect(self):
        plan = monotone_plan()
        plan['advice']['applied'].append({'effect': 'skip_check', 'station': 'water'})
        self.denied(self.fx(plan=plan, tau=CAUTION_TAU_H).raw(), 'plan:')

    def test_plan_that_loosens_or_removes_a_caution(self):
        for mutate in (lambda p: p['advice']['base'].update(caution={'water': {'tau_h': .005}}) or p['caution']['water'].update(tau_h=.01),
                       lambda p: p['advice']['base'].update(caution={'medicine': {'tau_h': .01}}),
                       lambda p: p['caution']['water'].update(tau_h=float('nan')),
                       lambda p: p['caution']['water'].update(tau_h=.06)):
            plan = monotone_plan(); mutate(plan)
            self.denied(self.fx(plan=plan, tau=CAUTION_TAU_H).raw(), 'plan:')

    def test_plan_that_drops_a_candidate(self):
        plan = monotone_plan(order=['water'])
        plan['advice']['base']['order'] = ['water', 'medicine']
        self.denied(self.fx(plan=plan, tau=CAUTION_TAU_H).raw(), 'plan:')

    def test_plan_caution_not_applied_to_the_checkpoint(self):
        self.denied(self.fx(plan=monotone_plan(), tau=None).raw(), 'plan_caution_not_applied')
        self.denied(self.fx(plan=monotone_plan(), tau=CAUTION_TAU_H * 0.9 + 0.04).raw(), 'plan_caution_not_applied')

    def test_missing_look_around_when_the_policy_asks(self):
        fx = self.fx(look_around=False)
        self.denied(fx.raw(), 'look_around_missing', Policy(require_look_around=True))

    def test_record_declares_look_around_so_it_cannot_drop_it(self):
        fx = self.fx(look_around=False); fx.look = .4          # the node says it ran --look-around 0.4 but shows no views
        self.denied(fx.raw(), 'look_around_missing')

    def test_only_one_side_view(self):
        fx = self.fx()
        raw = json.loads(fx.raw())
        raw['checkpoint']['look_around']['peeks'] = raw['checkpoint']['look_around']['peeks'][:1]
        self.denied(json.dumps(raw), 'standard_side_views_missing', Policy(require_look_around=True))

    def test_missing_adaptive_block(self):
        self.denied(self.fx().raw(), 'adaptive_views_missing', Policy(require_look_around=True, require_adaptive=True))

    def test_suspicious_station_approved_without_the_extra_views(self):
        for extra in (0, 2):
            fx = self.fx(p_side=.02, adaptive=True, extra=extra)
            d = decide(fx.raw(), Policy(require_adaptive=True, require_look_around=True))
            self.assertFalse(d.permit)
            self.assertIn('extra views', d.reason)

    def test_scrutinised_station_without_extra_views(self):
        fx = self.fx(adaptive=True, scrutiny=True, extra=1, tau=CAUTION_TAU_H, plan=monotone_plan(scrutiny=['water']))
        fx.plan['advice']['applied'][0]['scrutiny'] = True; fx.plan['advice']['scrutiny'] = True
        d = decide(fx.raw())
        self.assertFalse(d.permit)

    def test_scrutiny_plan_without_the_flag(self):
        fx = self.fx(tau=CAUTION_TAU_H, plan=monotone_plan(scrutiny=['water']))
        fx.plan['advice']['applied'][0]['scrutiny'] = True; fx.plan['advice']['scrutiny'] = True
        fx.scrutiny_flag = False
        self.assertFalse(decide(fx.raw()).permit)

    def test_garbage_never_raises(self):
        for raw in (None, '', 'not json', '[]', '{"v":1}', json.dumps({'v': 1, 'run_id': 'x', 'station': 's', 'expected': 'water'}),
                    json.dumps({'v': 1, 'run_id': 'x', 'station': 'water', 'expected': 'water', 'checkpoint': {}, 'images': 3}),
                    'x' * (dp.MAX_RECORD_BYTES + 1)):
            self.assertFalse(decide(raw).permit)

    def test_unknown_station_and_item(self):
        fx = self.fx()
        self.denied(fx.raw(checkpoint_station='attic'), 'unknown_station')
        self.denied(fx.raw(intent={'item': 'gold'}), 'bad_expected_item')


class Permits(unittest.TestCase):
    H = 'a' * 64

    def mk(self, now=100., ttl=4., key=KEY, h=None):
        return dp.make_permit(h or self.H, RUN, 'water', now, ttl, key)

    def test_valid(self):
        self.assertEqual(dp.check_permit(self.mk(), key=KEY, now=102., expected_hash=self.H), (True, 'ok'))

    def test_expired(self):
        self.assertEqual(dp.check_permit(self.mk(), key=KEY, now=104.5, expected_hash=self.H)[1], 'expired')

    def test_record_mismatch(self):
        self.assertEqual(dp.check_permit(self.mk(), key=KEY, now=101., expected_hash='b' * 64)[1], 'record_mismatch')
        self.assertEqual(dp.check_permit(self.mk(), key=KEY, now=101., expected_hash=None)[1], 'no_record')

    def test_forged_or_wrong_key(self):
        other = bytes(range(32))
        self.assertEqual(dp.check_permit(self.mk(key=other), key=KEY, now=101., expected_hash=self.H)[1], 'bad_mac')
        self.assertEqual(dp.check_permit(self.mk(key=None), key=KEY, now=101., expected_hash=self.H)[1], 'bad_mac')
        p = json.loads(self.mk()); p['not_after'] += 1000
        self.assertEqual(dp.check_permit(json.dumps(p), key=KEY, now=101., expected_hash=self.H)[1], 'bad_mac')
        p = json.loads(self.mk()); p['station'] = 'medicine'
        self.assertEqual(dp.check_permit(json.dumps(p), key=KEY, now=101., expected_hash=self.H)[1], 'bad_mac')

    def test_unsigned_permits_work_without_a_key(self):
        self.assertTrue(dp.check_permit(self.mk(key=None), key=None, now=101., expected_hash=self.H)[0])

    def test_lifetime_and_future(self):
        self.assertEqual(dp.check_permit(self.mk(ttl=500.), key=KEY, now=101., expected_hash=self.H)[1], 'bad_ttl')
        self.assertEqual(dp.check_permit(self.mk(now=200.), key=KEY, now=101., expected_hash=self.H)[1], 'issued_in_the_future')

    def test_malformed(self):
        for raw in (None, '', 'x', '[]', '{}', json.dumps({'v': 1}), 'x' * 20000):
            self.assertFalse(dp.check_permit(raw, key=KEY, now=1., expected_hash=self.H)[0])

    def test_key_file_is_private(self):
        with tempfile.TemporaryDirectory() as d:
            k = dp.generate_key(Path(d) / 'k')
            self.assertEqual(dp.load_key(Path(d) / 'k'), k)
            self.assertEqual((Path(d) / 'k').stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                dp.generate_key(Path(d) / 'k')


class Gate(unittest.TestCase):
    def gate(self, key=KEY):
        g = dp.PermitGate(key=key)
        g.on_record('record-1')
        return g

    def permit(self, g, now, raw='record-1', ttl=4., key=KEY):
        g.on_permit(dp.make_permit(dp.record_hash(raw), RUN, 'water', now, ttl, key))

    def test_search_phase_passes_without_a_permit(self):
        g = self.gate(); g.on_phase('search', 10.)
        self.assertEqual(g.filter(.2, .1, 10.2), (.2, .1, None))

    def test_deliver_phase_without_permit_is_zero(self):
        g = self.gate(); g.on_phase('deliver', 10.)
        self.assertEqual(g.filter(.2, .0, 10.2), (0., 0., 'delivery_interlock_malformed_permit'))

    def test_zero_always_passes(self):
        g = self.gate(); g.on_phase('deliver', 10.)
        self.assertEqual(g.filter(0., 0., 10.2), (0., 0., None))

    def test_deliver_phase_with_valid_permit_forwards(self):
        g = self.gate(); g.on_phase('deliver', 10.); self.permit(g, 10.)
        self.assertEqual(g.filter(.2, .1, 11.), (.2, .1, None))

    def test_expired_permit_stops_the_robot_mid_leg(self):
        g = self.gate(); g.on_phase('deliver', 10.); self.permit(g, 10.)
        g.on_phase('deliver', 14.4)
        self.assertEqual(g.filter(.2, .0, 14.5)[:2], (0., 0.))

    def test_permit_for_another_record_is_useless(self):
        g = self.gate(); g.on_phase('deliver', 10.); self.permit(g, 10.)
        g.on_record('record-2')
        self.assertEqual(g.filter(.2, .0, 10.5)[2], 'delivery_interlock_record_mismatch')
        self.permit(g, 10.5, raw='record-2')
        self.assertEqual(g.filter(.2, .0, 11.)[2], None)

    def test_missing_stale_or_unknown_phase_counts_as_deliver(self):
        g = self.gate()
        self.assertEqual(g.filter(.2, .0, 1.)[:2], (0., 0.))                 # never received
        g.on_phase('search', 10.)
        self.assertEqual(g.filter(.2, .0, 10.5)[2], None)
        self.assertEqual(g.filter(.2, .0, 11.5)[:2], (0., 0.))               # stale heartbeat
        g.on_phase('Search ', 12.)
        self.assertEqual(g.filter(.2, .0, 12.1)[:2], (0., 0.))               # unknown text
        g.on_phase('search', 20.)
        self.assertEqual(g.filter(.2, .0, 19.)[:2], (0., 0.))                # phase from the future

    def test_forged_permit_without_the_key(self):
        g = self.gate(); g.on_phase('deliver', 10.); self.permit(g, 10., key=None)
        self.assertEqual(g.filter(.2, .0, 10.5)[2], 'delivery_interlock_bad_mac')

    def test_oversized_record_invalidates_permits(self):
        g = self.gate(); g.on_phase('deliver', 10.); self.permit(g, 10.)
        g.on_record('x' * (dp.MAX_RECORD_BYTES + 1))
        self.assertEqual(g.filter(.2, .0, 10.5)[:2], (0., 0.))


class Simulation(Base):
    """Pure-python message flow: mission -> {record, phase} -> interlock -> permit -> guard gate, 10 Hz ticks."""

    def flow(self, fx_raw, *, interlock_alive=True, key=KEY, gate_key=KEY, hold_s=3., policy=Policy()):
        core = Interlock(policy, key=key, ttl_s=4., max_life_s=30.)
        gate = dp.PermitGate(key=gate_key)
        moved = []
        t = 100.
        gate.on_phase('deliver', t)
        gate.on_record(fx_raw)
        if interlock_alive:
            core.on_record(fx_raw, t)
        for i in range(int(hold_s * 10)):
            t = 100. + i * .1
            gate.on_phase('deliver', t)
            if i % 5 == 0 and interlock_alive:
                p = core.tick(t)
                if p:
                    gate.on_permit(p)
            moved.append(gate.filter(.25, 0., t)[0] > 0)
        return moved, core

    def test_approved_record_moves_after_the_first_permit(self):
        moved, core = self.flow(self.fx().raw())
        self.assertTrue(core.decision.permit)
        self.assertTrue(all(moved))

    def test_denied_record_never_moves(self):
        fx = self.fx()
        raw = json.loads(fx.raw()); raw['checkpoint']['model_calls']['first']['result']['scene'] = 'hazard'
        moved, core = self.flow(json.dumps(raw))
        self.assertFalse(core.decision.permit)
        self.assertFalse(any(moved))

    def test_dead_interlock_never_moves(self):
        moved, _ = self.flow(self.fx().raw(), interlock_alive=False)
        self.assertFalse(any(moved))

    def test_interlock_dying_mid_leg_stops_the_robot_within_the_ttl(self):
        core = Interlock(key=KEY, ttl_s=4.)
        raw = self.fx().raw()
        gate = dp.PermitGate(key=KEY); gate.on_record(raw); core.on_record(raw, 0.)
        gate.on_permit(core.tick(0.))
        gate.on_phase('deliver', 3.9)
        self.assertGreater(gate.filter(.25, 0., 3.9)[0], 0)
        gate.on_phase('deliver', 4.2)
        self.assertEqual(gate.filter(.25, 0., 4.2)[0], 0)

    def test_record_replaced_by_a_denied_one_withdraws_the_permit(self):
        fx = self.fx()
        good = fx.raw()
        core = Interlock(key=KEY)
        core.on_record(good, 0.)
        self.assertIsNotNone(core.tick(.5))
        bad = json.loads(good); bad['checkpoint']['decision']['allow'] = False
        core.on_record(json.dumps(bad), 1.)
        self.assertIsNone(core.tick(1.5))
        self.assertIsNone(core.on_record(json.dumps(bad), 2.))          # a repeat is not decided twice

    def test_old_record_stops_being_permitted(self):
        core = Interlock(key=KEY, max_life_s=10.)
        core.on_record(self.fx().raw(), 0.)
        self.assertIsNotNone(core.tick(9.)); self.assertIsNone(core.tick(10.5))

    def test_key_mismatch_between_interlock_and_guard(self):
        moved, _ = self.flow(self.fx().raw(), key=bytes(range(32)))
        self.assertFalse(any(moved))

    def test_log_summary(self):
        p = self.dir / 'il.jsonl'
        p.write_text('\n'.join(json.dumps(r) for r in ({'event': 'start'}, {'event': 'decision', 'permit': True},
                                                         {'event': 'decision', 'permit': False})) + '\n')
        s = summarise_log(p)
        self.assertEqual((s['decisions'], s['permits'], s['denials']), (2, 1, 1))
        self.assertFalse(summarise_log(self.dir / 'none.jsonl')['log'])


# --- the guard node with fake ROS -------------------------------------------------------------------------------------------

class FakeGuardNode:
    def __init__(self, name):
        self.subs, self.pubs, self.timers = {}, {}, []
    def create_publisher(self, cls, topic, qos):
        node = self
        class P:
            def publish(self, msg): node.pubs.setdefault(topic, []).append(msg)
        return P()
    def create_subscription(self, cls, topic, fn, qos): self.subs[topic] = fn
    def create_timer(self, period, fn): self.timers.append(fn)
    def get_logger(self): return NS(info=lambda *a: None, error=lambda *a: None)
    def destroy_node(self): pass


class Msg:
    def __init__(self, data=None): self.data = data; self.linear = NS(x=0.); self.angular = NS(z=0.)


class StubRelay:
    """Replaces the sensor-checking VelocityRelay: always ready, forwards the last request."""
    def __init__(self, **kw): self.last = (0., 0.); self.latched = None
    def request(self, lin, ang, now): self.last = (lin, ang)
    def decide(self, now): return NS(ready=True, linear=self.last[0], angular=self.last[1], reason='command_fresh', )


def load_guard():
    spec = importlib.util.spec_from_file_location('guard_i22', ROOT / 'ros/guarded_cmd_relay.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    m.VelocityRelay = StubRelay
    return m


def run_guard(argv_ns, scenario):
    """Run guarded_cmd_relay.run with fake ROS; `scenario(node, out)` drives it (instead of rclpy.spin)."""
    m = load_guard()
    holder = {}
    rclpy = types.ModuleType('rclpy'); rclpy.init = lambda: None; rclpy.shutdown = lambda: None
    def spin(node): holder['node'] = node; scenario(node)
    rclpy.spin = spin
    node_mod = types.ModuleType('rclpy.node'); node_mod.Node = FakeGuardNode
    qos = types.ModuleType('rclpy.qos'); qos.qos_profile_sensor_data = object(); qos.QoSProfile = lambda **kw: kw
    qos.ReliabilityPolicy = qos.HistoryPolicy = qos.DurabilityPolicy = NS(RELIABLE=1, KEEP_LAST=1, VOLATILE=1, BEST_EFFORT=2)
    class Twist:
        def __init__(self): self.linear = NS(x=0.); self.angular = NS(z=0.)
    mods = {'rclpy': rclpy, 'rclpy.node': node_mod, 'rclpy.qos': qos, 'geometry_msgs.msg': NS(Twist=Twist),
            'std_msgs.msg': NS(Bool=lambda data=None: NS(data=data), String=Msg), 'nav_msgs.msg': NS(Odometry=object),
            'sensor_msgs.msg': NS(Image=object, LaserScan=object)}
    with patch.dict(sys.modules, mods), patch.object(m.time, 'sleep', lambda s: None):
        m.run(argv_ns)
    return holder['node']


def twist(lin, ang=0.):
    return NS(linear=NS(x=lin, y=0., z=0.), angular=NS(x=0., y=0., z=ang))


class GuardNode(unittest.TestCase):
    def args(self, **kw):
        return NS(control_qos='reliable', legacy_latch_zero=False, **kw)

    def out(self, node):
        return [(m.linear.x, m.angular.z) for m in node.pubs['/cmd_vel']]

    def test_mode_off_is_unchanged_and_has_no_interlock_subscriptions(self):
        def sc(node):
            node.subs['/rescuemind/cmd_vel_request'](twist(.2, .1))
            for f in node.timers: f()
        node = run_guard(self.args(), sc)
        self.assertEqual(self.out(node)[0], (.2, .1))
        self.assertNotIn(dp.TOPIC_PHASE, node.subs); self.assertNotIn(dp.TOPIC_PERMIT, node.subs)

    def test_mode_off_ignores_a_deliver_phase(self):
        def sc(node):
            node.subs['/rescuemind/cmd_vel_request'](twist(.2))
            for f in node.timers: f()
        node = run_guard(self.args(delivery_interlock=False), sc)
        self.assertEqual(self.out(node)[0][0], .2)

    def test_deliver_without_permit_publishes_zero_then_forwards_with_a_permit(self):
        raw = 'approval-record-text'
        outs = {}
        def sc(node):
            node.subs[dp.TOPIC_RECORD](Msg(raw))
            node.subs[dp.TOPIC_PHASE](Msg('search'))
            node.subs['/rescuemind/cmd_vel_request'](twist(.2))
            for f in node.timers: f()                                            # search: forwarded
            node.subs[dp.TOPIC_PHASE](Msg('deliver'))
            for f in node.timers: f()                                            # deliver, no permit: zero
            import time
            node.subs[dp.TOPIC_PERMIT](Msg(dp.make_permit(dp.record_hash(raw), RUN, 'water', time.time(), 4., KEY)))
            node.subs[dp.TOPIC_PHASE](Msg('deliver'))
            for f in node.timers: f()                                            # deliver, permit: forwarded
            node.subs[dp.TOPIC_PERMIT](Msg(dp.make_permit(dp.record_hash('other'), RUN, 'water', time.time(), 4., KEY)))
            for f in node.timers: f()                                            # permit for another record: zero
        with tempfile.TemporaryDirectory() as d:
            kf = Path(d) / 'k'; kf.write_text(KEY.hex())
            node = run_guard(self.args(delivery_interlock=True, permit_key_file=str(kf)), sc)
        o = self.out(node)
        self.assertEqual([x[0] for x in o[:4]], [.2, 0., .2, 0.])

    def test_guard_does_not_import_the_mission_or_the_decision_code(self):
        src = (ROOT / 'ros/guarded_cmd_relay.py').read_text() + (ROOT / 'rescuemind/delivery_permit.py').read_text()
        for bad in ('gazebo_waypoint_mission', 'local_run_audit', 'delivery_interlock', 'advice', 'local_vision'):
            self.assertNotIn('import ' + bad, src)
            self.assertNotIn('from rescuemind.' + bad, src)
            self.assertNotIn('from .' + bad, src)


# --- the mission node (fake ROS, mocked model) -------------------------------------------------------------------------

class MissionNode(unittest.TestCase):
    CFG = rr.ArenaUnchanged.CFG
    CT = rr.ArenaUnchanged.CT

    def mission(self, responder, **extra):
        inst = []
        class Node(rr.FakeNode):
            def __init__(self):
                self.log = []; self.phase = None; super().__init__(); inst.append(self)
            @property
            def cmd(self): return self._cmd
            @cmd.setter
            def cmd(self, c):
                self._cmd = c
                if c.linear and self.log is not None:
                    self.log.append(('move', self.phase, self.permit_seen if hasattr(self, 'permit_seen') else False))
            def on_string(self, topic, data):
                if topic == dp.TOPIC_PHASE:
                    self.phase = data
                elif topic == dp.TOPIC_RECORD:
                    reply = responder(data)
                    if reply:
                        self.permit_seen = True
                        self.handlers[dp.TOPIC_PERMIT](NS(data=reply))
        with patch.object(rr, 'FakeNode', Node):
            r, err = rr.run(['water', 'medicine'], [rr.OK], config=self.CFG, centers=self.CT, extra_args=extra)
        return r, err, inst[0]

    def grant(self, raw):
        import time
        return dp.make_permit(dp.record_hash(raw), RUN, 'water', time.time(), 4., None)

    def test_flag_off_publishes_nothing_and_changes_nothing(self):
        r, err, node = self.mission(lambda raw: None)
        self.assertIsNone(err); self.assertTrue(r['success'])
        self.assertEqual(node.published, [])
        self.assertEqual(r['delivery_interlock'], {'enabled': False})

    def test_flag_on_with_a_permit_delivers_and_moves_only_after_it(self):
        r, err, node = self.mission(self.grant, delivery_interlock=True, interlock_wait=3.)
        self.assertIsNone(err, err); self.assertTrue(r['success'])
        phases = [d for t, d in node.published if t == dp.TOPIC_PHASE]
        records = [d for t, d in node.published if t == dp.TOPIC_RECORD]
        self.assertIn('search', phases); self.assertIn('deliver', phases)
        self.assertTrue(records)
        rec = json.loads(records[0])
        self.assertEqual((rec['station'], rec['expected']), ('water', 'water'))
        self.assertEqual(rec['checkpoint']['decision']['allow'], True)
        di = r['delivery_interlock']
        self.assertTrue(di['permit_received']); self.assertEqual(di['record_hash'], dp.record_hash(records[0]))
        moves_in_deliver = [m for m in node.log if m[1] == 'deliver']
        self.assertTrue(moves_in_deliver)
        self.assertTrue(all(m[2] for m in moves_in_deliver))         # a permit had been received before any delivery motion
        self.assertEqual(phases[0], 'search')

    def test_flag_on_without_a_permit_never_starts_the_delivery_leg(self):
        r, err, node = self.mission(lambda raw: None, delivery_interlock=True, interlock_wait=1.)
        self.assertIn('no permit', err); self.assertFalse(r['success'])
        self.assertFalse(r['delivery_interlock']['permit_received'])
        self.assertEqual([m for m in node.log if m[1] == 'deliver'], [])
        self.assertIn('delivery_permit_timeout', [e['stage'] for e in r['events']])

    def test_a_permit_for_another_record_does_not_count(self):
        r, err, node = self.mission(lambda raw: self.grant('something else'), delivery_interlock=True, interlock_wait=1.)
        self.assertIn('no permit', err)
        self.assertEqual([m for m in node.log if m[1] == 'deliver'], [])


class Flags(unittest.TestCase):
    def test_orchestrator_default_off_and_on(self):
        import scripts.v32_orchestrate as orch
        plan = orch.build_plan('live', 'x', mission_timeout=900, evidence_dir=Path('/tmp/abcdef0123456789'))
        self.assertNotIn('--delivery-interlock', ' '.join(plan['mission'].argv))
        self.assertFalse([s for s in plan['services'] if s.name == 'delivery_interlock'])
        plan = orch.build_plan('live', 'x', mission_timeout=900, evidence_dir=Path('/tmp/abcdef0123456789'),
                               delivery_interlock=True, interlock_key='/tmp/k', look_around=.4, adaptive_views=.6)
        self.assertIn('--delivery-interlock', ' '.join(plan['mission'].argv))
        svc = [s for s in plan['services'] if s.name == 'delivery_interlock']
        self.assertEqual(len(svc), 1)
        joined = ' '.join(svc[0].argv)
        for want in ('--key-file /tmp/k', '--require-look-around', '--require-adaptive', 'delivery_interlock.jsonl'):
            self.assertIn(want, joined)
        with self.assertRaises(ValueError):
            orch.build_plan('motion-check', 'x', mission_timeout=900, delivery_interlock=True)

    def test_campaign_trial_field(self):
        src = (ROOT / 'scripts/run_campaign.py').read_text()
        self.assertIn("trial.get('delivery_interlock')", src)
        self.assertIn("'--delivery-interlock'", src)


if __name__ == '__main__':
    unittest.main()
