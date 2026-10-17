"""I-21: the mission node's recovery search over k stations, run through the real run_ros with simulated ROS messages
(ideal kinematics, mocked checkpoint model; NOT Gazebo)."""
import hashlib
import importlib.util
import json
import math
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind.waypoint import Pose2, MotionCommand, integrate  # noqa: E402
from rescuemind.stations import StationSet  # noqa: E402
import rescuemind.local_vision  # noqa: E402,F401  (imported before the sys.modules patch, or the patch target is stale)

spec = importlib.util.spec_from_file_location('rm_i21', ROOT / 'ros/gazebo_waypoint_mission.py')
drive = importlib.util.module_from_spec(spec); spec.loader.exec_module(drive)

FRAME = b''.join(bytes(((x * 3 + y * 2) % 240 + 8,) * 3) for y in range(320) for x in range(320))
WRONG, HAZARD, OK = ('local_vlm_disagree_or_wrong_supply', False), ('visible_hazard_at_checkpoint', False), ('on_site_supply_confirmed', True)

INV4 = {'W1': 'water', 'M1': 'medicine', 'W2': 'water', 'M2': 'medicine'}
WP4 = {'initial': [0, 0], 'W1': [0.5, 0.0], 'W2': [0.5, 0.7], 'M1': [0.0, 0.7], 'M2': [-0.5, 0.0], 'B': [1.0, 0.0],
       'physical_pickup': False}
CT4 = {'W1': [2, 2], 'W2': [2, -2], 'M1': [-2, 2], 'M2': [-2, -2]}


class Twist:
    def __init__(self): self.linear = NS(x=0.); self.angular = NS(z=0.)


class FakeNode:
    def __init__(self): self.handlers = {}; self.cmd = MotionCommand(0, 0); self.pose = Pose2(0, 0, 0)
    def create_subscription(self, cls, topic, fn, qos): self.handlers[topic] = fn; return fn
    def create_publisher(self, cls, topic, qos):
        owner = self
        class Pub:
            def publish(self, msg): owner.cmd = MotionCommand(msg.linear.x, msg.angular.z)
        return Pub()
    def destroy_node(self): pass


