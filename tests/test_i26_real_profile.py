"""I-26: the opt-in real-robot profile.  Fake clocks, fake messages and a fake rclpy (no ROS runtime needed).

Two kinds of tests: (1) the new behaviour (system clock gate, best-effort camera QoS, odometry frame names, one site.json);
(2) the DEFAULT stays what the registered studies use (no new flag in a default command line, the sim /clock gate is still
subscribed, Reliable camera QoS, defaults of the parsers unchanged)."""
import contextlib
import copy
import importlib.util
import io
import json
import math
import runpy
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
from rescuemind import real_profile as rp  # noqa: E402
from rescuemind.camera_clock_gate import CameraClockRejected  # noqa: E402
from rescuemind.odom_health import OdomHealth  # noqa: E402
from rescuemind.velocity_relay import VelocityRelay  # noqa: E402
from rescuemind.waypoint import Pose2, MotionCommand, integrate  # noqa: E402
import scripts.v32_orchestrate as orch  # noqa: E402
import rescuemind.checkpoint, rescuemind.local_vision, rescuemind.image_acquisition  # noqa: E402,F401  (patch.dict(sys.modules) must not drop them)

UNIX0 = 1_800_000_000
SITE = {'schema': rp.SITE_SCHEMA, 'hazard_threshold': 0.3, 'hazard_prompt': 'h35', 'hazard_views': 'tiles'}


