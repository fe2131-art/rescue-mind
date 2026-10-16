"""Offline kinematic tests only, NOT a Gazebo execution proof."""
import importlib.util
import json
import math
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from rescuemind.waypoint import Pose2, WaypointController, integrate, simulate_route, yaw_from_quaternion, wrap
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('rm_direct',ROOT/'ros/gazebo_waypoint_mission.py')
mission=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mission)

class TestDirectController(unittest.TestCase):
    def test_control_reaches_predefined_route(self):
        d=json.loads((ROOT/'configs/gazebo_waypoints.json').read_text())
        for item in ('water','medicine'):
            r=simulate_route([d[item], d['B']]);self.assertTrue(r['arrived'])
            self.assertLess(math.hypot(r['final'][0]-d['B'][0],r['final'][1]-d['B'][1]),.23)
            self.assertEqual(r['kind'],'ideal_kinematic_regression_not_gazebo')
    def test_turn_in_place_before_moving(self):
        x=WaypointController().command(Pose2(0,0,0),(-1,0))
        self.assertEqual(x.linear,0);self.assertNotEqual(x.angular,0)
    def test_at_goal_stop(self):
        x=WaypointController().command(Pose2(1,1,0),(1.01,1.02))
        self.assertTrue(x.arrived);self.assertEqual((x.linear,x.angular),(0,0))
    def test_angle_wrap(self):
        self.assertAlmostEqual(wrap(4*math.pi),0,places=5)
        self.assertAlmostEqual(wrap(-math.pi/2),-math.pi/2,places=5)
    def test_quaternion_yaw(self):
        a=1.17
        self.assertAlmostEqual(yaw_from_quaternion(0,0,math.sin(a/2),math.cos(a/2)),a,places=6)
    def test_bad_pose_and_orientation(self):
        for pose in ((math.inf,1,1),(0,math.nan,1)):
            with self.assertRaises(ValueError):Pose2(*pose)
        with self.assertRaises(ValueError):yaw_from_quaternion(0,0,0,0)
    def test_bad_goal(self):
        with self.assertRaises(ValueError):WaypointController().command(Pose2(0,0,0),(math.nan,1))
        with self.assertRaises(ValueError):WaypointController(speed=-1)
    def test_route_and_claim(self):
        r=mission.route_from_config(ROOT/'configs/gazebo_waypoints.json','water')
        self.assertEqual(len(r),2);self.assertEqual(r[0][0],'supply_station')
        self.assertEqual(r[1][0],'shelter_approach')
        with self.assertRaises(ValueError):mission.route_from_config(ROOT/'configs/gazebo_waypoints.json','toy')
    def test_stale_image_denied(self):
        with tempfile.TemporaryDirectory() as t:
            f=Path(t)/'frame.jpg';f.write_bytes(b'X'*2000)
            with patch.object(mission.time,'time',return_value=f.stat().st_mtime+121):
                with self.assertRaisesRegex(RuntimeError,'stale'):mission.fresh_image(f)
    @unittest.skipIf(importlib.util.find_spec('rclpy') is not None,
                     'ROS 2 is installed; the live Gazebo runs cover this path')
    def test_missing_ros_never_claims_success(self):
        r={'events':[], 'success':False}
        with self.assertRaises((RuntimeError, ModuleNotFoundError)):
            mission.run_ros([('supply_station','water',[1,1])],None,r)
        self.assertFalse(r['success'])

if __name__=='__main__':unittest.main()
