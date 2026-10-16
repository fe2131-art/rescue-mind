import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import unittest
from scripts.build_evidence_bundle import sha256,video_probe,validate_bundle,create_bundle

class TestEvidenceBundle(unittest.TestCase):
    def test_ffprobe_and_duration_constraints(self):
        class Result:
            stdout=json.dumps({'format':{'duration':'120.2'},'streams':[{'codec_type':'video','codec_name':'h264'}]})
        self.assertTrue(video_probe(Path('fake.mp4'),runner=lambda *a,**k:Result())['passes_format'])
        Result.stdout=json.dumps({'format':{'duration':'59.9'},'streams':[{'codec_type':'video','codec_name':'h264'}]})
        self.assertFalse(video_probe(Path('fake.mp4'),runner=lambda *a,**k:Result())['passes_format'])
        Result.stdout=json.dumps({'format':{'duration':'181'},'streams':[{'codec_type':'video','codec_name':'h264'}]})
        self.assertFalse(video_probe(Path('fake.mp4'),runner=lambda *a,**k:Result())['passes_format'])
    def test_tampered_image_detected_independently_of_log(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);frame=root/'f.jpg';log=root/'r.json';vid=root/'v.mp4'
            frame.write_bytes(b'abcdef');log.write_text(json.dumps({'events':[{'stage':'checkpoint_frame','image_sha256':sha256(frame)}],
                                                                   'checkpoint':{'image_sha256':sha256(frame)}}))
            vid.write_bytes(b'fake')
            with patch('scripts.build_evidence_bundle.audit',return_value={'automated_pass':True}):
                with patch('scripts.build_evidence_bundle.video_probe',return_value={'passes_format':True}):
                    result=validate_bundle(log,vid,frame)
                    self.assertTrue(result['can_package'])
                    frame.write_bytes(b'tampered')
                    with self.assertRaisesRegex(ValueError,'frame bytes'):
                        validate_bundle(log,vid,frame)
    def test_v10_timestamp_missing_refuses_bundle(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);frame=root/'f.jpg';log=root/'r.json';vid=root/'v.mp4'
            frame.write_bytes(b'abcd');vid.write_bytes(b'x')
            log.write_text(json.dumps({'version':'1.0','events':[{'stage':'checkpoint_frame','image_sha256':sha256(frame)}],
                                       'checkpoint':{'image_sha256':sha256(frame)}}))
            with patch('scripts.build_evidence_bundle.audit',return_value={'automated_pass':True}):
                with self.assertRaisesRegex(ValueError,'timestamp'):
                    validate_bundle(log,vid,frame)
    def test_invalid_audit_fails_closed(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);frame=root/'f.jpg';log=root/'r.json';vid=root/'v.mp4'
            frame.write_bytes(b'abcd');vid.write_bytes(b'x')
            log.write_text(json.dumps({'events':[{'stage':'checkpoint_frame','image_sha256':sha256(frame)}],
                                       'checkpoint':{'image_sha256':sha256(frame)}}))
            with patch('scripts.build_evidence_bundle.audit',return_value={'automated_pass':False}),\
                 patch('scripts.build_evidence_bundle.video_probe',return_value={'passes_format':True}):
                with self.assertRaisesRegex(ValueError,'preflight failed'):
                    create_bundle(log,vid,frame,root/'out.zip')
if __name__=='__main__':unittest.main()
