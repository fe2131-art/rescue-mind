"""Pure-python adversarial acquisition timestamp checks (no ROS required)."""
import unittest
from types import SimpleNamespace as NS
from rescuemind.frame_freshness import frame_stamp_ns,FrameSequence

def img(sec=1,nsec=0):
    return NS(header=NS(stamp=NS(sec=sec,nanosec=nsec)))

class TestFrameFreshness(unittest.TestCase):
    def test_valid_stamp_and_missing_header(self):
        self.assertEqual(frame_stamp_ns(img(5,125)),5_000_000_125)
        self.assertIsNone(frame_stamp_ns(NS()))
        self.assertIsNone(frame_stamp_ns(img(0,0)))
        self.assertIsNone(frame_stamp_ns(img(1,1_000_000_000)))
        self.assertIsNone(frame_stamp_ns(img(-1,0)))
    def test_stale_queued_image_is_not_accepted(self):
        f=FrameSequence();f.observe(img(4))
        anchor=f.last_stamp_ns
        f.observe(img(4))
        self.assertFalse(f.eligible(anchor, 21.,20.))
        f.observe(img(5))
        self.assertFalse(f.eligible(anchor,19.,20.))
        self.assertTrue(f.eligible(anchor,21.,20.))
    def test_regression_latched_even_after_fresh(self):
        f=FrameSequence();f.observe(img(5));anchor=f.last_stamp_ns
        f.observe(img(4));f.observe(img(6))
        self.assertTrue(f.invalid_or_regressed)
        self.assertFalse(f.eligible(anchor,21.,20.))
    def test_bad_header_latched(self):
        f=FrameSequence();f.observe(img(10));f.observe(NS());self.assertTrue(f.invalid_or_regressed)
    def test_same_frame_at_station_rejected(self):
        f=FrameSequence();f.observe(img(8));self.assertFalse(f.eligible(f.last_stamp_ns,200,100))
if __name__=='__main__':unittest.main()
