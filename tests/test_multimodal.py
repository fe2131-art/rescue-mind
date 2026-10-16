import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from rescuemind.jev import infer as jev_infer, MODEL_ID
from rescuemind.qwen35 import infer as qwen_infer
from rescuemind.safety import decide
from rescuemind.vision import image_from_ros_msg
from types import SimpleNamespace

class TestMultimodal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.img=Path(self.tmp.name)/'sample.jpg'
        Image.new('RGB',(400,320),(120,130,140)).save(self.img)
    def tearDown(self):self.tmp.cleanup()

    @staticmethod
    def jev_response(supply='water',scene='clear',hazard=.03):
        return {'model':MODEL_ID,'answers':{'supply':{'type':'choice','choice':supply,'confidence':.92},
            'scene':{'type':'choice','choice':scene,'confidence':.89},
            'hazard':{'type':'noul','noul':hazard}, 'visible_supply':{'type':'noul','noul':.94},
            'location':{'type':'box','box':{'top':.1,'bottom':.5,'left':.2,'right':.7},'confidence':.7}},
            'usage':{'input_tokens':1400}}

    def test_jev_image_request_exact_version_and_header(self):
        def transport(body,headers):
            self.assertEqual(body['model'],'jev-1.14.0')
            self.assertEqual(headers['TypeSafe-Danger-Zone-Images'],'true')
            self.assertEqual(set(body['questions']),{'supply','scene','hazard','location','visible_supply'})
            self.assertTrue(body['assets'])
            return self.jev_response()
        result=jev_infer(self.img,api_key='FAKE_TEST_KEY',transport=transport)
        self.assertEqual(result['model'],MODEL_ID)
        self.assertEqual(result['supply'],'water')

    def test_jev_requires_key(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(RuntimeError,'TYPESAFE_API_KEY'):
                jev_infer(self.img)

    def test_qwen_local_api_request(self):
        def transport(body):
            self.assertEqual(body['model'],'Qwen/Qwen3.5-4B')
            self.assertTrue(body['messages'][1]['content'][0]['image_url']['url'].startswith('data:image/jpeg;base64,'))
            return {'model':'Qwen/Qwen3.5-4B','choices':[{'message':{'content':'{"supply":"water","scene":"clear"}'}}]}
        result=qwen_infer(self.img,transport=transport)
        self.assertTrue(result['real_model'])
        self.assertEqual(result['supply'],'water')

    def test_jev_box_is_not_used_when_object_absent(self):
        mock=self.jev_response()
        mock['answers']['visible_supply']['noul']=.05
        j=jev_infer(self.img,api_key='FAKE_TEST_KEY',transport=lambda b,h:mock)
        self.assertIsNone(j['box'])
        q={'real_model':True,'supply':'water','scene':'clear'}
        self.assertEqual(decide('water',j,q).reason, 'jev_supply_not_confirmed')

    def test_jev_presence_invalid_rejected(self):
        mock=self.jev_response()
        mock['answers']['visible_supply']['noul']=1.5
        with self.assertRaisesRegex(ValueError,'visibility'):
            jev_infer(self.img,api_key='FAKE_TEST_KEY',transport=lambda b,h:mock)

    def test_fake_cloud_host_rejected(self):
        from unittest.mock import patch
        with patch.dict('os.environ',{'DASHSCOPE_API_KEY':'FAKE','DASHSCOPE_BASE_URL':'https://invalid.example/v1'}):
            with self.assertRaisesRegex(ValueError,'aliyuncs'):
                qwen_infer(self.img,model='qwen3.8-omni-flash',transport=lambda b: {})

    def test_agreement_allows_with_mocked_transport_data(self):
        j=jev_infer(self.img,api_key='FAKE_TEST_KEY',transport=lambda b,h:self.jev_response())
        q=qwen_infer(self.img,transport=lambda b:{'model':'Qwen/Qwen3.5-4B','choices':[{'message':{'content':'{"supply":"water","scene":"clear"}'}}]})
        self.assertTrue(decide('water',j,q).allow)

    def test_disagreement_blocks(self):
        j={'real_model':True,'supply':'water','scene':'clear','supply_confidence':.95,'hazard_probability':.03,'supply_present_probability':.95}
        q={'real_model':True,'supply':'medicine','scene':'clear'}
        self.assertFalse(decide('water',j,q).allow)
        self.assertEqual(decide('water',j,q).reason,'supply_mismatch_or_disagreement')

    def test_hazard_blocks(self):
        j={'real_model':True,'supply':'water','scene':'clear','supply_confidence':.95,'hazard_probability':.8,'supply_present_probability':.95}
        q={'real_model':True,'supply':'water','scene':'clear'}
        self.assertEqual(decide('water',j,q).reason,'hazard_or_uncertain_scene')

    def test_missing_jev_blocks(self):
        q={'real_model':True,'supply':'water','scene':'clear'}
        self.assertEqual(decide('water',None,q).reason,'missing_model_result')
        self.assertFalse(decide('water',None,q).allow)

    def test_fixture_not_authorized(self):
        j={'real_model':False,'supply':'water','scene':'clear','supply_confidence':.95,'hazard_probability':.0,'supply_present_probability':.95}
        q={'real_model':True,'supply':'water','scene':'clear'}
        self.assertEqual(decide('water',j,q).reason,'mock_results_not_authorized')

    def test_bad_model_version_rejected(self):
        with self.assertRaisesRegex(ValueError,'version'):
            jev_infer(self.img,api_key='FAKE_TEST_KEY',transport=lambda b,h:{**self.jev_response(),'model':'jev-1.13.0'})

    def test_bad_box_rejected(self):
        data=self.jev_response()
        data['answers']['location']['box']['left']=.95
        with self.assertRaisesRegex(ValueError,'box'):
            jev_infer(self.img,api_key='FAKE_TEST_KEY',transport=lambda b,h:data)

    def test_bad_qwen_json_fails(self):
        with self.assertRaises(json.JSONDecodeError):
            qwen_infer(self.img,transport=lambda b:{'model':'Qwen/Qwen3.5-4B','choices':[{'message':{'content':'anything'}}]})

    def test_cloud_qwen38_api_contract(self):
        from unittest.mock import patch
        def transport(body):
            self.assertEqual(body['model'], 'qwen3.8-omni-flash')
            self.assertEqual(body['reasoning_effort'], 'low')
            self.assertTrue(body['stream'])
            self.assertEqual(body['stream_options']['include_usage'], True)
            self.assertNotIn('temperature', body)
            return {'model':'qwen3.8-omni-flash','choices':[{'message':{'content':'{"supply":"medicine","scene":"unknown"}'}}]}
        import os
        with patch.dict(os.environ, {'DASHSCOPE_API_KEY':'FAKE_KEY', 'DASHSCOPE_BASE_URL':'https://example.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1'}):
            q = qwen_infer(self.img,model='qwen3.8-omni-flash',transport=transport)
        self.assertEqual(q['model'],'qwen3.8-omni-flash')
        self.assertEqual(q['supply'],'medicine')

    def test_cloud_qwen38_missing_credentials_denied(self):
        from unittest.mock import patch
        import os
        with patch.dict(os.environ, {},clear=True):
            with self.assertRaisesRegex(RuntimeError,'DASHSCOPE'):
                qwen_infer(self.img,model='qwen3.8-omni-flash')

    def test_separate_corridor_observation_required(self):
        from rescuemind.multimodal_demo import run
        with self.assertRaisesRegex(ValueError,'corridor-image'):
            run(str(self.img), 'water')

    def test_ros_rgb_conversion(self):
        msg=SimpleNamespace(encoding='rgb8',width=1,height=1,step=3,data=bytes([255,0,0]))
        self.assertEqual(image_from_ros_msg(msg).getpixel((0,0)),(255,0,0))

if __name__=='__main__':unittest.main()

class TestImageIndependence(unittest.TestCase):
    def test_identical_images_rejected_even_with_different_paths(self):
        from rescuemind.multimodal_demo import run
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/'a.jpg'; b=Path(td)/'b.jpg'
            Image.new('RGB',(400,320),(50,80,20)).save(a)
            b.write_bytes(a.read_bytes())
            with self.assertRaisesRegex(ValueError,'identical decoded images'):
                run(str(a),'water',corridor_image=str(b))