def stamp_msg(ns):
    return NS(header=NS(stamp=NS(sec=ns // 10**9, nanosec=ns % 10**9)))


def site_text(**kw):
    d = dict(SITE)
    d.update(kw)
    return json.dumps({k: v for k, v in d.items() if v is not None})


class SystemClockGateTests(unittest.TestCase):
    NOW = UNIX0 * 10**9

    def gate(self, now=None):
        box = [self.NOW if now is None else now]
        g = rp.SystemClockGate(now_ns=lambda: box[0])
        return g, box

    def test_fresh_frame_passes_with_the_sim_tolerances(self):
        g, _ = self.gate()
        r = g.check_frame(stamp_msg(self.NOW - 300_000_000), 1.0)
        self.assertEqual(r['camera_lag_to_system_clock_s'], 0.3)
        self.assertEqual(r['limits_s'], {'max_lag': 1.2, 'max_lead': 0.25})
        self.assertEqual(r['basis'], 'system_clock_vs_camera_ROS_stamp')

    def test_same_limits_as_the_gazebo_gate(self):
        from rescuemind.camera_clock_gate import CameraClockGate
        sim = CameraClockGate()
        g, _ = self.gate()
        self.assertEqual((g.max_camera_lag_s, g.max_camera_lead_s), (sim.max_camera_lag_s, sim.max_camera_lead_s))

    def test_boundaries(self):
        g, _ = self.gate()
        g.check_frame(stamp_msg(self.NOW - 1_200_000_000))           # exactly the lag limit: accepted
        g2, _ = self.gate()
        g2.check_frame(stamp_msg(self.NOW + 250_000_000))            # exactly the lead limit: accepted
        with self.assertRaisesRegex(CameraClockRejected, 'too_old_for_system_clock'):
            self.gate()[0].check_frame(stamp_msg(self.NOW - 1_200_000_001))
        with self.assertRaisesRegex(CameraClockRejected, 'ahead_of_system_clock'):
            self.gate()[0].check_frame(stamp_msg(self.NOW + 250_000_001))

    def test_stamp_since_boot_instead_of_unix_time_is_rejected(self):
        with self.assertRaisesRegex(CameraClockRejected, 'too_old'):
            self.gate()[0].check_frame(stamp_msg(12_345 * 10**9))

    def test_absent_zero_negative_or_malformed_stamps_fail_closed(self):
        g, _ = self.gate()
        for bad in (NS(), NS(header=None), NS(header=NS()), stamp_msg(0), NS(header=NS(stamp=NS(sec=-1, nanosec=0))),
                    NS(header=NS(stamp=NS(sec=UNIX0, nanosec=10**9))), NS(header=NS(stamp=NS(sec='x', nanosec=0))), None):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(CameraClockRejected, 'invalid_camera_ros_stamp'):
                    g.check_frame(bad)
        self.assertEqual(g.rejected_count, 8)

    def test_a_regressed_stamp_poisons_the_gate(self):
        g, box = self.gate()
        g.check_frame(stamp_msg(self.NOW - 100_000_000))
        box[0] += 10**8
        with self.assertRaisesRegex(CameraClockRejected, 'not_monotonic'):
            g.check_frame(stamp_msg(self.NOW - 200_000_000))
        box[0] += 10**8
        with self.assertRaisesRegex(CameraClockRejected, 'not_monotonic'):     # sticky: a good stamp no longer helps
            g.check_frame(stamp_msg(self.NOW + 10**8))

    def test_repeated_stamp_is_not_a_regression_but_goes_stale(self):
        g, box = self.gate()
        s = self.NOW - 100_000_000
        g.check_frame(stamp_msg(s))
        box[0] += 500_000_000
        g.check_frame(stamp_msg(s))
        box[0] += 900_000_000                                   # the camera keeps republishing the same old frame
        with self.assertRaisesRegex(CameraClockRejected, 'too_old'):
            g.check_frame(stamp_msg(s))

    def test_system_clock_stepping_backwards_is_rejected(self):
        g, box = self.gate()
        g.check_frame(stamp_msg(self.NOW))
        box[0] -= 5 * 10**9                                     # NTP step
        with self.assertRaisesRegex(CameraClockRejected, 'system_clock_rewound'):
            g.check_frame(stamp_msg(self.NOW + 1))

    def test_reception_time_is_used_when_given(self):
        g, box = self.gate()
        box[0] = self.NOW + 5 * 10**9                           # the executor looked much later than the callback
        g.check_frame(stamp_msg(self.NOW - 100_000_000), 1.0, received_ns=self.NOW)
        with self.assertRaisesRegex(CameraClockRejected, 'too_old'):
            rp.SystemClockGate(now_ns=lambda: box[0]).check_frame(stamp_msg(self.NOW - 100_000_000))

    def test_invalid_clock_or_receive_time(self):
        g, _ = self.gate()
        for v in (0, -5, 1.5e18, True):
            with self.subTest(v=v):
                with self.assertRaisesRegex(CameraClockRejected, 'invalid_system_clock'):
                    g.check_frame(stamp_msg(self.NOW), received_ns=v)
        for w in (math.nan, math.inf, True, 'x'):
            with self.assertRaisesRegex(CameraClockRejected, 'invalid_frame_receive_time'):
                self.gate()[0].check_frame(stamp_msg(self.NOW), w)

    def test_invalid_parameters(self):
        for kw in ({'max_camera_lag_s': 0}, {'max_camera_lead_s': -1}, {'max_camera_lag_s': math.nan},
                   {'max_camera_lead_s': 31}, {'max_camera_lag_s': True}, {'now_ns': 5}):
            with self.assertRaises(CameraClockRejected):
                rp.SystemClockGate(**kw)

    def test_receipt_audit(self):
        g, _ = self.gate()
        proof = g.check_frame(stamp_msg(self.NOW - 300_000_000))
        ev = {'events': [{'stage': rp.SYSTEM_CLOCK_STAGE, **proof},
                         {'stage': 'checkpoint_frame', 'ros_acquisition_stamp_ns': self.NOW - 300_000_000}]}
        self.assertTrue(rp.audit_system_clock_capture(ev)['passed'])
        def mut(f):
            e = copy.deepcopy(ev)
            f(e)
            with self.assertRaises(rp.SystemClockEvidenceError):
                rp.audit_system_clock_capture(e)
        mut(lambda e: e['events'][0].update(basis='Gazebo_clock_vs_camera_ROS_stamp'))
        mut(lambda e: e['events'][0]['limits_s'].update(max_lag=5.0))                 # weakened limit
        mut(lambda e: e['events'][0].update(camera_lag_to_system_clock_s=0.1))        # inconsistent lag
        mut(lambda e: e['events'][0].update(system_clock_ns=self.NOW + 10 * 10**9))   # far from the stamp
        mut(lambda e: e['events'][1].update(ros_acquisition_stamp_ns=1))              # a different frame
        mut(lambda e: e['events'].pop(0))                                             # no receipt
        mut(lambda e: e['events'].append(dict(e['events'][0])))                       # two receipts
        with self.assertRaises(rp.SystemClockEvidenceError):
            rp.audit_system_clock_capture({})


class ProfileValidation(unittest.TestCase):
    def test_defaults_are_not_the_real_profile(self):
        self.assertFalse(rp.check_profile())
        self.assertFalse(rp.check_profile('sim', 'reliable'))
        self.assertTrue(rp.check_profile('system', 'best_effort'))
        self.assertTrue(rp.check_profile('system', 'reliable'))

    def test_best_effort_only_under_the_real_profile(self):
        with self.assertRaises(rp.SiteConfigError):
            rp.check_profile('sim', 'best_effort')
        for bad in (('wall', 'reliable'), ('sim', 'sensor_data'), ('', ''), (None, None)):
            with self.assertRaises(rp.SiteConfigError):
                rp.check_profile(*bad)

    def test_guard_settings(self):
        self.assertEqual(rp.guard_settings(NS()), ('reliable', None, None))
        self.assertEqual(rp.guard_settings(NS(camera_qos='best_effort', real_profile=True, odom_frame='odom', base_frame='base_footprint')),
                         ('best_effort', 'odom', 'base_footprint'))
        with self.assertRaises(rp.SiteConfigError):
            rp.guard_settings(NS(camera_qos='best_effort'))
        with self.assertRaises(rp.SiteConfigError):
            rp.guard_settings(NS(odom_frame='od om'))
        with self.assertRaises(rp.SiteConfigError):
            rp.guard_settings(NS(camera_qos='fast'))

    def test_guard_settings_read_frames_from_the_site_config(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'site.json'
            f.write_text(site_text(odom_frame='odom', base_frame='base_footprint'))
            self.assertEqual(rp.guard_settings(NS(site_config=str(f))), ('reliable', 'odom', 'base_footprint'))
            self.assertEqual(rp.guard_settings(NS(site_config=str(f), base_frame='base_link'))[2], 'base_link')   # flag wins


class OdomFrames(unittest.TestCase):
    @staticmethod
    def odom(frame='odom', child='base_link', stamp=5):
        return NS(pose=NS(pose=NS(position=NS(x=0., y=0., z=0.), orientation=NS(x=0., y=0., z=0., w=1.))),
                  header=NS(frame_id=frame, stamp=NS(sec=stamp, nanosec=0)), child_frame_id=child)

    def test_default_health_check_is_unchanged(self):
        self.assertIsNone(OdomHealth().observe(self.odom()))
        self.assertIsNone(OdomHealth().observe(self.odom('robot/odom', 'robot/base_link')))
        self.assertEqual(OdomHealth().observe(self.odom(child='base_footprint')), 'invalid_odom_frames')
        self.assertEqual(OdomHealth().observe(self.odom(frame='map')), 'invalid_odom_frames')

    def test_configurable_frames(self):
        h = OdomHealth(odom_frame='odom', base_frame='base_footprint')
        self.assertIsNone(h.observe(self.odom(child='base_footprint')))
        self.assertEqual(OdomHealth(odom_frame='odom', base_frame='base_footprint').observe(self.odom()), 'invalid_odom_frames')
        self.assertEqual(OdomHealth(odom_frame='wheel_odom').observe(self.odom()), 'invalid_odom_frames')
        self.assertIsNone(OdomHealth(odom_frame='wheel_odom').observe(self.odom(frame='wheel_odom')))

    def test_velocity_guard_latches_on_a_wrong_frame(self):
        relay = VelocityRelay(started_at=0., odom_health=OdomHealth(base_frame='base_footprint'))
        relay.odometry(1., self.odom(child='base_link'))
        self.assertEqual(relay.latched, 'invalid_odom_frames')
        ok = VelocityRelay(started_at=0., odom_health=OdomHealth(base_frame='base_footprint'))
        ok.odometry(1., self.odom(child='base_footprint'))
        self.assertIsNone(ok.latched)

    def test_odom_frames_ok_helper(self):
        m = self.odom('robot/odom', 'robot/base_footprint')
        self.assertTrue(rp.odom_frames_ok(m, None, None))
        self.assertTrue(rp.odom_frames_ok(m, 'odom', 'base_footprint'))
        self.assertTrue(rp.odom_frames_ok(m, 'odom', None))
        self.assertFalse(rp.odom_frames_ok(m, 'odom', 'base_link'))
        self.assertFalse(rp.odom_frames_ok(m, 'map', None))
        self.assertFalse(rp.odom_frames_ok(NS(), 'odom', None))
        self.assertTrue(rp.odom_frames_ok(NS(), None, None))


class ImageQos(unittest.TestCase):
    @staticmethod
    def fake_qos():
        qos = types.ModuleType('rclpy.qos')
        qos.QoSProfile = lambda **kw: kw
        qos.ReliabilityPolicy = NS(RELIABLE='RELIABLE', BEST_EFFORT='BEST_EFFORT')
        qos.HistoryPolicy = NS(KEEP_LAST='KEEP_LAST')
        qos.DurabilityPolicy = NS(VOLATILE='VOLATILE')
        rclpy = types.ModuleType('rclpy')
        rclpy.qos = qos
        return {'rclpy': rclpy, 'rclpy.qos': qos}

    def test_default_is_reliable_keep_last_2(self):
        from rescuemind.ros_qos import image_qos
        with patch.dict(sys.modules, self.fake_qos()):
            self.assertEqual(image_qos(), {'depth': 2, 'reliability': 'RELIABLE', 'history': 'KEEP_LAST', 'durability': 'VOLATILE'})
            self.assertEqual(image_qos(reliability='reliable'), image_qos())

    def test_best_effort_and_validation(self):
        from rescuemind.ros_qos import image_qos
        with patch.dict(sys.modules, self.fake_qos()):
            q = image_qos(reliability='best_effort')
            self.assertEqual((q['reliability'], q['depth'], q['history']), ('BEST_EFFORT', 2, 'KEEP_LAST'))
            with self.assertRaises(ValueError):
                image_qos(reliability='transient')


class SiteConfigTests(unittest.TestCase):
    def test_minimal_config_and_derived_caution(self):
        s = rp.parse_site_config(site_text())
        self.assertEqual((s.hazard_threshold, s.caution_ratio, s.caution_tau_h), (0.3, 0.2, 0.01))
        self.assertEqual((s.hazard_prompt, s.hazard_views, s.odom_frame, s.base_frame), ('h35', 'tiles', None, None))
        b = s.block()
        self.assertEqual((b['hazard_threshold'], b['caution_tau_h'], b['schema']), (0.3, 0.01, rp.SITE_SCHEMA))
        self.assertEqual(len(b['sha256']), 64)

    def test_caution_is_relative_to_tau_h_but_never_loosened_beyond_the_simulation_value(self):
        self.assertEqual(rp.derive_caution(0.05), 0.01)          # the simulation pair: 0.05 / 0.01
        self.assertEqual(rp.derive_caution(0.3), 0.01)
        self.assertEqual(rp.derive_caution(1.0), 0.01)
        self.assertEqual(rp.derive_caution(0.02), 0.004)         # a stricter site tightens the caution with it
        self.assertEqual(rp.derive_caution(0.005, 0.5), 0.0025)
        self.assertEqual(rp.parse_site_config(site_text(hazard_threshold=0.02)).caution_tau_h, 0.004)
        for tau in (0.0001, 0.001, 0.01, 0.02, 0.05, 0.1, 0.3, 0.5, 1.0):
            for ratio in (0.05, 0.2, 0.5, 0.99):
                c = rp.derive_caution(tau, ratio)
                self.assertTrue(0 < c < tau and c <= 0.01, (tau, ratio, c))     # inside every audit bound (0 < tau_mem < 0.05, <= 0.01)
        with self.assertRaises(rp.SiteConfigError):
            rp.derive_caution(1e-6)                              # would round to 0

    def test_rejects_malformed_configs(self):
        bad = [
            '{', '[]', '"x"', json.dumps({'hazard_threshold': 0.3}),                                   # no schema
            site_text(schema='other'), site_text(hazard_threshold=None),
            site_text(hazard_threshold=0), site_text(hazard_threshold=-0.1), site_text(hazard_threshold=1.01),
            site_text(hazard_threshold=True), site_text(hazard_threshold='0.3'),
            '{"schema": "rescuemind-site-1", "hazard_threshold": NaN}',
            '{"schema": "rescuemind-site-1", "hazard_threshold": Infinity}',
            '{"schema": "rescuemind-site-1", "hazard_threshold": 0.3, "hazard_threshold": 0.5}',      # duplicate key
            site_text(caution_ratio=1.0), site_text(caution_ratio=0), site_text(caution_ratio=-1), site_text(caution_ratio=True),
            site_text(hazard_prompt='h99'), site_text(hazard_views='all'), site_text(unknown=1),
            site_text(odom_frame=''), site_text(odom_frame='od om'), site_text(base_frame=5), site_text(base_frame='a' * 65),
        ]
        for text in bad:
            with self.subTest(text=text[:70]):
                with self.assertRaises(rp.SiteConfigError):
                    rp.parse_site_config(text)

    def test_load_from_file(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'site.json'
            f.write_text(site_text(odom_frame='odom', base_frame='base_footprint', caution_ratio=0.1))
            s = rp.load_site_config(f)
            self.assertEqual((s.odom_frame, s.base_frame, s.caution_ratio, s.caution_tau_h), ('odom', 'base_footprint', 0.1, 0.01))
            self.assertEqual(s.path, str(f))
            with self.assertRaises(rp.SiteConfigError):
                rp.load_site_config(Path(d) / 'missing.json')
            (Path(d) / 'bin.json').write_bytes(b'\xff\xfe')
            with self.assertRaises(rp.SiteConfigError):
                rp.load_site_config(Path(d) / 'bin.json')

    def test_resolve_conflicts_are_errors(self):
        self.assertEqual(rp.resolve('x', None, None, 0.05), 0.05)
        self.assertEqual(rp.resolve('x', 0.1, None, 0.05), 0.1)
        self.assertEqual(rp.resolve('x', None, 0.3, 0.05), 0.3)
        self.assertEqual(rp.resolve('x', 0.3, 0.3, 0.05), 0.3)
        self.assertEqual(rp.resolve('p', 'h35', 'h35', 'h36'), 'h35')
        with self.assertRaises(rp.SiteConfigError):
            rp.resolve('x', 0.05, 0.3, 0.05)                     # even the default value, when given explicitly, must agree
        with self.assertRaises(rp.SiteConfigError):
            rp.resolve('p', 'h36', 'h35', 'h36')

    def test_audit_kwargs_only_for_site_runs(self):
        self.assertEqual(rp.audit_kwargs({}), {})
        self.assertEqual(rp.audit_kwargs({'checkpoint': {}}), {})
        self.assertEqual(rp.audit_kwargs(None), {})
        self.assertEqual(rp.audit_kwargs({'site_config': {'hazard_threshold': 0.3}}), {'hazard_threshold': 0.3, 'require_threshold': True})
        for bad in ({}, {'hazard_threshold': None}, {'hazard_threshold': 0}, {'hazard_threshold': 2}, {'hazard_threshold': True},
                    {'hazard_threshold': math.nan}, 'x'):
            with self.assertRaises(ValueError):
                rp.audit_kwargs({'site_config': bad})

    def test_audit_uses_the_recorded_site_threshold(self):
        import test_i22_delivery_interlock as t22
        from rescuemind.local_run_audit import audit_local_checkpoint, LocalReceiptError
        with tempfile.TemporaryDirectory() as d:
            fx = t22.Fixture(Path(d), tau=t22.CAUTION_TAU_H, plan=t22.monotone_plan())
            calls = list(fx.cp['model_calls'].values()) + [c for pk in fx.cp['look_around']['peeks'] for c in pk['model_calls'].values()]
            for c in calls:
                c['scores']['hazard_threshold'] = 0.3                      # a server started with the site tau_h
            sha = fx.cp['image_sha256']
            with self.assertRaises(LocalReceiptError):                      # a normal (non-site) audit still insists on 0.05
                audit_local_checkpoint(fx.cp, sha, expected='water')
            rec = {'site_config': {'hazard_threshold': 0.3}}
            res = audit_local_checkpoint(fx.cp, sha, expected='water', **rp.audit_kwargs(rec))
            self.assertTrue(res['hazard_threshold_verified'])
            self.assertEqual(res['hazard_threshold'], 0.3)
            with self.assertRaises(LocalReceiptError):                      # the mission claims 0.3 but one call recorded 0.05
                calls[0]['scores']['hazard_threshold'] = 0.05
                audit_local_checkpoint(fx.cp, sha, expected='water', **rp.audit_kwargs(rec))

    def test_evidence_audits_call_through_audit_kwargs(self):
        for mod in ('run_completion', 'negative_evidence', 'recovery_evidence'):
            src = (ROOT / 'rescuemind' / (mod + '.py')).read_text(encoding='utf8')
            self.assertIn('audit_kwargs', src, mod)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


drive = load('rm_i26_mission', 'ros/gazebo_waypoint_mission.py')


class MissionCli(unittest.TestCase):
    """The mission node's argument handling (dry run: stops before any ROS import)."""
    def dry(self, *argv):
        buf, err = io.StringIO(), io.StringIO()
        with patch.object(sys, 'argv', ['m', *argv]), contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            try:
                drive.main()
            except SystemExit as e:
                return e.code, buf.getvalue(), err.getvalue()
        return None, buf.getvalue(), err.getvalue()

    def record(self, *argv):
        code, out, err = self.dry(*argv)
        self.assertIsNone(code, err)
        return json.loads(out[:out.rindex('}') + 1])

    def site(self, d, **kw):
        f = Path(d) / 'site.json'
        f.write_text(site_text(**kw))
        return str(f)

    def test_default_dry_run_record_has_no_new_keys(self):
        rec = self.record('--instruction', '避難所Bに飲料水を届けて')
        self.assertNotIn('site_config', rec)
        self.assertNotIn('real_profile', rec)

    def test_best_effort_camera_needs_the_system_clock_source(self):
        code, _, err = self.dry('--camera-qos', 'best_effort')
        self.assertEqual(code, 2)
        self.assertIn('real profile', err)
        self.assertIsNone(self.dry('--camera-qos', 'best_effort', '--clock-source', 'system')[0])

    def test_real_profile_is_recorded(self):
        rec = self.record('--clock-source', 'system', '--camera-qos', 'best_effort', '--odom-frame', 'odom', '--base-frame', 'base_footprint')
        self.assertEqual(rec['real_profile'], {'clock_source': 'system', 'camera_qos': 'best_effort',
                                               'odom_frame': 'odom', 'base_frame': 'base_footprint'})

    def test_site_config_is_recorded_and_supplies_the_frames(self):
        with tempfile.TemporaryDirectory() as d:
            rec = self.record('--site-config', self.site(d, odom_frame='odom', base_frame='base_footprint'))
            self.assertEqual(rec['site_config']['hazard_threshold'], 0.3)
            self.assertEqual(rec['site_config']['caution_tau_h'], 0.01)
            self.assertEqual(rec['real_profile']['base_frame'], 'base_footprint')
            self.assertEqual(rec['real_profile']['clock_source'], 'sim')

    def test_threshold_flag_must_agree_with_the_site_config(self):
        with tempfile.TemporaryDirectory() as d:
            f = self.site(d)
            self.assertIsNone(self.dry('--site-config', f, '--expected-hazard-threshold', '0.3')[0])
            code, _, err = self.dry('--site-config', f, '--expected-hazard-threshold', '0.05')
            self.assertEqual(code, 2)
            self.assertIn('conflicts with the site config', err)
            self.assertEqual(self.dry('--site-config', str(Path(d) / 'nope.json'))[0], 2)
            self.assertEqual(self.dry('--site-config', f, '--odom-frame', 'a b')[0], 2)

    def test_advice_with_a_non_default_caution_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            f = self.site(d, hazard_threshold=0.02)
            code, _, err = self.dry('--site-config', f, '--advice-from-instruction', '--advice-mode', 'monotone')
            self.assertEqual(code, 2)
            self.assertIn('advice', err)
            self.assertIsNone(self.dry('--site-config', f)[0])
            self.assertIsNone(self.dry('--site-config', self.site(d, hazard_threshold=0.3), '--advice-from-instruction',
                                       '--advice-mode', 'monotone')[0])

    def test_site_caution_reaches_the_memory_plan(self):
        with tempfile.TemporaryDirectory() as d:
            calls = []
            from rescuemind import mission_memory as mm
            real_plan = mm.MissionMemory.plan
            def spy(self_, *a, **kw):
                calls.append(kw)
                return real_plan(self_, *a, **kw)
            mem = Path(d) / 'mem.jsonl'
            mem.write_text('')
            with patch.object(mm.MissionMemory, 'plan', spy):
                self.record('--memory-file', str(mem), '--memory-mode', 'verified')
                self.record('--memory-file', str(mem), '--memory-mode', 'verified', '--site-config', self.site(d, hazard_threshold=0.02))
            self.assertNotIn('caution_tau_h', calls[0])               # default: the call is exactly the old one
            self.assertEqual(calls[1]['caution_tau_h'], 0.004)


class FakeNode:
    def __init__(self):
        self.handlers, self.qos, self.cmd, self.pose, self.stopped_calls = {}, {}, MotionCommand(0, 0), Pose2(0, 0, 0), 0

    def create_subscription(self, cls, topic, fn, qos):
        self.handlers[topic] = fn
        self.qos[topic] = qos
        return fn

    def create_publisher(self, cls, topic, qos):
        owner = self

        class Publisher:
            def publish(self, msg):
                owner.cmd = MotionCommand(msg.linear.x, msg.angular.z)
                if msg.linear.x == 0 and msg.angular.z == 0:
                    owner.stopped_calls += 1
        return Publisher()

    def destroy_node(self):
        pass


class Twist:
    def __init__(self):
        self.linear, self.angular = NS(x=0.), NS(z=0.)


TEXTURED = b''.join(bytes(((x * 3 + y * 2) % 240 + 8,) * 3) for y in range(320) for x in range(320))


class MissionWithFakeRos(unittest.TestCase):
    def run_mission(self, *, system, camera_lag_s=0.1, camera_bias_s=0.0, extra_args=None, stamp_style='ok',
                    odom_child='base_link', expect=None):
        fake, clock, real_sleep = FakeNode(), [0.], __import__('time').sleep
        rclpy = types.ModuleType('rclpy')
        rclpy.init = rclpy.shutdown = lambda: None
        rclpy.create_node = lambda name: fake

        def spin_once(node, timeout_sec=.1):
            clock[0] += .08
            node.pose = integrate(node.pose, node.cmd, .08)
            x, y, yaw = node.pose.x, node.pose.y, node.pose.yaw
            node.handlers['/odom'](NS(pose=NS(pose=NS(position=NS(x=x, y=y), orientation=NS(x=0., y=0., z=math.sin(yaw / 2), w=math.cos(yaw / 2)))),
                                      twist=NS(twist=NS(linear=NS(x=node.cmd.linear, y=0., z=0.), angular=NS(x=0., y=0., z=node.cmd.angular))),
                                      header=NS(frame_id='odom'), child_frame_id=odom_child))
            node.handlers['/scan'](NS(ranges=[3.] * 360, angle_min=-math.pi, angle_increment=2 * math.pi / 360, range_min=.08, range_max=10.))
            if '/clock' in node.handlers:                                   # simulation: the Gazebo clock runs one second ahead
                ct = clock[0] + 1 + camera_bias_s
                node.handlers['/clock'](NS(clock=NS(sec=int(ct), nanosec=int((ct % 1) * 1e9))))
                t = clock[0] + 1
            else:                                                           # real robot: stamps in Unix time
                t = UNIX0 + clock[0] - camera_lag_s
            if stamp_style == 'zero':
                stamp = NS(sec=0, nanosec=0)
            elif stamp_style == 'missing':
                stamp = None
            else:
                stamp = NS(sec=int(t), nanosec=int((t % 1) * 1e9))
            node.handlers['/camera'](NS(encoding='rgb8', width=320, height=320, step=960, data=TEXTURED, header=NS(stamp=stamp)))
            real_sleep(.0002)
        rclpy.spin_once = spin_once
        qos = ImageQos.fake_qos()['rclpy.qos']
        qos.qos_profile_sensor_data = 'SENSOR_DATA'
        rclpy.qos = qos
        mods = {'rclpy': rclpy, 'rclpy.qos': qos, 'geometry_msgs.msg': NS(Twist=Twist), 'nav_msgs.msg': NS(Odometry=object),
                'sensor_msgs.msg': NS(LaserScan=object, Image=object), 'std_msgs.msg': NS(Bool=object),
                'rosgraph_msgs.msg': NS(Clock=object)}
        args = NS(cmd_topic='/cmd_vel', odom_topic='/odom', scan_topic='/scan', estop_topic='/estop', camera_topic='/camera',
                  min_front_m=.27, scan_max_age=2.0, warmup=.1, stage_timeout=50., camera_wait=5., aim_timeout=14., settle_timeout=7.,
                  checkpoint_timeout=40., checkpoint_image='/tmp/rescuemind_i26_fake_ros_camera.jpg', camera_max_age=3.,
                  qwen_model='qwen3.8-omni-flash', qwen_endpoint='unused', inference_backend='cloud', local_mode='single',
                  local_primary_url='http://127.0.0.1:8765/v1/classify', local_secondary_url='http://127.0.0.1:8766/v1/classify')
        for k, v in (extra_args or {}).items():
            setattr(args, k, v)
        record = {'run_type': 'jev_qwen_live_mission', 'success': False, 'events': [], 'trace': [], 'checkpoint': None}

        def fake_verify(f, expected, *, qwen_model, endpoint):
            return {'decision': {'allow': True, 'reason': 'on_site_supply_confirmed'},
                    'image_sha256': __import__('hashlib').sha256(Path(f).read_bytes()).hexdigest(),
                    'model_calls': {'jev': {'model': 'jev-1.14.0'}, 'qwen': {'model': 'qwen3.8-omni-flash'}}}

        def fake_sleep(s):
            clock[0] += s
            real_sleep(.0001)
        route = [('supply_station', 'water', (0.50, 0)), ('shelter_approach', 'B', (1.0, 0))]
        with patch.dict(sys.modules, mods), \
                patch.object(drive.time, 'monotonic', side_effect=lambda: clock[0]), \
                patch.object(drive.time, 'sleep', side_effect=fake_sleep), \
                patch.object(drive.time, 'time_ns', side_effect=lambda: int((UNIX0 + clock[0]) * 1e9)), \
                patch('rescuemind.checkpoint.verify_station', side_effect=fake_verify):
            if expect is None:
                drive.run_ros(route, args, record)
            else:
                with self.assertRaisesRegex(*expect):
                    drive.run_ros(route, args, record)
        return fake, record

    def stages(self, rec):
        return [e['stage'] for e in rec['events']]

    # ---- the default is the simulation behaviour, untouched ----
    def test_default_subscribes_clock_with_reliable_camera_qos(self):
        # note: the simulation stub of test_v07 covers the full default mission; here only the wiring that I-26 touched
        fake, rec = self.run_mission(system=False, camera_lag_s=0)
        self.assertIn('/clock', fake.handlers)
        self.assertEqual(fake.qos['/camera']['reliability'], 'RELIABLE')
        self.assertTrue(rec['success'])
        self.assertIn('checkpoint_camera_sim_clock_verified', self.stages(rec))
        self.assertNotIn(rp.SYSTEM_CLOCK_STAGE, self.stages(rec))

    # ---- the real profile ----
    def test_system_clock_mission_runs_without_a_clock_topic_and_with_best_effort_camera(self):
        fake, rec = self.run_mission(system=True, extra_args={'clock_source': 'system', 'camera_qos': 'best_effort'})
        self.assertNotIn('/clock', fake.handlers)
        self.assertEqual(fake.qos['/camera']['reliability'], 'BEST_EFFORT')
        self.assertEqual(fake.qos['/camera']['depth'], 2)
        self.assertTrue(rec['success'])
        self.assertEqual([e['stage'] for e in rec['events'] if e.get('arrived')], ['supply_station', 'shelter_approach'])
        st = self.stages(rec)
        self.assertIn(rp.SYSTEM_CLOCK_STAGE, st)
        self.assertNotIn('checkpoint_camera_sim_clock_verified', st)
        # the freshness / stationarity checks are still in front of the decision
        self.assertLess(st.index('checkpoint_stationary_verified'), st.index('checkpoint_image_quality_verified'))
        self.assertLess(st.index(rp.SYSTEM_CLOCK_STAGE), st.index('checkpoint_frame'))
        self.assertLess(st.index('checkpoint_frame'), st.index('checkpoint_decision'))
        self.assertTrue(rp.audit_system_clock_capture(rec)['passed'])
        proof = next(e for e in rec['events'] if e['stage'] == rp.SYSTEM_CLOCK_STAGE)
        self.assertAlmostEqual(proof['camera_lag_to_system_clock_s'], 0.1, places=3)

    def test_system_clock_stale_camera_stamp_is_refused_before_inference(self):
        fake, rec = self.run_mission(system=True, camera_lag_s=2.0, extra_args={'clock_source': 'system'},
                                     expect=(CameraClockRejected, 'too_old_for_system_clock'))
        self.assertIsNone(rec['checkpoint'])
        self.assertNotIn('checkpoint_frame', self.stages(rec))

    def test_system_clock_ahead_camera_stamp_is_refused(self):
        self.run_mission(system=True, camera_lag_s=-1.0, extra_args={'clock_source': 'system'},
                         expect=(CameraClockRejected, 'ahead_of_system_clock'))

    def test_missing_or_zero_stamps_never_reach_inference(self):
        for style in ('zero', 'missing'):
            with self.subTest(style=style):
                fake, rec = self.run_mission(system=True, stamp_style=style, extra_args={'clock_source': 'system'},
                                             expect=(RuntimeError, 'ROS camera|camera watchdog'))
                self.assertIsNone(rec['checkpoint'])
                self.assertNotIn('checkpoint_frame', self.stages(rec))

    def test_wrong_odometry_frame_name_stops_the_mission(self):
        fake, rec = self.run_mission(system=True, odom_child='base_footprint',
                                     extra_args={'clock_source': 'system', 'odom_frame': 'odom', 'base_frame': 'base_link'},
                                     expect=(RuntimeError, 'watchdog during startup: invalid_odometry_frames'))
        self.assertFalse(rec['success'])
        self.assertGreater(fake.stopped_calls, 3)

    def test_configured_odometry_frame_names_are_accepted(self):
        fake, rec = self.run_mission(system=True, odom_child='robot/base_footprint',
                                     extra_args={'clock_source': 'system', 'odom_frame': 'odom', 'base_frame': 'base_footprint'})
        self.assertTrue(rec['success'])


class DefaultCommandLines(unittest.TestCase):
    """The registered studies run the orchestrator with defaults: none of the I-26 flags may appear."""
    FLAGS = ('--site-config', '--clock-source', '--camera-qos', '--odom-frame', '--base-frame', '--real-profile')

    def joined(self, plan):
        return ' '.join(' '.join(map(str, s.argv)) for s in plan['services']) + ' ' + ' '.join(plan['mission'].argv)

    def test_default_and_option_laden_plans_contain_no_new_flag(self):
        for kw in ({}, {'delivery_interlock': True, 'adaptive_views': 0.8, 'hazard_threshold': 0.3, 'hazard_prompt': 'h35'},
                   {'memory_file': '/x/m.jsonl', 'memory_mode': 'verified', 'caution_soft': True, 'advice_scrutiny': True}):
            plan = orch.build_plan('live', '避難所Bに飲料水を届けて', mission_timeout=900, evidence_dir=Path('/tmp/abcdef0123456789'), **kw)
            text = self.joined(plan)
            for f in self.FLAGS:
                self.assertNotIn(f, text, (kw, f))

    def test_site_config_is_passed_to_the_mission_only_when_given(self):
        plan = orch.build_plan('live', 'x', mission_timeout=900, evidence_dir=Path('/tmp/abcdef0123456789'), site_config='/s/site.json')
        self.assertIn("--site-config /s/site.json", self.joined(plan))

    def run_main(self, *argv):
        buf, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            try:
                orch.main(list(argv))
            except SystemExit as e:
                return e.code, buf.getvalue(), err.getvalue()
        return None, buf.getvalue(), err.getvalue()

    def test_one_site_json_sets_the_same_tau_h_for_server_mission_and_interlock(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'site.json'
            f.write_text(site_text())
            code, out, err = self.run_main('--plan', '--scenario', 'live', '--delivery-interlock', '--site-config', str(f))
            self.assertIsNone(code, err)
            plan = json.loads(out)
            server = next(s for s in plan['services'] if 'local_vlm_server' in ' '.join(s))
            interlock = next(s for s in plan['services'] if 'delivery_interlock.py' in ' '.join(s))
            mission = ' '.join(plan['mission'])
            self.assertIn('--hazard-threshold 0.3 --hazard-views tiles --hazard-prompt h35', ' '.join(server))
            self.assertIn('--hazard-threshold 0.3', ' '.join(interlock))
            self.assertIn('--expected-hazard-threshold 0.3', mission)
            self.assertIn('--site-config ' + str(f), mission)
            code, _, err = self.run_main('--plan', '--scenario', 'live', '--site-config', str(f), '--hazard-threshold', '0.05')
            self.assertEqual(code, 2)
            self.assertIn('conflicts', err)
            code, _, err = self.run_main('--plan', '--scenario', 'live', '--site-config', str(f), '--hazard-prompt', 'h36')
            self.assertEqual(code, 2)

    def test_cli_defaults_still_resolve_to_v36(self):
        captured = {}

        def fake_build_plan(*a, **kw):
            captured.update(kw)
            raise SystemExit(0)
        with patch.object(orch, 'build_plan', fake_build_plan):
            self.run_main('--plan', '--scenario', 'live')
        self.assertEqual((captured['hazard_threshold'], captured['hazard_views'], captured['hazard_prompt']), (0.05, 'tiles', 'h36'))
        self.assertNotIn('site_config', captured)


class ServerAndInterlockCli(unittest.TestCase):
    def server_args(self, *argv):
        mod = load('rm_i26_server', 'scripts/local_vlm_server.py')
        seen = {}

        class Worker:
            DESCRIBE_PROMPTS = mod.ModelWorker.DESCRIBE_PROMPTS
            INTENT_PROMPTS = mod.ModelWorker.INTENT_PROMPTS

            def __init__(self, *a, **kw):
                seen['worker'] = self

        class Http:
            def __init__(self, *a, **kw):
                pass

            def serve_forever(self):
                pass
        err = io.StringIO()
        with patch.object(sys, 'argv', ['s', *argv]), patch.object(mod, 'ModelWorker', Worker), \
                patch.object(mod, 'ThreadingHTTPServer', Http), patch.object(mod, 'make_handler', lambda w: None), \
                contextlib.redirect_stderr(err):
            try:
                mod.main()
            except SystemExit as e:
                return e.code, err.getvalue(), None
        w = seen['worker']
        return None, '', (w.hazard_threshold, w.hazard_views, w.hazard_prompt)

    def test_server_defaults_are_unchanged(self):
        self.assertEqual(self.server_args()[2], (0.5, 'full', 'h35'))
        self.assertEqual(self.server_args('--hazard-threshold', '0.05', '--hazard-views', 'tiles', '--hazard-prompt', 'h36')[2],
                         (0.05, 'tiles', 'h36'))

    def test_server_takes_the_site_values_and_refuses_a_conflict(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'site.json'
            f.write_text(site_text())
            self.assertEqual(self.server_args('--site-config', str(f))[2], (0.3, 'tiles', 'h35'))
            self.assertEqual(self.server_args('--site-config', str(f), '--hazard-threshold', '0.3')[2], (0.3, 'tiles', 'h35'))
            code, err, _ = self.server_args('--site-config', str(f), '--hazard-threshold', '0.5')
            self.assertEqual(code, 2)
            self.assertIn('conflicts', err)
            f.write_text(site_text(hazard_prompt=None, hazard_views=None))
            self.assertEqual(self.server_args('--site-config', str(f), '--hazard-views', 'full')[2], (0.3, 'full', 'h35'))

    def interlock_threshold(self, *argv):
        import rescuemind.delivery_interlock as di
        seen = {}

        def policy(**kw):
            seen.update(kw)
            raise RuntimeError('stop')                      # before any ROS import: the policy is built first inside run()
        err = io.StringIO()
        fake_rclpy = types.ModuleType('rclpy')
        mods = {'rclpy': fake_rclpy, 'rclpy.node': NS(Node=object), 'std_msgs.msg': NS(String=object)}
        with patch.object(sys, 'argv', ['i', *argv]), patch.object(di, 'Policy', policy), patch.dict(sys.modules, mods), \
                contextlib.redirect_stderr(err):
            try:
                runpy.run_path(str(ROOT / 'ros/delivery_interlock.py'), run_name='__main__')
            except SystemExit as e:
                return e.code, err.getvalue()
            except RuntimeError:
                return seen['hazard_threshold'], ''
        raise AssertionError('interlock did not start')

    def test_interlock_default_and_site(self):
        self.assertEqual(self.interlock_threshold()[0], 0.05)
        self.assertEqual(self.interlock_threshold('--hazard-threshold', '0.07')[0], 0.07)
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'site.json'
            f.write_text(site_text())
            self.assertEqual(self.interlock_threshold('--site-config', str(f))[0], 0.3)
            code, err = self.interlock_threshold('--site-config', str(f), '--hazard-threshold', '0.05')
            self.assertEqual(code, 2)
            self.assertIn('conflicts', err)

    def test_guard_parser_defaults_and_real_profile_gate(self):
        src = (ROOT / 'ros/guarded_cmd_relay.py').read_text(encoding='utf8')
        for needle in ("'--real-profile'", "'--camera-qos'", "'--odom-frame'", "'--base-frame'", "'--site-config'", 'guard_settings'):
            self.assertIn(needle, src)
        # best_effort without --real-profile is refused before any ROS node exists
        err = io.StringIO()
        with patch.object(sys, 'argv', ['g', '--camera-qos', 'best_effort']), contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit) as cm:
                runpy.run_path(str(ROOT / 'ros/guarded_cmd_relay.py'), run_name='__main__')
        self.assertEqual(cm.exception.code, 2)
        self.assertIn('real-profile', err.getvalue())


if __name__ == '__main__':
    unittest.main()
