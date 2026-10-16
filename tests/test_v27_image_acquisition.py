"""Deterministic synthetic images; no Gazebo and no real VLM inference."""
from __future__ import annotations
import unittest
from PIL import Image
from types import SimpleNamespace as NS
from rescuemind.image_acquisition import (CheckpointAcquisitionGate, AcquisitionRejected, measure_quality)
from rescuemind.vision import image_from_ros_msg


def frame(stamp=11, style='textured', enc='rgb8', padding=0, truncate=0):
    w,h=320,240
    def pixel(x,y):
        v= (x*5+y*3)%200+20 if style=='textured' else (0 if style=='black' else 255 if style=='white' else 128)
        return bytes((v,v,v))
    data=b''.join(b''.join(pixel(x,y) for x in range(w))+b'\0'*padding for y in range(h))
    if truncate:data=data[:-truncate]
    return NS(width=w,height=h,encoding=enc,step=w*3+padding,data=data,
              header=NS(stamp=NS(sec=stamp,nanosec=0)))

class QualityTests(unittest.TestCase):
    def test_textured(self):
        q=measure_quality(image_from_ros_msg(frame()))
        self.assertTrue(q['quality_ok']);self.assertGreater(q['p99_luma']-q['p01_luma'],100)
    def test_blackout(self):
        self.assertIn('camera_blackout',measure_quality(image_from_ros_msg(frame(style='black')))['reasons'])
    def test_whiteout(self):
        self.assertIn('camera_whiteout',measure_quality(image_from_ros_msg(frame(style='white')))['reasons'])
    def test_flat_gray(self):
        self.assertIn('camera_flat_frame',measure_quality(image_from_ros_msg(frame(style='gray')))['reasons'])
    def test_padding(self):
        self.assertTrue(measure_quality(image_from_ros_msg(frame(padding=8)))['quality_ok'])
    def test_truncation(self):
        with self.assertRaises(ValueError):image_from_ros_msg(frame(truncate=1))
    def test_extra_payload_rejected(self):
        m=frame();m.data += b'EXTRA'
        with self.assertRaises(ValueError):image_from_ros_msg(m)
    def test_bad_resolution(self):
        with self.assertRaises(AcquisitionRejected):measure_quality(Image.new('RGB',(100,100)))

class CheckpointTwoFrameTests(unittest.TestCase):
    def gate(self):return CheckpointAcquisitionGate(10_000_000_000,12.5)
    def test_two_fresh(self):
        g=self.gate()
        self.assertFalse(g.observe(frame(11),12.1))  # callback before post-stationary dwell
        self.assertFalse(g.observe(frame(11),12.6))
        self.assertTrue(g.observe(frame(12),12.9))
        self.assertEqual(g.report()['distinct_frames'],2)
        self.assertGreaterEqual(g.report()['capture_gap_wall_s'],.15)
    def test_old_stamp(self):
        g=self.gate()
        self.assertFalse(g.observe(frame(10),12.7))
        self.assertEqual(len(g.accepted),0)
    def test_duplicate_stamp(self):
        g=self.gate()
        self.assertFalse(g.observe(frame(11),12.6))
        self.assertFalse(g.observe(frame(11),12.9))
        self.assertEqual(len(g.accepted),1)
    def test_min_gap(self):
        g=self.gate()
        g.observe(frame(11),12.6)
        self.assertFalse(g.observe(frame(12),12.7))
        self.assertTrue(g.observe(frame(13),12.9))
    def test_reversed_stamp(self):
        g=self.gate();g.observe(frame(12),12.6)
        with self.assertRaisesRegex(AcquisitionRejected,'regressed'):
            g.observe(frame(11),13.)
    def test_first_black_fails_without_cherry_picking(self):
        g=self.gate()
        with self.assertRaisesRegex(AcquisitionRejected,'blackout'):
            g.observe(frame(11,'black'),12.6)
        self.assertIsNone(g.frame)
    def test_second_white_fails_without_cherry_picking(self):
        g=self.gate();g.observe(frame(11),12.6)
        with self.assertRaisesRegex(AcquisitionRejected,'whiteout'):
            g.observe(frame(12,'white'),12.9)
        self.assertIsNone(g.frame)
    def test_oversized_dimensions_fail_without_decode(self):
        g=self.gate();m=frame(11);m.width=10_000_000
        with self.assertRaisesRegex(AcquisitionRejected,'dimensions'):
            g.observe(m,12.6)
    def test_oversized_stride_fail_without_decode(self):
        g=self.gate();m=frame(11);m.step=99999999
        with self.assertRaisesRegex(AcquisitionRejected,'stride'):
            g.observe(m,12.6)
    def test_invalid_payload(self):
        g=self.gate()
        with self.assertRaisesRegex(AcquisitionRejected,'malformed'):
            g.observe(frame(11,truncate=100),12.6)
    def test_invalid_clock(self):
        with self.assertRaises(AcquisitionRejected):self.gate().observe(frame(11),float('nan'))
    def test_evidence_not_ready(self):
        g=self.gate();g.observe(frame(11),12.6)
        with self.assertRaisesRegex(AcquisitionRejected,'two_fresh'):
            g.report()
    def test_invalid_ros_stamp(self):
        m=frame();m.header.stamp.sec=-2
        with self.assertRaisesRegex(AcquisitionRejected,'invalid_checkpoint_stamp'):
            self.gate().observe(m,12.6)

class IntegrationContract(unittest.TestCase):
    def test_wired_before_jev(self):
        from pathlib import Path
        s=(Path(__file__).resolve().parents[1]/'ros/gazebo_waypoint_mission.py').read_text()
        self.assertLess(s.index('image_gate.report()'),s.index('def inference():'))
        self.assertLess(s.index('image_gate.frame.save'),s.index('def inference():'))
        self.assertIn('CheckpointAcquisitionGate(stamp_at_arrival,first_frame_after)',s)

if __name__=='__main__':unittest.main()
