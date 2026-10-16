"""v2.9: regression tests for actual process SIGINT finalization and Jev negative classification.
No real ROS or Jev connection is claimed by these tests.
"""
from __future__ import annotations
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from rescuemind.stack_supervisor import Supervisor, ManagedCommand, StackFailure
from rescuemind import jev
from rescuemind.checkpoint import verify_station


def jev_wire(*, supply='other', presence=0.02, include_box=False):
    answers={
        'supply': {'type':'choice','choice':supply,'confidence':0.97},
        'visible_supply': {'type':'noul','noul':presence},
        'hazard': {'type':'noul','noul':0.02},
        'scene': {'type':'choice','choice':'unknown'},
    }
    if include_box:
        answers['location']={'type':'box','box':{'left':.2,'top':.2,'right':.6,'bottom':.7},'confidence':.9}
    return {'model':jev.MODEL_ID,'answers':answers}


class JevTwoPhaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.img=Path(self.tmp.name)/'image.jpg'
        Image.new('RGB',(420,360),(90,140,180)).save(self.img)
    def tearDown(self):self.tmp.cleanup()

    def test_missing_object_no_box_answer_is_valid_for_classification(self):
        def fake(body,headers):
            self.assertNotIn('location',body['questions'])
            self.assertEqual(body['model'],'jev-1.14.0')
            self.assertEqual(headers['TypeSafe-Danger-Zone-Images'],'true')
            return jev_wire()
        j=jev.infer_checkpoint(self.img,api_key='SYNTHETIC_ONLY',transport=fake)
        self.assertTrue(j['real_model']) # means transport response parsed, not independently attested!
        self.assertIsNone(j['box'])
        self.assertFalse(j['box_requested'])
        self.assertEqual(j['supply'],'other')

    def test_missing_box_stays_invalid_for_explicit_box_diagnostic(self):
        with self.assertRaises((KeyError,ValueError)):
            jev.infer(self.img,api_key='SYNTHETIC_ONLY',transport=lambda _b,_h:jev_wire())

    def test_positive_classification_without_box_still_requires_qwen_agreement(self):
        j=jev.infer_checkpoint(self.img,api_key='SYNTHETIC_ONLY',transport=lambda _b,_h:jev_wire(supply='water',presence=.96))
        self.assertIsNone(j['box'])
        from rescuemind.checkpoint import decide_checkpoint
        q={'real_model':True,'model':'qwen3.8-omni-flash','supply':'water','scene':'unknown'}
        self.assertTrue(decide_checkpoint('water',j,q).allow)
        q['supply']='medicine'
        self.assertFalse(decide_checkpoint('water',j,q).allow)

    def test_bad_supply_response_fails_closed_without_box(self):
        invalid=jev_wire(); invalid['answers']['visible_supply']['noul']=float('nan')
        with self.assertRaises(ValueError):
            jev.infer_checkpoint(self.img,api_key='SYNTHETIC_ONLY',transport=lambda _b,_h:invalid)

    def test_required_model_id_enforced_without_box(self):
        invalid=jev_wire(); invalid['model']='jev-1.13.0'
        with self.assertRaisesRegex(ValueError,'version'):
            jev.infer_checkpoint(self.img,api_key='SYNTHETIC_ONLY',transport=lambda _b,_h:invalid)

    def test_live_checkpoint_uses_no_box_request_by_default(self):
        def jev_fake(path, **kwargs):
            self.assertEqual(path,self.img)
            return {'real_model':True,'model':jev.MODEL_ID,'supply':'other',
                    'supply_confidence':.90,'supply_present_probability':.02,
                    'hazard_probability':.01,'scene':'unknown','box':None}
        def qwen_fake(path,**kwargs):
            return {'real_model':True,'model':'qwen3.8-omni-flash','supply':'other','scene':'unknown'}
        with patch('rescuemind.jev.infer_checkpoint',side_effect=jev_fake), \
             patch('rescuemind.qwen35.infer',side_effect=qwen_fake):
            result=verify_station(self.img,'water',qwen_model='qwen3.8-omni-flash',endpoint='unused')
        self.assertFalse(result['decision']['allow'])
        self.assertEqual(result['decision']['reason'],'insufficient_jev_evidence')

    def test_request_box_opt_in_is_kept_for_separate_diagnostic(self):
        j=jev.infer(self.img,api_key='SYNTHETIC_ONLY',transport=lambda b,h:jev_wire(supply='water',presence=.94,include_box=True))
        self.assertTrue(j['box_requested'])
        self.assertIsNotNone(j['box'])

class BagFinalizeTests(unittest.TestCase):
    def _start_process(self,d):
        root=Path(d)
        marker=root/'bag_finalized.marker'
        ready=root/'bag_running.marker'
        code='''import pathlib,signal,sys,time
ready=pathlib.Path(sys.argv[1]);complete=pathlib.Path(sys.argv[2])
def exit_clean(sig,frame):
 complete.write_text('metadata finalized by SIGINT')
 sys.exit(0)
signal.signal(signal.SIGINT,exit_clean)
ready.write_text('recording')
while True:time.sleep(0.03)
'''
        sup=Supervisor(root)
        sup.start_service(ManagedCommand('rosbag_recorder',(sys.executable,'-u','-c',code,str(ready),str(marker))))
        deadline=time.monotonic()+3.
        while not ready.exists() and time.monotonic()<deadline:time.sleep(.01)
        self.assertTrue(ready.exists(),'mock recorder never started')
        return sup,marker

    def test_recorder_finalizes_on_sigint_before_metadata_audit(self):
        with tempfile.TemporaryDirectory() as d:
            sup,marker=self._start_process(d)
            try:
                self.assertFalse(marker.exists(),'metadata should be absent during recording')
                result=sup.stop_service('rosbag_recorder')
                self.assertTrue(result['process_finished_before_metadata_audit'])
                self.assertEqual(result['signal'],'SIGINT')
                self.assertTrue(marker.exists(),'metadata became available after graceful exit')
                sup.ensure_alive() # intentionally removed service is not a crash
            finally:
                sup.shutdown()

    def test_cannot_finalize_unknown_or_non_bag_service(self):
        with tempfile.TemporaryDirectory() as d:
            sup=Supervisor(Path(d))
            with self.assertRaises(StackFailure):sup.stop_service('velocity_guard')
            with self.assertRaises(StackFailure):sup.stop_service('rosbag_recorder')

    def test_no_double_finalization(self):
        with tempfile.TemporaryDirectory() as d:
            sup,_=self._start_process(d)
            try:
                sup.stop_service('rosbag_recorder')
                with self.assertRaises(StackFailure):sup.stop_service('rosbag_recorder')
            finally:sup.shutdown()

    def test_real_live_success_path_finalizes_before_completion_audits(self):
        source=(Path(__file__).resolve().parents[1]/'scripts/v22_orchestrate.py').read_text()
        self.assertLess(source.index("outcome['rosbag_finalization'] = sup.stop_service('rosbag_recorder')"),
                        source.index("outcome['receipt']=validate("))
        self.assertIn("outcome['rosbag_evidence'] = audit_bag_metadata",source)

if __name__=='__main__':unittest.main()
