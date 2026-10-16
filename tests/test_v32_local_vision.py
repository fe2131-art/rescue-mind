import base64
import hashlib
import io
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from rescuemind.local_vision import (parse_model_json,localhost_only,validate_result,
    verify_station_local,local_decision,LocalInferenceError,PRIMARY_MODEL,SECONDARY_MODEL)
from rescuemind.local_run_audit import audit_local_checkpoint
from scripts.local_vlm_server import make_handler
from scripts.v32_orchestrate import build_plan

class FakeWorker:
    model_id=PRIMARY_MODEL
    def classify(self, image_bytes, pass_id):
        return {'supply':'water','scene':'unknown'}

class Tests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.image=Path(self.t.name)/'camera.jpg'
        Image.new('RGB',(512,384),(120,150,170)).save(self.image,'JPEG')
        self.blob=self.image.read_bytes()
        self.sha=hashlib.sha256(self.blob).hexdigest()

    def make_resp(self,model=PRIMARY_MODEL,pass_id=1,supply='water',scene='unknown',sha=None):
        return {'backend':'local_transformers','real_inference':True,'model':model,
                'image_sha256':sha or self.sha,'pass_id':pass_id,
                'result':{'supply':supply,'scene':scene}}

    def test_json_valid(self):
        self.assertEqual(parse_model_json('```json\n{"supply":"water","scene":"unknown"}\n```')['supply'],'water')
    def test_json_reject_malformed(self):
        for txt in ('not json','{"supply":"water"}','{"supply":"water","scene":"other"}',
                    '{"supply":"water","scene":"clear","allowed":true}'):
            with self.subTest(txt=txt),self.assertRaises(LocalInferenceError):parse_model_json(txt)
    def test_localhost_restrictions(self):
        for url in ('https://127.0.0.1:8765/v1/classify','http://0.0.0.0:8765/v1/classify',
                    'http://evil.net:8765/v1/classify','http://127.0.0.1:8765/wrong',
                    'http://127.0.0.1:8765/v1/classify?leak=1'):
            with self.subTest(url=url),self.assertRaises(LocalInferenceError):localhost_only(url)
        localhost_only('http://127.0.0.1:8765/v1/classify')
    def test_result_provenance(self):
        validate_result(self.make_resp(),PRIMARY_MODEL,self.sha,1)
        for changes in ({'model':'fake'},{'real_inference':False},{'image_sha256':'bad'},{'pass_id':2},
                        {'backend':'cloud_api'}):
            bad=self.make_resp();bad.update(changes)
            with self.subTest(changes=changes),self.assertRaises(LocalInferenceError):
                validate_result(bad,PRIMARY_MODEL,self.sha,1)
    def test_allow_same_model_twice(self):
        calls=[self.make_resp(pass_id=i) for i in (1,2)]
        self.assertTrue(local_decision('water',*calls)['allow'])
        self.assertFalse(local_decision('water',*calls)['model_diversity'])
    def test_wrong_or_missing_rejected(self):
        for wrong in ('medicine','other'):
            self.assertFalse(local_decision('water',self.make_resp(),self.make_resp(pass_id=2,supply=wrong))['allow'])
    def test_hazard_rejected(self):
        self.assertFalse(local_decision('water',self.make_resp(scene='hazard'),self.make_resp(pass_id=2))['allow'])
    def test_dual_requires_distinct_models(self):
        a,b=self.make_resp(),self.make_resp(pass_id=2)
        with self.assertRaises(LocalInferenceError):local_decision('water',a,b,dual_model=True)
        b=self.make_resp(model=SECONDARY_MODEL,pass_id=2)
        self.assertTrue(local_decision('water',a,b,dual_model=True)['allow'])
    def test_dual_hash_mismatch_rejected(self):
        with self.assertRaises(LocalInferenceError):
            local_decision('water',self.make_resp(),self.make_resp(pass_id=2,sha='a'*64))
    def test_checkpoint_mock_and_recompute(self):
        def transport(url,payload):
            return self.make_resp(model=payload['model'],pass_id=payload['pass_id'])
        outcome=verify_station_local(self.image,'water',transport=transport)
        self.assertTrue(outcome['decision']['allow'])
        self.assertEqual(outcome['backend'],'LOCAL_ONLY_NO_CLOUD_API')
        audit_local_checkpoint(outcome,self.sha,expected='water')
        outcome['decision']['allow']=False
        with self.assertRaises(ValueError):audit_local_checkpoint(outcome,self.sha,expected='water')
    def test_dual_mode_transport(self):
        def transport(url,payload):
            self.assertEqual(payload['model'], SECONDARY_MODEL if payload['pass_id']==2 else PRIMARY_MODEL)
            return self.make_resp(model=payload['model'],pass_id=payload['pass_id'])
        out=verify_station_local(self.image,'water',mode='dual',transport=transport)
        self.assertTrue(out['decision']['model_diversity'])
        audit_local_checkpoint(out,self.sha,expected='water')
    def test_wrong_transport_response_rejected(self):
        with self.assertRaises(LocalInferenceError):
            verify_station_local(self.image,'water',transport=lambda u,p:self.make_resp(sha='0'*64))
    def test_request_reject_wrong_url_before_transport(self):
        with self.assertRaises(LocalInferenceError):
            verify_station_local(self.image,'water',primary_url='http://example.com/v1/classify',transport=lambda *_:{})
    def test_server_real_http_mock_worker(self):
        http=ThreadingHTTPServer(('127.0.0.1',0),make_handler(FakeWorker()))
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        try:
            url='http://127.0.0.1:'+str(http.server_address[1])+'/v1/classify'
            from rescuemind.local_vision import _client_call
            answer=_client_call(url,PRIMARY_MODEL,self.blob,1)
            self.assertEqual(answer['result']['supply'],'water')
            with self.assertRaises(Exception):
                _client_call(url,SECONDARY_MODEL,self.blob,1)
        finally:
            http.shutdown();http.server_close();thread.join(2)
    def test_orchestrator_default_local(self):
        p=build_plan('live','避難所Bに飲料水を届けて',mission_timeout=900,evidence_dir=Path('/tmp/abcdef0123456789'))
        names=[x.name for x in p['services']]
        self.assertIn('primary_local_vlm',names)
        self.assertNotIn('secondary_local_vlm',names)
        self.assertIn('--inference-backend',p['mission'].argv[-1])
        self.assertIn('local',p['mission'].argv[-1])
        self.assertNotIn('TYPESAFE_API_KEY',str(p))
    def test_orchestrator_dual_and_motion_check(self):
        p=build_plan('live','避難所Bに飲料水を届けて',mission_timeout=900,local_mode='dual')
        self.assertIn('secondary_local_vlm',[x.name for x in p['services']])
        p=build_plan('motion-check','避難所Bに飲料水を届けて',mission_timeout=900)
        self.assertNotIn('primary_local_vlm',[x.name for x in p['services']])

