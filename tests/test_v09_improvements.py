"""v0.9 regression tests: fail closed at on-site hazard and stalled drive.
All tests run without Gazebo, network, Jev or Qwen endpoints.
"""
from __future__ import annotations
import copy
import importlib.util
import json
import tempfile
from pathlib import Path
import unittest
from rescuemind.checkpoint import decide_checkpoint
from rescuemind.progress_watch import ProgressWatch
from rescuemind.waypoint import Pose2

ROOT=Path(__file__).resolve().parents[1]

def good_pair():
    j={'model':'jev-1.14.0','real_model':True,'supply':'water',
       'supply_confidence':.94,'supply_present_probability':.96,
       'hazard_probability':.06,'scene':'unknown'}
    q={'model':'qwen3.8-omni-flash','real_model':True,'supply':'water','scene':'unknown'}
    return j,q

class TestV09Safety(unittest.TestCase):
    def test_correct_station_and_no_visible_hazard_can_pass(self):
        j,q=good_pair();r=decide_checkpoint('water',j,q)
        self.assertTrue(r.allow);self.assertEqual(r.reason,'on_site_supply_confirmed')
    def test_jev_visible_hazard_is_veto_even_if_items_agree(self):
        j,q=good_pair();j['hazard_probability']=.95
        self.assertEqual(decide_checkpoint('water',j,q).reason,'visible_hazard_at_checkpoint')
    def test_qwen_visible_hazard_is_veto(self):
        j,q=good_pair();q['scene']='hazard'
        self.assertEqual(decide_checkpoint('water',j,q).reason,'visible_hazard_at_checkpoint')
    def test_jev_scene_hazard_veto_even_if_low_numeric_hazard(self):
        j,q=good_pair();j['scene']='hazard';self.assertFalse(decide_checkpoint('water',j,q).allow)
    def test_missing_or_malformed_safety_evidence_veto(self):
        for v in (None,'bad',float('nan'),float('inf'),-0.3,1.1):
            j,q=good_pair()
            if v is None:j.pop('hazard_probability')
            else:j['hazard_probability']=v
            with self.subTest(v=v):
                self.assertEqual(decide_checkpoint('water',j,q).reason,'missing_or_invalid_hazard_observation')
    def test_invalid_scene_veto(self):
        for key in ('jev','qwen'):
            j,q=good_pair();(j if key=='jev' else q)['scene']='surprisingly_safe'
            self.assertFalse(decide_checkpoint('water',j,q).allow)
    def test_threshold_boundary(self):
        j,q=good_pair();j['hazard_probability']=.35
        self.assertFalse(decide_checkpoint('water',j,q).allow)
    def test_box_not_collision_clearance(self):
        j,q=good_pair();j['scene']='unknown';q['scene']='unknown'
        self.assertTrue(decide_checkpoint('water',j,q).allow)
        self.assertNotIn('corridor_safe',decide_checkpoint('water',j,q).to_dict())

class TestV09Progress(unittest.TestCase):
    def test_sustained_forward_stall_is_latched(self):
        w=ProgressWatch(max_stall_s=3.)
        p=Pose2(0,0,0)
        self.assertIsNone(w.update(p,.2,0.))
        self.assertIsNone(w.update(p,.2,3.))
        self.assertEqual(w.update(p,.2,3.01),'drive_commanded_but_no_translation')
        self.assertEqual(w.update(Pose2(1,0,0),0.,8.),'drive_commanded_but_no_translation')
    def test_turn_in_place_not_counted_as_stall(self):
        w=ProgressWatch(max_stall_s=2.)
        for t in range(10):self.assertIsNone(w.update(Pose2(0,0,t/10),0.,t))
    def test_reset_when_translation_succeeds(self):
        w=ProgressWatch(max_stall_s=2.)
        self.assertIsNone(w.update(Pose2(0,0,0),.2,0))
        self.assertIsNone(w.update(Pose2(.1,0,0),.2,1))
        self.assertIsNone(w.update(Pose2(.2,0,0),.2,2.1))
    def test_zero_command_resets_partial_stall(self):
        w=ProgressWatch(max_stall_s=2.)
        w.update(Pose2(0,0,0),.2,0)
        w.update(Pose2(0,0,0),0,1.9)
        self.assertIsNone(w.update(Pose2(0,0,0),.2,3.))
    def test_non_finite_and_time_regression_fail_closed(self):
        w=ProgressWatch();w.update(Pose2(0,0,0),.2,5.)
        self.assertEqual(w.update(Pose2(0,0,0),.2,4.),'clock_regression')
        self.assertEqual(ProgressWatch().update(Pose2(0,0,0),float('nan'),0.),'invalid_drive_progress_input')
    def test_fake_evidence_requires_two_models_and_recomputed_decision(self):
        spec=importlib.util.spec_from_file_location('audit_v09',ROOT/'scripts/audit_robot_run.py')
        audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
        j,q=good_pair()
        d=decide_checkpoint('water',j,q).to_dict()
        record={'run_type':'jev_qwen_live_mission','intent':{'item':'water'},'intent_gate':{'allow':True},'preflight':None,
                'checkpoint':{'image_sha256':'f'*64,'model_calls':{'jev':j,'qwen':q},'decision':d},
                'events':[{'stage':'supply_station','arrived':True,'t_wall_s':3},
                          {'stage':'checkpoint_frame','image_sha256':'f'*64,'t_wall_s':4},
                          {'stage':'checkpoint_decision','allow':True,'t_wall_s':6},
                          {'stage':'shelter_approach','arrived':True,'t_wall_s':13}],
                'trace':[{'x':1},{'x':2}], 'success':True,'physical_pickup':False}
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'evidence.json'
            def run(rec):f.write_text(json.dumps(rec));return audit.audit(f)
            self.assertTrue(run(record)['automated_pass'])
            bad=copy.deepcopy(record);bad['checkpoint']['model_calls']['qwen'].pop('real_model')
            self.assertFalse(run(bad)['automated_pass'])
            bad=copy.deepcopy(record);bad['checkpoint']['decision']['jev_hazard']=.8
            self.assertFalse(run(bad)['automated_pass'])
            bad=copy.deepcopy(record);bad['events'][1]['t_wall_s']=18
            self.assertFalse(run(bad)['automated_pass'])

if __name__=='__main__':unittest.main()
