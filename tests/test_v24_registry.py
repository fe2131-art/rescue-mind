"""Strongly bind a trial ID to genuine-looking *local saved records*.

Fixtures are synthetic, never actual Gazebo or real model evidence.
"""
import unittest
import json
import hashlib
import shutil
import tempfile
from pathlib import Path
from rescuemind.v24_run_registry import proof_for_trial,register,RunRegistrationError
from rescuemind.v23_protocol import make_protocol
from tests.test_v24_negative_outcome import setup,RUN

SOURCE=Path(__file__).resolve().parents[1]

def create_root(root):
    trial=next(x for x in make_protocol()['trials'] if x['scene']=='swapped' and x['expected']=='water')
    sdf=root/'worlds/scenarios'/('rescuemind_swapped.sdf');sdf.parent.mkdir(parents=True)
    shutil.copy2(SOURCE/'worlds/scenarios/rescuemind_swapped.sdf',sdf)
    cfg=root/'configs/gazebo_waypoints.json';cfg.parent.mkdir(parents=True)
    cfg.write_text(json.dumps({'water':[1.18,1.13],'medicine':[-1.18,1.13],'B':[2.15,-1.12]}))
    run=root/'outputs/runs'/RUN;run.mkdir(parents=True)
    mp,rp,mission,_=setup(run)
    # This fake fixture simulates the API format for an offline contract test.
    img=b'FAKE FRAME BYTES - NOT A CAMERA CAPTURE'
    (run/'checkpoint.jpg').write_bytes(img)
    digest=hashlib.sha256(img).hexdigest()
    mission['checkpoint_image_path']=f'outputs/runs/{RUN}/checkpoint.jpg'
    mission['events'].insert(2,{'stage':'checkpoint_frame','image_sha256':digest,'t_wall_s':6.})
    mission['checkpoint']['image_sha256']=digest
    mission['checkpoint']['model_calls']['jev']['model']='jev-1.14.0'
    mission['checkpoint']['model_calls']['qwen']['model']='qwen3.8-omni-flash'
    mp.write_text(json.dumps(mission))
    (run/'stack_plan.json').write_text(json.dumps({'scenario':'live','scene':'swapped','scene_sha256':hashlib.sha256(sdf.read_bytes()).hexdigest()}))
    (run/'stack_result.json').write_text(json.dumps({'state':'COMPLETED_EXPECTED_DENIAL','run_id':RUN,'scene':'swapped'}))
    return trial,run

class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.trial,self.run=create_root(self.root)
        self.protocol=make_protocol()
    def test_registered_negative_trial(self):
        p=proof_for_trial(self.root,self.protocol,self.trial['id'],self.run)
        self.assertEqual(p['observed_behavior'],'DENY_AND_STATIONARY')
    def test_append_only_no_duplicate(self):
        r=self.root/'experiments/registry.jsonl'
        register(self.root,self.protocol,self.trial['id'],self.run,r)
        with self.assertRaises(RunRegistrationError):
            register(self.root,self.protocol,self.trial['id'],self.run,r)
        self.assertEqual(len(r.read_text().splitlines()),1)
    def test_wrong_trial_rejected(self):
        other=next(x for x in self.protocol['trials'] if x['scene']=='nominal')
        with self.assertRaises(RunRegistrationError):
            proof_for_trial(self.root,self.protocol,other['id'],self.run)
    def test_scene_tamper_rejected(self):
        sdf=self.root/'worlds/scenarios/rescuemind_swapped.sdf'
        sdf.write_bytes(sdf.read_bytes()+b'<!-- tampered -->')
        with self.assertRaises(RunRegistrationError):
            proof_for_trial(self.root,self.protocol,self.trial['id'],self.run)
    def test_image_tamper_rejected(self):
        (self.run/'checkpoint.jpg').write_bytes(b'something else')
        with self.assertRaises(RunRegistrationError):
            proof_for_trial(self.root,self.protocol,self.trial['id'],self.run)
    def test_wrong_model_version_rejected(self):
        f=self.run/'mission.json';m=json.loads(f.read_text())
        m['checkpoint']['model_calls']['jev']['model']='jev-latest';f.write_text(json.dumps(m))
        with self.assertRaises(RunRegistrationError):
            proof_for_trial(self.root,self.protocol,self.trial['id'],self.run)
    def test_crash_rejected(self):
        f=self.run/'mission.json';m=json.loads(f.read_text())
        m['events']=[e for e in m['events'] if e.get('stage')!='checkpoint_denial_dwell_finished']
        f.write_text(json.dumps(m))
        with self.assertRaises(RunRegistrationError):
            proof_for_trial(self.root,self.protocol,self.trial['id'],self.run)
    def test_wrong_supply_rejected(self):
        f=self.run/'mission.json';m=json.loads(f.read_text())
        m['intent']['item']='medicine';f.write_text(json.dumps(m))
        with self.assertRaises(RunRegistrationError):
            proof_for_trial(self.root,self.protocol,self.trial['id'],self.run)
    def test_run_folder_external_rejected(self):
        with self.assertRaises(RunRegistrationError):
            proof_for_trial(self.root,self.protocol,self.trial['id'],SOURCE/'outputs')

if __name__=='__main__':unittest.main()
