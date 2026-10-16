"""Tests v1.1 evidence binding, without claiming external data provenance."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.build_evidence_bundle import validate_bundle

class TestNewBundleBinding(unittest.TestCase):
    def example(self,td):
        root=Path(td)
        log=root/'mission.json';frame=root/'on_site_supply.jpg';video=root/'recording.mp4'
        frame.write_bytes(b'frame bytes'*100);video.write_bytes(b'video bytes'*100)
        obj={'version':'1.1','run_id':'f'*16,'checkpoint_image_path':'outputs/runs/'+'f'*16+'/on_site_supply.jpg',
             'events':[{'stage':'checkpoint_frame','image_sha256':__import__('hashlib').sha256(frame.read_bytes()).hexdigest(),
                        'ros_acquisition_stamp_ns':123456789}],
             'checkpoint':{'image_sha256':__import__('hashlib').sha256(frame.read_bytes()).hexdigest()}}
        log.write_text(json.dumps(obj))
        return log,video,frame,obj
    def test_valid_run_id_and_matching_frame(self):
        with tempfile.TemporaryDirectory() as td:
            log,video,frame,obj=self.example(td)
            with patch('scripts.build_evidence_bundle.audit',return_value={'automated_pass':True}),\
                 patch('scripts.build_evidence_bundle.video_probe',return_value={'passes_format':True}):
                self.assertTrue(validate_bundle(log,video,frame)['can_package'])
    def test_missing_or_bad_runid_rejected(self):
        for bad in (None,'not-valid','A'*16):
            with self.subTest(value=bad),tempfile.TemporaryDirectory() as td:
                log,video,frame,obj=self.example(td)
                obj['run_id']=bad;log.write_text(json.dumps(obj))
                with patch('scripts.build_evidence_bundle.audit',return_value={'automated_pass':True}):
                    with self.assertRaisesRegex(ValueError,'run_id'):
                        validate_bundle(log,video,frame)
    def test_different_frame_name_rejected_even_matching_hash(self):
        with tempfile.TemporaryDirectory() as td:
            log,video,frame,obj=self.example(td)
            obj['checkpoint_image_path']='other_folder/unrelated.jpg';log.write_text(json.dumps(obj))
            with patch('scripts.build_evidence_bundle.audit',return_value={'automated_pass':True}):
                with self.assertRaisesRegex(ValueError,'checkpoint_image_path'):
                    validate_bundle(log,video,frame)

if __name__=='__main__':unittest.main()
