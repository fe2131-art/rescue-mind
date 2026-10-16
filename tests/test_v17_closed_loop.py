import math
import unittest
from rescuemind.closed_loop_twin import simulate, fake_odom, fake_camera, fake_scan

class ClosedLoopScenarioTests(unittest.TestCase):
    def test_nominal_finishes_twice(self):
        for _ in range(2):
            r=simulate('nominal')
            self.assertTrue(r.mission_completed,r.terminal_reason)
            self.assertTrue(r.station_reached)
            self.assertEqual(r.simulated_ai_calls,1)
            self.assertTrue(r.shelter_reached)
    def test_scripted_ai_denial_blocks_second_leg(self):
        r=simulate('ai_denied')
        self.assertTrue(r.station_reached)
        self.assertFalse(r.shelter_reached)
        self.assertIn('scripted_ai_denied',r.terminal_reason)
    def test_faults_never_complete(self):
        for s in ('lidar_block','command_loss','camera_freeze','odom_freeze'):
            with self.subTest(s=s):
                r=simulate(s)
                self.assertFalse(r.mission_completed,r.as_dict())
                self.assertFalse(r.shelter_reached)
                self.assertIn('guard_latched',r.terminal_reason)
                self.assertIsNotNone(r.stop_delay_s)
                self.assertLessEqual(r.stop_delay_s,2.2)
    def test_zero_velocity_for_denied(self):
        r=simulate('ai_denied')
        self.assertEqual(r.simulated_ai_calls,1)
        self.assertFalse(r.mission_completed)
    def test_repeatability(self):
        self.assertEqual(simulate('nominal').as_dict(),simulate('nominal').as_dict())
    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):simulate('made_up')
        for d in (0,0.5,float('nan')):
            with self.assertRaises(ValueError):simulate('nominal',dt=d)
