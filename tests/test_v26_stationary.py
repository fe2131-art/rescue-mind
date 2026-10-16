from __future__ import annotations
import copy
import math
import unittest
from types import SimpleNamespace as NS
from rescuemind.waypoint import Pose2
from rescuemind.stationary_gate import StationaryGate, MotionUnstable, odom_planar_twist
from rescuemind.v26_stationary_evidence import audit_stationarity, StationaryEvidenceError


def odom(lin=0.0,ang=0.0,off_axis=0.):
    return NS(twist=NS(twist=NS(linear=NS(x=lin,y=0.,z=0.),angular=NS(x=off_axis,y=0.,z=ang))))

def events():
    return {'run_type':'jev_qwen_live_mission','run_id':'1234567890abcdef','events':[
        {'stage':'camera_aim_aligned','t_wall_s':10.0},
        {'stage':'checkpoint_stationary_verified','t_wall_s':10.9,
         'stable_elapsed_s':0.7,'sample_count':5,'reset_count':1,
         'max_linear_mps':.025,'max_angular_rps':.055,
         'max_drift_m':.02,'max_yaw_drift_rad':.04},
        {'stage':'checkpoint_frame','t_wall_s':11.7,'image_sha256':'a'*64},
        {'stage':'checkpoint_decision','t_wall_s':12.3,'allow':False}]}

class StationaryGateTests(unittest.TestCase):
    def test_stable_requires_time_and_distinct_samples(self):
        gate=StationaryGate()
        self.assertFalse(gate.observe(Pose2(0,0,0),0,0,1.))
        for t in (1.1,1.2,1.3,1.4):self.assertFalse(gate.observe(Pose2(0,0,0),0,0,t))
        self.assertTrue(gate.observe(Pose2(0,0,0),0,0,1.7))
        self.assertEqual(gate.report()['sample_count'],6)
    def test_wheel_coasting_blocks_lock(self):
        gate=StationaryGate()
        for t in (1.,1.2,1.4,1.8,2.,2.2):
            self.assertFalse(gate.observe(Pose2(0,0,0),0.11,0,t))
    def test_rotation_coasting_blocks_lock(self):
        gate=StationaryGate()
        for t in (1.,1.2,1.4,1.8):
            self.assertFalse(gate.observe(Pose2(0,0,0),0,0.2,t))
    def test_small_motion_accepted(self):
        gate=StationaryGate()
        for idx,t in enumerate((1,1.2,1.4,1.8)):
            gate.observe(Pose2(idx*.003,0,idx*.003),.01,.01,t)
        self.assertTrue(gate.locked)
    def test_drift_resets_hold(self):
        gate=StationaryGate()
        for t in (1,1.2,1.4):gate.observe(Pose2(0,0,0),0,0,t)
        self.assertFalse(gate.observe(Pose2(.03,0,0),0,0,2.0))
        self.assertEqual(gate.resets,1)
    def test_yaw_wrap(self):
        gate=StationaryGate()
        for t,yaw in ((1,math.pi-.01),(1.3,-math.pi+.001),(1.5,-math.pi+.005),(1.8,math.pi-.008)):
            gate.observe(Pose2(0,0,yaw),0,0,t)
        self.assertTrue(gate.locked)
    def test_movement_after_lock_rejected(self):
        gate=StationaryGate()
        for t in (1,1.2,1.4,1.8):gate.observe(Pose2(0,0,0),0,0,t)
        with self.assertRaisesRegex(MotionUnstable,'physical_motion'):
            gate.observe(Pose2(.07,0,0),0,0,2.0)
    def test_rotation_after_lock_rejected(self):
        gate=StationaryGate()
        for t in (1,1.2,1.4,1.8):gate.observe(Pose2(0,0,0),0,0,t)
        with self.assertRaises(MotionUnstable):gate.observe(Pose2(0,0,0.1),0,0,2.)
    def test_nonadvancing_clock_rejected(self):
        gate=StationaryGate();gate.observe(Pose2(0,0,0),0,0,1.)
        with self.assertRaises(MotionUnstable):gate.observe(Pose2(0,0,0),0,0,1.)
    def test_bad_numeric_rejected(self):
        with self.assertRaises(MotionUnstable):StationaryGate().observe(Pose2(0,0,0),float('nan'),0,1)
    def test_odom_twist_uses_body_velocity(self):
        self.assertEqual(odom_planar_twist(odom(.10,.20)),(.10,.20))
    def test_odom_twist_fails_missing(self):
        with self.assertRaises(MotionUnstable):odom_planar_twist(NS())
    def test_odom_twist_rejects_axis_velocity(self):
        self.assertAlmostEqual(odom_planar_twist(odom(0,0,off_axis=.15))[1],.15)
    def test_odom_twist_fails_nonfinite(self):
        with self.assertRaises(MotionUnstable):odom_planar_twist(odom(lin=float('nan')))
    def test_stationary_report_fails_without_lock(self):
        with self.assertRaises(MotionUnstable):StationaryGate().report()

class StationaryEvidenceTests(unittest.TestCase):
    def test_receipt_valid(self):self.assertTrue(audit_stationarity(events())['passed'])
    def test_missing(self):
        obj=events();obj['events'].pop(1)
        with self.assertRaises(StationaryEvidenceError):audit_stationarity(obj)
    def test_duplicate(self):
        obj=events();obj['events'].insert(1,copy.deepcopy(obj['events'][1]))
        with self.assertRaises(StationaryEvidenceError):audit_stationarity(obj)
    def test_inverted_order(self):
        obj=events();obj['events'][1],obj['events'][2]=obj['events'][2],obj['events'][1]
        with self.assertRaises(StationaryEvidenceError):audit_stationarity(obj)
    def test_too_soon_image(self):
        obj=events();obj['events'][2]['t_wall_s']=11.1
        with self.assertRaises(StationaryEvidenceError):audit_stationarity(obj)
    def test_weak_stability(self):
        obj=events();obj['events'][1]['max_drift_m']=.40
        with self.assertRaises(StationaryEvidenceError):audit_stationarity(obj)
    def test_invalid_image_digest(self):
        obj=events();obj['events'][2]['image_sha256']='fake'
        with self.assertRaises(StationaryEvidenceError):audit_stationarity(obj)
    def test_missing_decision(self):
        obj=events();obj['events'][3].pop('allow')
        with self.assertRaises(StationaryEvidenceError):audit_stationarity(obj)
    def test_fake_nonlive(self):
        obj=events();obj['run_type']='motion_check_non_ai'
        with self.assertRaises(StationaryEvidenceError):audit_stationarity(obj)
    def test_integration_wired_both_denial_and_approval(self):
        from pathlib import Path
        text=(Path(__file__).resolve().parents[1]/'scripts/v22_orchestrate.py').read_text()
        self.assertEqual(text.count("audit_stationarity(log_dir/'mission.json')"),2)

if __name__=='__main__': unittest.main()
