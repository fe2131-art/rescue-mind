"""Unit/property checks for simulation-only camera liveness monitor."""
import math
import unittest
from types import SimpleNamespace as NS
from rescuemind.camera_watch import CameraWatch


def image(t):
    return NS(header=NS(stamp=NS(sec=int(t),nanosec=int((t%1)*1_000_000_000))))


class TestCameraWatch(unittest.TestCase):
    def test_healthy_stream(self):
        w=CameraWatch(0.,max_age_s=2.,startup_grace_s=1.)
        for n in range(1,20):
            w.observe(image(n), float(n))
            self.assertIsNone(w.check(n+.4))
    def test_startup_heartbeat_missing(self):
        w=CameraWatch(0.,max_age_s=2.,startup_grace_s=1.)
        self.assertIsNone(w.check(.9))
        self.assertEqual(w.check(1.1),'no_camera_frames')
        w.observe(image(4),4.0)
        self.assertEqual(w.check(4.1),'no_camera_frames')
    def test_camera_freeze_even_when_duplicates_arrive(self):
        w=CameraWatch(0.,max_age_s=1.5)
        w.observe(image(1),1.)
        for t in (1.3,1.8,2.1,2.5):
            w.observe(image(1),t)
        self.assertEqual(w.check(2.51),'stale_camera_frames')
    def test_new_timestamp_refreshes(self):
        w=CameraWatch(0.,max_age_s=1.5)
        w.observe(image(1),1.)
        w.observe(image(2),2.1)
        self.assertIsNone(w.check(3.5))
        self.assertEqual(w.check(3.61),'stale_camera_frames')
    def test_timestamp_regression_latched(self):
        w=CameraWatch(0.);w.observe(image(4),1.);w.observe(image(3),1.2)
        self.assertEqual(w.latched_reason,'regressed_camera_stamp')
    def test_invalid_timestamp_latched(self):
        w=CameraWatch(0.);w.observe(image(0),1.)
        self.assertEqual(w.check(1.2),'invalid_camera_stamp')
    def test_bad_configuration(self):
        for setting in (-1,0,float('nan'),float('inf')):
            with self.subTest(setting=setting),self.assertRaises(ValueError):
                CameraWatch(0.,max_age_s=setting)
    def test_backward_clock_rejected(self):
        w=CameraWatch(100.);w.observe(image(2),99.)
        self.assertEqual(w.check(101.),'invalid_camera_clock')
    def test_gap_at_boundary(self):
        w=CameraWatch(0.,max_age_s=2.)
        w.observe(image(1),1.)
        self.assertIsNone(w.check(3.))
        self.assertEqual(w.check(3.00001),'stale_camera_frames')


if __name__=='__main__':unittest.main()
