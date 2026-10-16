"""Focused regressions for v1.6, isolated from actual ROS/API credentials."""
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import patch
from rescuemind.odom_health import OdomHealth
from rescuemind.velocity_relay import VelocityRelay
from rescuemind.run_completion import validate, CompletionError

ROOT=Path(__file__).resolve().parents[1]

def odom(stamp=123_000_000_000, x=1.0, w=1.0, frame='odom', child='base_link'):
    return N(header=N(stamp=N(sec=stamp//10**9,nanosec=stamp%10**9),frame_id=frame),
             child_frame_id=child,
             pose=N(pose=N(position=N(x=x,y=2.0,z=0.0), orientation=N(x=0.0,y=0.0,z=0.0,w=w))))

class TestRuntimeOdom(unittest.TestCase):
    def test_valid_and_advancing_odometry(self):
        c=OdomHealth()
        self.assertIsNone(c.observe(odom()))
        self.assertIsNone(c.observe(odom(stamp=124_000_000_000,x=1.1)))
        self.assertEqual(c.last_position,(1.1,2.,0.))
    def test_fail_closed_invalid_cases(self):
        cases=[(odom(x=float('nan')),'invalid_odom_numeric'),(odom(w=0),'invalid_odom_quaternion'),
               (odom(frame='map'),'invalid_odom_frames'),(odom(child='wheel'),'invalid_odom_frames'),
               (odom(stamp=0),'invalid_odom_timestamp'),(N(), 'malformed_odom'),
               (odom(x=True),'invalid_odom_numeric')]
        for msg,reason in cases:
            with self.subTest(reason=reason):
                self.assertEqual(OdomHealth().observe(msg),reason)
    def test_replay_regressions(self):
        c=OdomHealth();self.assertIsNone(c.observe(odom()))
        self.assertEqual(c.observe(odom()),'repeated_odom_timestamp')
        c=OdomHealth();c.observe(odom())
        self.assertEqual(c.observe(odom(stamp=122_000_000_000)), 'regressed_odom_timestamp')
    def test_invalid_payload_latches_speed_guard(self):
        c=VelocityRelay(started_at=0.0)
        c.odometry(.3, odom(x=float('nan')))
        self.assertEqual(c.decide(.31).reason, 'invalid_odom_numeric')
        self.assertEqual(c.decide(.31).linear,0.)
        c.odometry(.32,odom())
        self.assertEqual(c.decide(.33).reason,'invalid_odom_numeric')

class TestCompletionReceipt(unittest.TestCase):
    def record(self, run_type='motion_check_non_ai'):
        return {'run_id':'a'*16,'run_type':run_type,'success':True,'events':[
                {'stage':'supply_station','arrived':True},
                {'stage':'shelter_approach','arrived':True}]}
    def save(self,path,obj):path.write_text(json.dumps(obj),encoding='utf-8')
    def test_valid_motion_check_not_claimed_as_ai(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'mission.json';self.save(p,self.record())
            rec=validate(p,'motion-check','a'*16)
            self.assertFalse(rec['robot_motion_independently_verified'])
            self.assertEqual(rec['scenario'],'motion-check')
    def test_wrong_run_id_fails(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'mission.json';self.save(p,self.record())
            with self.assertRaisesRegex(CompletionError,'run_id'):validate(p,'motion-check','b'*16)
    def test_no_success_or_bad_order_fails(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'mission.json';obj=self.record();obj['success']=False;self.save(p,obj)
            with self.assertRaisesRegex(CompletionError,'successful'):validate(p,'motion-check')
            obj=self.record();obj['events'].reverse();self.save(p,obj)
            with self.assertRaisesRegex(CompletionError,'ordered'):validate(p,'motion-check')
    def test_no_record_fails(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(CompletionError,'missing mission'):validate(Path(td)/'not.json','motion-check')
    def test_synthetic_live_log_requires_dual_model_audit(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'mission.json'
            obj=self.record('jev_qwen_live_mission')
            obj['checkpoint']={'decision':{'allow':True,'reason':'on_site_supply_confirmed'}}
            obj['events'].insert(1,{'stage':'checkpoint_frame'})
            obj['events'].insert(2,{'stage':'checkpoint_decision'})
            self.save(p,obj)
            with patch('scripts.audit_robot_run.audit',return_value={'automated_pass':True}):
                self.assertEqual(validate(p,'live','a'*16)['software_log_validation'],'PASS')
            with patch('scripts.audit_robot_run.audit',return_value={'automated_pass':False}):
                with self.assertRaisesRegex(CompletionError,'full Jev/Qwen'):validate(p,'live','a'*16)
    def test_exit_zero_cannot_fabricate_receipt(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'mission.json'
            p.write_text('{"success":true}')
            with self.assertRaises(CompletionError):validate(p,'motion-check')
    def test_v16_launcher_plan_does_not_require_ros(self):
        cp=subprocess.run([sys.executable,str(ROOT/'scripts/v16_orchestrate.py'), '--plan','--scenario','live'],
                          capture_output=True,text=True,timeout=15)
        self.assertEqual(cp.returncode,0,cp.stderr)
        self.assertEqual(json.loads(cp.stdout)['scenario'],'live')
    def test_orchestrator_includes_run_id_and_guard(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('orchv16',ROOT/'scripts/v16_orchestrate.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        plan=m.build_plan('live','避難所Bに水',mission_timeout=400,evidence_dir=Path('/tmp/'+'a'*16))
        self.assertIn('--run-id',plan['mission'].argv[-1])
        self.assertIn('/rescuemind/cmd_vel_request', (ROOT/'ros/gazebo_waypoint_mission.py').read_text())

if __name__=='__main__':unittest.main()
