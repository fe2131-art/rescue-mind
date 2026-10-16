"""ROS-independent time-domain tests, including altered audit receipts."""
import copy,math,unittest
from types import SimpleNamespace as NS
from rescuemind.camera_clock_gate import CameraClockGate,CameraClockRejected
from rescuemind.v28_clock_evidence import audit_clock_capture,ClockEvidenceError

def msg(sec=5,nsec=0):return NS(header=NS(stamp=NS(sec=sec,nanosec=nsec)))
def good_gate():
 g=CameraClockGate()
 for j in range(4):g.clock(10+j,0,10+j)
 return g

def example():
 return {'run_type':'jev_qwen_live_mission','events':[
  {'stage':'checkpoint_stationary_verified','t_wall_s':2.},
  {'stage':'checkpoint_image_quality_verified','t_wall_s':2.7,'ros_stamps_ns':[11_000_000_000,12_800_000_000]},
  {'stage':'checkpoint_camera_sim_clock_verified','t_wall_s':2.7,'basis':'Gazebo_clock_vs_camera_ROS_stamp',
   'sim_clock_ns':13_000_000_000,'camera_ros_stamp_ns':12_800_000_000,
   'camera_lag_to_sim_clock_s':.2,'clock_callback_idle_s':.08,'clock_progress_idle_s':.08,'clock_advances':5,
   'limits_s':{'max_lag':1.2,'max_lead':.25,'max_clock_idle':.9}},
  {'stage':'checkpoint_frame','t_wall_s':2.8,'ros_acquisition_stamp_ns':12_800_000_000},
  {'stage':'checkpoint_decision','t_wall_s':4.,'allow':True}]}

class GateTests(unittest.TestCase):
 def test_recent_frame_ok(self):
  g=good_gate();r=g.check_frame(msg(12,700_000_000),13.1)
  self.assertEqual(r['camera_lag_to_sim_clock_s'],.3)
 def test_old_but_increasing_frame(self):
  with self.assertRaisesRegex(CameraClockRejected,'too_old'):
   good_gate().check_frame(msg(11,0),13.1)
 def test_ahead_stamp(self):
  with self.assertRaisesRegex(CameraClockRejected,'ahead'):
   good_gate().check_frame(msg(14,0),13.1)
 def test_stopped_clock(self):
  with self.assertRaisesRegex(CameraClockRejected,'stalled'):
   good_gate().check_frame(msg(12,900_000_000),14.3)
 def test_clock_regresses(self):
  with self.assertRaisesRegex(CameraClockRejected,'rewound'):
   good_gate().clock(11,0,13.1)
 def test_duplicate_clock_not_advance(self):
  g=CameraClockGate()
  for t in (1.,1.1,1.2):g.clock(2,0,t)
  with self.assertRaisesRegex(CameraClockRejected,'not_advancing'):
   g.check_frame(msg(2,0),1.3)
 def test_repeated_sim_clock_without_progress_stalls(self):
  g=good_gate()
  for t in (13.2,13.5,14.):g.clock(13,0,t)
  with self.assertRaisesRegex(CameraClockRejected,'stalled'):
   g.check_frame(msg(12,900_000_000),14.1)
 def test_missing_clock(self):
  with self.assertRaisesRegex(CameraClockRejected,'no_gazebo_clock'):
   CameraClockGate().check_frame(msg(3),5.)
 def test_bad_ros_nsec(self):
  with self.assertRaisesRegex(CameraClockRejected,'invalid_camera_ros_stamp'):
   good_gate().check_frame(msg(12,-1),13.1)
 def test_bad_receive_time(self):
  with self.assertRaisesRegex(CameraClockRejected,'invalid_frame_receive_time'):
   good_gate().check_frame(msg(13),float('nan'))
 def test_clock_wall_regression(self):
  with self.assertRaisesRegex(CameraClockRejected,'clock_callback_time_nonadvancing'):
   good_gate().clock(14,0,12.9)
 def test_config_rejects_nan(self):
  with self.assertRaises(CameraClockRejected):CameraClockGate(max_camera_lag_s=float('nan'))

class EvidenceTests(unittest.TestCase):
 def test_good_receipt(self):self.assertTrue(audit_clock_capture(example())['passed'])
 def mutate_and_fail(self,mutate,reason):
  receipt=example();mutate(receipt)
  with self.assertRaisesRegex(ClockEvidenceError,reason):audit_clock_capture(receipt)
 def test_missing(self):self.mutate_and_fail(lambda x:x['events'].pop(2),'missing_or_duplicate')
 def test_reordered(self):self.mutate_and_fail(lambda x:x['events'].reverse(),'out_of_order')
 def test_fake_lag(self):self.mutate_and_fail(lambda x:x['events'][2].update(camera_lag_to_sim_clock_s=0.),'inconsistent')
 def test_stale_image(self):self.mutate_and_fail(lambda x:x['events'][2].update(sim_clock_ns=15_000_000_000,camera_lag_to_sim_clock_s=2.2),'not_near')
 def test_future_image(self):self.mutate_and_fail(lambda x:x['events'][2].update(sim_clock_ns=12_000_000_000,camera_lag_to_sim_clock_s=-.8),'not_near')
 def test_stale_clock(self):self.mutate_and_fail(lambda x:x['events'][2].update(clock_callback_idle_s=1.5),'stale')
 def test_clock_progress_stalled_receipt(self):self.mutate_and_fail(lambda x:x['events'][2].update(clock_progress_idle_s=1.3),'clock_progress_stalled')
 def test_fake_clock_limit(self):self.mutate_and_fail(lambda x:x['events'][2]['limits_s'].update(max_lag=15.),'weakened')
 def test_false_frame_stamp(self):self.mutate_and_fail(lambda x:x['events'][3].update(ros_acquisition_stamp_ns=100),'disagrees')
 def test_clock_not_advancing(self):self.mutate_and_fail(lambda x:x['events'][2].update(clock_advances=0),'not_advanced')
 def test_nonfinite(self):self.mutate_and_fail(lambda x:x['events'][2].update(camera_lag_to_sim_clock_s=float('nan')),'inconsistent')
 def test_live_only(self):self.mutate_and_fail(lambda x:x.update(run_type='motion_check_non_ai'),'not_live')
 def test_supervisor_both_branches(self):
  from pathlib import Path
  base=Path(__file__).resolve().parents[1]
  s=(base/'scripts/v22_orchestrate.py').read_text()
  self.assertEqual(s.count("outcome['gazebo_camera_clock_evidence']=audit_clock_capture"),2)
  source=(base/'ros/gazebo_waypoint_mission.py').read_text()
  self.assertIn("node.create_subscription(Clock,'/clock'",source)
  self.assertLess(source.index('last_clock_proof=clock_gate.check_frame'),source.index('def inference():'))
if __name__=='__main__':unittest.main()