def run(order, verdicts, *, stations=None, recovery=True, first=None, config=None, centers=None, memory=None, extra_args=None):
    """Run the mission over `order` (candidate order) with one verdict per on-site check, in call order."""
    fake, clock, real_sleep = FakeNode(), [0.], time.sleep
    rclpy = types.ModuleType('rclpy'); rclpy.init = lambda: None; rclpy.shutdown = lambda: None; rclpy.create_node = lambda n: fake
    record = {'run_type': 'local_vlm_live_mission', 'success': False, 'events': [], 'trace': [], 'checkpoint': None,
              'intent': {'item': 'water'}}
    if memory is not None:
        record['memory'] = memory
    if stations is not None:
        record['stations'] = stations.to_block(); record['station_order'] = list(order)

    def spin_once(node, timeout_sec=.1):
        clock[0] += .08
        node.pose = integrate(node.pose, node.cmd, .08)
        x, y, yaw = node.pose.x, node.pose.y, node.pose.yaw
        node.handlers['/odom'](NS(pose=NS(pose=NS(position=NS(x=x, y=y), orientation=NS(x=0., y=0., z=math.sin(yaw / 2), w=math.cos(yaw / 2)))),
                                  twist=NS(twist=NS(linear=NS(x=node.cmd.linear, y=0., z=0.), angular=NS(x=0., y=0., z=node.cmd.angular)))))
        node.handlers['/scan'](NS(ranges=[3.] * 360, angle_min=-math.pi, angle_increment=2 * math.pi / 360, range_min=.08, range_max=10.))
        ct = clock[0] + 1
        node.handlers['/clock'](NS(clock=NS(sec=int(ct), nanosec=int((ct % 1) * 1e9))))
        node.handlers['/camera'](NS(encoding='rgb8', width=320, height=320, step=960, data=FRAME,
                                    header=NS(stamp=NS(sec=int(clock[0]) + 1, nanosec=int((clock[0] % 1) * 1e9)))))
        real_sleep(.0002)
    rclpy.spin_once = spin_once
    qos = types.ModuleType('rclpy.qos'); qos.qos_profile_sensor_data = object(); qos.QoSProfile = lambda **kw: kw
    qos.ReliabilityPolicy = qos.HistoryPolicy = qos.DurabilityPolicy = NS(RELIABLE=1, KEEP_LAST=1, VOLATILE=1)
    rclpy.qos = qos
    typesmap = {'rclpy': rclpy, 'rclpy.qos': qos, 'geometry_msgs.msg': NS(Twist=Twist), 'nav_msgs.msg': NS(Odometry=object),
                'sensor_msgs.msg': NS(LaserScan=object, Image=object), 'std_msgs.msg': NS(Bool=object),
                'rosgraph_msgs.msg': NS(Clock=object)}
    calls = []

    def fake_local(f, expected, *, mode, primary_url, secondary_url, primary_model=None):
        reason, allow, *more = verdicts[len(calls)]
        calls.append(expected)
        return {'decision': {'allow': allow, 'reason': reason, 'expected': expected}, 'backend': 'OFFLINE_MOCK_ONLY',
                'image_sha256': hashlib.sha256(Path(f).read_bytes()).hexdigest(), **(more[0] if more else {})}

    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        cfgp, ctp = d / 'w.json', d / 'c.json'
        cfgp.write_text(json.dumps(config or WP4)); ctp.write_text(json.dumps(centers or CT4))
        args = NS(cmd_topic='/cmd_vel', odom_topic='/odom', scan_topic='/scan', estop_topic='/estop', camera_topic='/camera',
                  min_front_m=.27, scan_max_age=2.0, warmup=.1, stage_timeout=50., camera_wait=5., aim_timeout=14.,
                  settle_timeout=7., checkpoint_timeout=40., checkpoint_image=str(d / 'checkpoint.jpg'), camera_max_age=3.,
                  inference_backend='local', local_mode='single', local_primary_url='http://127.0.0.1:8765/v1/classify',
                  local_secondary_url='http://127.0.0.1:8766/v1/classify', recovery=recovery,
                  config=str(cfgp), centers=str(ctp) if centers != 'default' else None, **(extra_args or {}))
        wp = json.loads(cfgp.read_text())
        route = [('supply_station', order[0], tuple(wp[order[0]])), ('shelter_approach', 'B', tuple(wp['B']))]
        error = None
        with patch.dict(sys.modules, typesmap), patch.object(drive.time, 'monotonic', side_effect=lambda: clock[0]), \
                patch.object(drive.time, 'sleep', side_effect=lambda s: (clock.__setitem__(0, clock[0] + s), real_sleep(.0001))), \
                patch('rescuemind.local_vision.verify_station_local', side_effect=fake_local):
            try:
                drive.run_ros(route, args, record)
            except RuntimeError as e:
                error = str(e)
        record['_files'] = sorted(p.name for p in d.iterdir())
    record['_calls'] = calls
    return record, error


def checks(record):
    """Stations at which an on-site check was made, in order (arrival events 'supply_station' / 'recovery_supply_station')."""
    return [e['target'] for e in record['events'] if e.get('stage') in ('supply_station', 'recovery_supply_station') and e.get('arrived')]


SS4 = StationSet.build(['W1', 'M1', 'W2', 'M2'], INV4)


