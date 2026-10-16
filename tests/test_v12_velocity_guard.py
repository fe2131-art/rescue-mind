"""Deterministic simulation tests for a separate watchdog process, not Gazebo tests."""
import math
import unittest
from types import SimpleNamespace as N
from rescuemind.velocity_relay import VelocityRelay


def image(t):
    return N(header=N(stamp=N(sec=int(t),nanosec=int((t%1)*1e9))))


def scan(distance=3.0):
    return N(ranges=[distance]*360,angle_min=-math.pi,
             angle_increment=2*math.pi/360,range_min=.08,range_max=10.)


def healthy(t=0.3):
    r=VelocityRelay(0.)
    r.odometry(t)
    r.camera_frame(image(t),t)
    r.laser_scan(scan(),t)
    return r


class TestGuard(unittest.TestCase):
    def test_new_guard_outputs_zero(self):
        r=VelocityRelay(0.)
        d=r.decide(.1)
        self.assertEqual((d.linear,d.angular),(0,0))
        self.assertFalse(d.ready)

    def test_fresh_input_passes(self):
        r=healthy()
        r.request(.19,.2,.4)
        d=r.decide(.41)
        self.assertTrue(d.ready)
        self.assertAlmostEqual(d.linear,.19)
        self.assertAlmostEqual(d.angular,.2)

    def test_missing_request_does_not_enable_motion(self):
        r=healthy()
        d=r.decide(.4)
        self.assertTrue(d.ready)
        self.assertEqual(d.linear,0)

    def test_lost_mission_command_aborts_and_latches(self):
        r=healthy()
        r.request(.19,0,.4)
        d=r.decide(.86)
        self.assertEqual(d.reason,'stale_velocity_command')
        self.assertEqual(d.linear,0)
        r.request(.1,0,.90)
        self.assertEqual(r.decide(.91).linear,0)

    def test_sensor_freeze_stops_even_with_cmd_updates(self):
        for missing in ('camera','scan','odom'):
            with self.subTest(missing=missing):
                r=healthy()
                r.request(.1,0,2.4)
                if missing!='camera':r.camera_frame(image(2.4),2.4)
                if missing!='scan':r.laser_scan(scan(),2.4)
                if missing!='odom':r.odometry(2.4)
                d=r.decide(2.41)
                self.assertFalse(d.ready)
                self.assertEqual(d.linear,0)

    def test_close_object_stops(self):
        r=healthy()
        r.laser_scan(scan(.22),.4)
        r.request(.1,0,.41)
        self.assertIn('front_obstacle',r.decide(.42).reason)
        self.assertEqual(r.decide(.42).linear,0.)

    def test_lidar_inf_is_no_hit(self):
        r=healthy()
        r.laser_scan(scan(math.inf),.4)
        r.request(.1,0,.45)
        self.assertAlmostEqual(r.decide(.46).linear,.1)

    def test_nan_scan_aborts(self):
        r=healthy()
        r.laser_scan(scan(math.nan),.4)
        self.assertFalse(r.decide(.41).ready)

    def test_estop_latches(self):
        r=healthy()
        r.request(.1,0,.4)
        r.emergency_stop(True)
        self.assertEqual(r.decide(.41).reason,'operator_estop')
        r.emergency_stop(False)
        self.assertEqual(r.decide(.42).linear,0)

    def test_nonfinite_velocity_aborts(self):
        for invalid in (float('nan'),float('inf'),float('-inf')):
            with self.subTest(invalid=invalid):
                r=healthy()
                r.request(invalid,0,.4)
                self.assertFalse(r.decide(.41).ready)

    def test_overlimit_velocity_aborts(self):
        r=healthy()
        r.request(.301,0,.4)
        self.assertEqual(r.decide(.41).reason,'request_exceeds_speed_limit')

    def test_camera_duplicate_stamp_stops(self):
        r=healthy()
        r.camera_frame(image(.3),1.5)
        r.laser_scan(scan(),2.31)
        r.odometry(2.31)
        r.request(0.1,0,2.31)
        self.assertIn('camera_',r.decide(2.32).reason)

    def test_guard_clock_regression(self):
        r=healthy()
        r.request(.1,0,-1.)
        self.assertFalse(r.decide(.4).ready)

    def test_invalid_config_rejected(self):
        for cfg in [{'cmd_max_age_s':0},{'max_linear':float('nan')},{'camera_max_age_s':-1}]:
            with self.subTest(cfg=cfg),self.assertRaises(ValueError):
                VelocityRelay(0.,**cfg)

    def test_very_many_request_freshness_boundaries(self):
        for age_ms in range(0,650,5):
            r=healthy()
            r.camera_frame(image(.6),.6)
            r.laser_scan(scan(),.6)
            r.odometry(.6)
            r.request(.10,0,.6)
            t=.6+age_ms/1000
            d=r.decide(t)
            if age_ms>450:
                self.assertFalse(d.ready)
                self.assertEqual(d.linear,0)
            else:
                self.assertTrue(d.ready)
                self.assertEqual(d.linear,.1)
