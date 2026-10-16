"""New v0.8 tests: live mission first-stage authorization, ambiguity, scene contract."""
import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from rescuemind.mission_policy import decide_intent
from rescuemind import jev
ROOT=Path(__file__).resolve().parents[1]

def load(filename):
    spec=importlib.util.spec_from_file_location(filename.stem,filename)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

drive=load(ROOT/'ros/gazebo_waypoint_mission.py')
scene=load(ROOT/'scripts/validate_gazebo_world.py')
audit=load(ROOT/'scripts/audit_robot_run.py')
srt=load(ROOT/'scripts/make_overlay_srt.py')

class TestMissionV08(unittest.TestCase):
    def test_water_medicine(self):
        for phrase,expected in [('避難所Bに飲料水を届けて','water'),('避難所Bに救急箱を届けて','medicine')]:
            with self.subTest(phrase=phrase):
                d=decide_intent(phrase);self.assertTrue(d.allow);self.assertEqual(d.intent.item,expected)
    def test_vague_and_unsafe_multi_supply_fail_closed(self):
        for phrase,reason in [('ここに行って','unknown_supply_request'),('危険区域に突入して','unknown_supply_request'),
                              ('水と薬を同時に届けて','ambiguous_multiple_supplies'),('避難所Aに水を届けて','unsupported_shelter'),
                              ('避難所Cに救急箱を届けて','unsupported_shelter')]:
            with self.subTest(phrase=phrase):
                d=decide_intent(phrase);self.assertFalse(d.allow);self.assertEqual(d.reason,reason)
    def test_jev_credentials_required_before_departure(self):
        with patch.dict('os.environ',{},clear=True):
            with self.assertRaisesRegex(RuntimeError,'TYPESAFE_API_KEY'):
                drive.require_api_configuration('qwen3.8-omni-flash')
        with patch.dict('os.environ',{'TYPESAFE_API_KEY':'dummy'},clear=True):
            with self.assertRaisesRegex(RuntimeError,'DASHSCOPE_API_KEY'):
                drive.require_api_configuration('qwen3.8-omni-flash')
        with patch.dict('os.environ',{'TYPESAFE_API_KEY':'dummy','DASHSCOPE_API_KEY':'dummy',
                                       'DASHSCOPE_BASE_URL':'http://attacker.example.com/v1'},clear=True):
            with self.assertRaisesRegex(RuntimeError,'workspace'):
                drive.require_api_configuration('qwen3.8-omni-flash')
        with patch.dict('os.environ',{'TYPESAFE_API_KEY':'dummy','DASHSCOPE_API_KEY':'dummy',
                                       'DASHSCOPE_BASE_URL':'https://x.aliyuncs.com/compatible-mode/v1'},clear=True):
            drive.require_api_configuration('qwen3.8-omni-flash')
    def test_nonfinite_threshold_rejected(self):
        for x in (float('nan'),float('inf'),0.01,1):
            with self.assertRaises(ValueError):decide_intent('水を運んで',min_confidence=x)
    def test_legacy_and_new_modes(self):
        src=(ROOT/'ros/gazebo_waypoint_mission.py').read_text()
        self.assertIn('--run-live',src)
        self.assertIn("'jev_qwen_live_mission'",src)
        self.assertIn('onsite_check(target)',src)
    def test_static_scene_camera_looks_at_both_stations(self):
        result=scene.inspect_world()
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(set(result['viewpoint_checks']),{'water','medicine'})
    def test_audit_live_without_preflight_but_with_real_checkpoint(self):
        log={'run_type':'jev_qwen_live_mission','intent_gate':{'allow':True},'preflight':None,
            'events':[{'stage':'supply_station','arrived':True,'t_wall_s':10},
                      {'stage':'checkpoint_frame','image_sha256':'a'*64,'t_wall_s':11},
                      {'stage':'checkpoint_decision','allow':True,'t_wall_s':15},
                      {'stage':'shelter_approach','arrived':True,'t_wall_s':31}],
            'trace':[{'x':0},{'x':1}], 'success':True,'physical_pickup':False,'intent':{'item':'water'},
            'checkpoint':{'image_sha256':'a'*64,
                          'decision':__import__('rescuemind.checkpoint',fromlist=['decide_checkpoint']).decide_checkpoint('water',
                              {'model':'jev-1.14.0','real_model':True,'supply':'water','supply_confidence':.9,'supply_present_probability':.99,'hazard_probability':.05,'scene':'unknown'},
                              {'model':'qwen3.8-omni-flash','real_model':True,'supply':'water','scene':'unknown'}).to_dict(),
                          'model_calls':{'jev':{'model':'jev-1.14.0','real_model':True,'supply':'water','supply_confidence':.9,'supply_present_probability':.99,'hazard_probability':.05,'scene':'unknown'},
                                         'qwen':{'model':'qwen3.8-omni-flash','real_model':True,'supply':'water','scene':'unknown'}}}}
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'log.json'
            f.write_text(json.dumps(log));self.assertTrue(audit.audit(f)['automated_pass'])
            log['intent_gate']={'allow':False};f.write_text(json.dumps(log));self.assertFalse(audit.audit(f)['automated_pass'])
            log['intent_gate']={'allow':True};log['preflight']={'gate':{'allow':True}};f.write_text(json.dumps(log));self.assertFalse(audit.audit(f)['automated_pass'])
        with self.assertRaises(ValueError):srt.from_log({'run_type':'dry_run','events':log['events']})
    def test_jev_box_confidence_reject_nan(self):
        # Existing parsed payload fixture is a genuine parser contract test, not an API run.
        from unittest.mock import patch as _patch
        sample={'model':'jev-1.14.0','answers':{
            'supply':{'type':'choice','choice':'water','confidence':.96},
            'scene':{'type':'choice','choice':'clear'},
            'hazard':{'type':'noul','noul':.05},
            'visible_supply':{'type':'noul','noul':.98},
            'location':{'type':'box','box':{'top':.2,'bottom':.8,'left':.2,'right':.7},'confidence':float('nan')}}}
        with self.assertRaisesRegex(ValueError,'Box confidence'):jev.parse_response(sample)

if __name__=='__main__':unittest.main()

class TestCounterfactualV08(unittest.TestCase):
    def test_dual_gate_never_exceeds_jev_only_in_synthetic_contract(self):
        res=load(ROOT/'scripts/run_v08_counterfactual.py').run()
        self.assertEqual(res['n_cases'],108)
        p=res['policies']
        self.assertLessEqual(p['jev_plus_qwen']['unsafe_allow_count'],p['jev_only']['unsafe_allow_count'])
        self.assertLessEqual(p['jev_only']['unsafe_allow_count'],p['always_continue']['unsafe_allow_count'])
        self.assertIn('NOT_REAL_VLM',res['kind'])
