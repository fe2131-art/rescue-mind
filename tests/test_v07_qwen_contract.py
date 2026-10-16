import os
import unittest
from unittest.mock import patch
from PIL import Image
import tempfile
from pathlib import Path
from rescuemind import qwen35

class TestQwen38Request(unittest.TestCase):
    def test_cloud_uses_text_only_streaming(self):
        with tempfile.TemporaryDirectory() as d:
            im=Path(d)/'frame.jpg';Image.new('RGB',(320,320),(255,0,0)).save(im)
            collected=[]
            def fake_transport(req):
                collected.append(req)
                return {'model':'qwen3.8-omni-flash','choices':[{'message':{'content':'{"supply":"water","scene":"unknown"}'}}]}
            with patch.dict(os.environ,{'DASHSCOPE_API_KEY':'MOCK_ONLY',
              'DASHSCOPE_BASE_URL':'https://fake.ap-northeast-1.maas.aliyuncs.com/compatible-mode/v1'}):
                result=qwen35.infer(im,model='qwen3.8-omni-flash',transport=fake_transport)
            self.assertEqual(result['supply'],'water')
            self.assertEqual(collected[0]['modalities'],['text'])
            self.assertTrue(collected[0]['stream'])
            self.assertEqual(collected[0]['reasoning_effort'],'low')

if __name__=='__main__':unittest.main()