class RecoveryOverFourStations(unittest.TestCase):
    def test_three_wrong_then_confirmed_visits_every_candidate_in_order(self):
        r, err = run(SS4.order('water'), [WRONG, WRONG, WRONG, OK], stations=SS4)
        self.assertIsNone(err); self.assertTrue(r['success'])
        self.assertEqual(checks(r), ['W1', 'W2', 'M1', 'M2'])
        self.assertEqual(r['checkpoint_station'], 'M2')
        rec = r['recovery']
        self.assertEqual((rec['first_station'], rec['searched_station'], rec['candidates']), ('W1', 'M2', ['W1', 'W2', 'M1', 'M2']))
        self.assertEqual([h['station'] for h in rec['hops']], ['W2', 'M1'])
        self.assertEqual(r['_calls'], ['water'] * 4)                                  # the request never changes
        self.assertEqual([e['stage'] for e in r['events']].count('recovery_search_started'), 3)
        self.assertEqual([e['to'] for e in r['events'] if e['stage'] == 'recovery_search_started'], ['W2', 'M1', 'M2'])
        self.assertEqual(rec['first_checkpoint_image'], 'recovery_checkpoint.jpg')
        self.assertEqual([h['checkpoint_image'] for h in rec['hops']], ['recovery2_checkpoint.jpg', 'recovery3_checkpoint.jpg'])
        for name in ['recovery_checkpoint.jpg', 'recovery2_checkpoint.jpg', 'recovery3_checkpoint.jpg', 'checkpoint.jpg']:
            self.assertIn(name, r['_files'])
        self.assertEqual([e['target'] for e in r['events'] if e.get('stage') == 'shelter_approach'], ['B'])

    def test_all_four_wrong_stops_and_reports_after_k_checks(self):
        r, err = run(SS4.order('water'), [WRONG] * 5, stations=SS4)
        self.assertIn('checkpoint DENIED', err); self.assertFalse(r['success'])
        self.assertEqual(checks(r), ['W1', 'W2', 'M1', 'M2'])
        self.assertEqual(len(r['_calls']), 4)                         # k checks, not k + 1, and no shelter leg
        self.assertEqual(r['checkpoint_station'], 'M2')
        self.assertFalse(r['checkpoint']['decision']['allow'])

    def test_hazard_at_any_visited_station_stops(self):
        r, err = run(SS4.order('water'), [WRONG, HAZARD, OK, OK], stations=SS4)
        self.assertIn('checkpoint DENIED: visible_hazard_at_checkpoint', err)
        self.assertEqual(checks(r), ['W1', 'W2']); self.assertEqual(len(r['_calls']), 2)
        self.assertEqual(r['recovery']['searched_station'], 'W2')

    def test_without_recovery_flag_the_first_denial_stops(self):
        r, err = run(SS4.order('water'), [WRONG, OK], stations=SS4, recovery=False)
        self.assertIn('DENIED', err); self.assertEqual(checks(r), ['W1']); self.assertNotIn('recovery', r)

    def test_memory_reordered_candidates_are_followed_without_skipping(self):
        order = SS4.order('water', first='M2')
        r, err = run(order, [WRONG, WRONG, WRONG, OK], stations=SS4)
        self.assertIsNone(err)
        self.assertEqual(checks(r), order)

    def test_first_station_confirms_without_recovery(self):
        r, err = run(SS4.order('water'), [OK], stations=SS4)
        self.assertIsNone(err); self.assertNotIn('recovery', r); self.assertEqual(checks(r), ['W1'])
        self.assertEqual(r['_files'].count('recovery_checkpoint.jpg'), 0)


class ArenaUnchanged(unittest.TestCase):
    """k = 2: the one-time 'check the other station' search, exactly as before."""
    CFG = {'initial': [0, 0], 'water': [0.5, 0.0], 'medicine': [-0.5, 0.0], 'B': [1.0, 0.0], 'physical_pickup': False}
    CT = {'water': [2, 2], 'medicine': [-2, 2]}

    def go(self, verdicts, order=('water', 'medicine')):
        return run(list(order), verdicts, config=self.CFG, centers=self.CT)

    def test_wrong_then_ok(self):
        r, err = self.go([WRONG, OK])
        self.assertIsNone(err); self.assertEqual(checks(r), ['water', 'medicine'])
        rec = r['recovery']
        self.assertEqual((rec['first_station'], rec['searched_station']), ('water', 'medicine'))
        self.assertNotIn('hops', rec); self.assertNotIn('stations', r); self.assertNotIn('station_order', r)

    def test_wrong_wrong_stops_after_two_checks(self):
        r, err = self.go([WRONG, WRONG, OK])
        self.assertIn('checkpoint DENIED: local_vlm_disagree_or_wrong_supply', err)
        self.assertEqual(checks(r), ['water', 'medicine']); self.assertEqual(len(r['_calls']), 2)
        self.assertNotIn('hops', r['recovery'])

    def test_memory_first_medicine(self):
        r, err = self.go([WRONG, OK], order=('medicine', 'water'))
        self.assertIsNone(err); self.assertEqual(checks(r), ['medicine', 'water'])


if __name__ == '__main__':
    unittest.main()
