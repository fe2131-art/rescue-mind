import importlib.util
import json
import tempfile
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('rm_evidence',ROOT/'scripts/audit_robot_run.py')
audit=importlib.util.module_from_spec(s);s.loader.exec_module(audit)
class TestEvidence(unittest.TestCase):
 def test_offline_logs_not_robot_proof(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.json';p.write_text(json.dumps({'run_type':'dry_run','success':True,'events':[],'trace':[]}))
   result=audit.audit(p)
   self.assertFalse(result['automated_pass'])
   self.assertFalse(result['robot_motion_independently_verified'])
 def test_honest_mission_log(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.json';p.write_text(json.dumps({'run_type':'jev_qwen_mission','preflight':{'gate':{'allow':True}},
    'success':True,'physical_pickup':False,'intent':{'item':'water'},
    'checkpoint':{'decision':__import__('rescuemind.checkpoint',fromlist=['decide_checkpoint']).decide_checkpoint('water',
        {'model':'jev-1.14.0','real_model':True,'supply':'water','supply_confidence':.95,'supply_present_probability':.99,'hazard_probability':.01,'scene':'unknown'},
        {'model':'qwen3.8-omni-flash','real_model':True,'supply':'water','scene':'unknown'}).to_dict(),
        'image_sha256':'a'*64,'model_calls':{'jev':{'model':'jev-1.14.0','real_model':True,'supply':'water','supply_confidence':.95,'supply_present_probability':.99,'hazard_probability':.01,'scene':'unknown'},
        'qwen':{'model':'qwen3.8-omni-flash','real_model':True,'supply':'water','scene':'unknown'}}},
    'events':[{'stage':'supply_station','arrived':True,'t_wall_s':12},{'stage':'checkpoint_frame','image_sha256':'a'*64,'t_wall_s':13},
              {'stage':'checkpoint_decision','allow':True,'t_wall_s':16}, {'stage':'shelter_approach','arrived':True,'t_wall_s':30}],
    'trace':[{},{}]}))
   result=audit.audit(p);self.assertTrue(result['automated_pass'])
   self.assertFalse(result['robot_motion_independently_verified'])
if __name__=='__main__':unittest.main()