if __name__=='__main__': unittest.main()


class ScoredDecisionTests(unittest.TestCase):
    """v3.3 closed-set log-probability decisions (threshold pre-registered at 0.50)."""
    def resp(self,pass_id,supply,probs,scene='clear'):
        return {'backend':'local_transformers','real_inference':True,'model':PRIMARY_MODEL,
                'image_sha256':'a'*64,'pass_id':pass_id,'result':{'supply':supply,'scene':scene},
                'scores':{'method':'closed_set_logprob','supply_probs':probs,'hazard_prob':0.01}}
    def test_confident_agreement_allows(self):
        p={'water':.7,'medicine':.1,'other':.2}
        d=local_decision('water',self.resp(1,'water',p),self.resp(2,'water',p))
        self.assertTrue(d['allow']);self.assertEqual(d['first_confidence'],.7)
    def test_plurality_below_threshold_denies(self):
        weak={'water':.45,'medicine':.15,'other':.40}
        strong={'water':.8,'medicine':.1,'other':.1}
        d=local_decision('water',self.resp(1,'water',weak),self.resp(2,'water',strong))
        self.assertFalse(d['allow']);self.assertEqual(d['reason'],'low_confidence_supply_match')
    def test_malformed_scores_rejected(self):
        bad=self.resp(1,'water',{'medicine':.9})
        with self.assertRaises(LocalInferenceError):
            local_decision('water',bad,self.resp(2,'water',{'water':.9,'medicine':0,'other':.1}))
    def test_hazard_still_overrides_confidence(self):
        p={'water':.95,'medicine':.0,'other':.05}
        d=local_decision('water',self.resp(1,'water',p,scene='hazard'),self.resp(2,'water',p))
        self.assertFalse(d['allow'])
