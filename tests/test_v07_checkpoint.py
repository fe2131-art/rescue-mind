import importlib.util
import json
import math
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from rescuemind.checkpoint import decide_checkpoint, verify_station
from rescuemind import jev
ROOT=Path(__file__).resolve().parents[1]

def load(name,rel):
    spec=importlib.util.spec_from_file_location(name,ROOT/rel)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

audit=load('audit07','scripts/audit_robot_run.py')
srt=load('srt07','scripts/make_overlay_srt.py')

def j(**kwargs):
    return {**{'real_model':True,'model':jev.MODEL_ID,'supply':'water','supply_confidence':.95,'supply_present_probability':.99,'hazard_probability':.05,'scene':'unknown'},**kwargs}
def q(**kwargs):
    return {**{'real_model':True,'model':'qwen3.8-omni-flash','supply':'water','scene':'unknown'},**kwargs}

def valid_log():
    events=[{'stage':'supply_station','arrived':True,'t_wall_s':12.0},
            {'stage':'checkpoint_frame','image_sha256':'f'*64,'t_wall_s':13.0},
            {'stage':'checkpoint_decision','allow':True,'t_wall_s':17.0},
            {'stage':'shelter_approach','arrived':True,'t_wall_s':31.0}]
    return {'version':'0.7','run_type':'jev_qwen_mission','success':True,
            'physical_pickup':False,'intent':{'item':'water'},'events':events,'trace':[{'x':0},{'x':1}],
            'preflight':{'gate':{'allow':True}},
            'checkpoint':{'decision':decide_checkpoint('water',j(),q()).to_dict(),
                           'image_sha256':'f'*64,'model_calls':{'jev':j(),'qwen':q()}}}

class TestCheckpoint(unittest.TestCase):
    def test_both_real_models_approve(self):
        d=decide_checkpoint('water',j(),q())
        self.assertTrue(d.allow)
        self.assertEqual(d.reason,'on_site_supply_confirmed')
    def test_jev_is_mandatory(self):
        for v in (None,{},j(real_model=False),j(model='jev-1.13.0')):
            with self.subTest(v=v):self.assertFalse(decide_checkpoint('water',v,q()).allow)
    def test_qwen_is_mandatory(self):
        for v in (None,{},q(real_model=False),q(supply='medicine'),q(model='untrusted')):
            with self.subTest(v=v):self.assertFalse(decide_checkpoint('water',j(),v).allow)
    def test_presence_confidence(self):
        for v in (j(supply_confidence=.64),j(supply_present_probability=.79),
                  j(supply_confidence=math.inf),j(supply_present_probability=math.nan),
                  j(supply_confidence='unknown'),j(supply='medicine')):
            with self.subTest(v=v):self.assertFalse(decide_checkpoint('water',v,q()).allow)
    def test_unknown_supply_raises(self):
        with self.assertRaises(ValueError):decide_checkpoint('bandages',j(),q())
    def test_injected_clients_offline(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'frame.jpg';f.write_bytes(b'x'*301)
            result=verify_station(f,'water',qwen_model='qwen3.8-omni-flash',endpoint='unused',
                                  jev_client=lambda img:j(),qwen_client=lambda img,model,endpoint:q())
            self.assertTrue(result['decision']['allow'])
            self.assertEqual(len(result['image_sha256']),64)
    def test_missing_image_rejected_before_call(self):
        with self.assertRaises(ValueError):verify_station('/does/not/exist','water',qwen_model='x',endpoint='x')
    def test_evidence_require_order_and_hash(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'log.json'
            def check(log):
                f.write_text(json.dumps(log));return audit.audit(f)['automated_pass']
            rec=valid_log();self.assertTrue(check(rec))
            rec['checkpoint']['image_sha256']='0'*64;self.assertFalse(check(rec))
            rec=valid_log();rec['events'][-1],rec['events'][1]=rec['events'][1],rec['events'][-1]
            self.assertFalse(check(rec))
            rec=valid_log();rec['checkpoint']=None;self.assertFalse(check(rec))
    def test_srt_logged_events_only(self):
        result=srt.from_log(valid_log());self.assertIn('00:00:13,000',result)
        self.assertIn('Jev',result)
        d=valid_log();d['run_type']='dry_run'
        with self.assertRaises(ValueError):srt.from_log(d)
    def test_srt_malformed_timestamp(self):
        d=valid_log();d['events'][0].pop('t_wall_s')
        with self.assertRaises(ValueError):srt.from_log(d)
    def test_no_real_api_or_ros_claim(self):
        self.assertFalse(valid_log().get('independently_verified',False))

if __name__=='__main__':unittest.main()
