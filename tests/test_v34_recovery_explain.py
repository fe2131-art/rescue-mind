"""v3.4 I-02 (recovery audit) and I-03 (explanation client) — ROS-free tests."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from rescuemind.local_vision import (PRIMARY_MODEL, LocalInferenceError, describe_station_local,
                                     local_decision)
from rescuemind.recovery_evidence import RecoveryEvidenceError, audit_recovery


def resp(pass_id, supply, sha, probs):
    return {'backend': 'local_transformers', 'real_inference': True, 'model': PRIMARY_MODEL,
            'image_sha256': sha, 'pass_id': pass_id, 'result': {'supply': supply, 'scene': 'clear'},
            'scores': {'method': 'closed_set_logprob', 'supply_probs': probs, 'hazard_prob': 0.01}}


class RecoveryAuditTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); self.addCleanup(self.t.cleanup)
        self.dir = Path(self.t.name)
        img = self.dir / 'recovery_checkpoint.jpg'
        Image.new('RGB', (64, 48), (200, 30, 30)).save(img)
        self.sha = hashlib.sha256(img.read_bytes()).hexdigest()
        probs = {'water': 0.01, 'medicine': 0.9, 'other': 0.09}
        a, b = resp(1, 'medicine', self.sha, probs), resp(2, 'medicine', self.sha, probs)
        first = {'checkpoint_type': 'local_on_site_camera_supply_check', 'image_sha256': self.sha,
                 'backend': 'LOCAL_ONLY_NO_CLOUD_API', 'mode': 'single', 'model_calls': {'first': a, 'second': b},
                 'decision': local_decision('water', a, b)}
        stages = ['recovery_supply_station', 'recovery_checkpoint_frame', 'recovery_checkpoint_decision',
                  'recovery_checkpoint_denial_dwell_finished', 'recovery_search_started', 'supply_station',
                  'checkpoint_frame', 'checkpoint_decision']
        events = [{'stage': st, 't_wall_s': float(i)} for i, st in enumerate(stages)]
        events[1]['image_sha256'] = self.sha
        self.m = {'intent': {'item': 'water'}, 'checkpoint_station': 'medicine', 'events': events,
                  'checkpoint': {'decision': {'allow': True}},
                  'recovery': {'first_station': 'water', 'searched_station': 'medicine', 'first_checkpoint': first,
                               'first_checkpoint_image': img.name}}

    def test_valid_recovery_passes(self):
        r = audit_recovery(self.m, self.dir, completed=True)
        self.assertTrue(r['pass']); self.assertEqual(r['searched_station'], 'medicine')

    def test_recovery_after_hazard_is_rejected(self):
        self.m['recovery']['first_checkpoint']['decision']['reason'] = 'visible_hazard_at_checkpoint'
        with self.assertRaises(RecoveryEvidenceError):
            audit_recovery(self.m, self.dir, completed=True)

    def test_out_of_order_events_rejected(self):
        ev = self.m['events']; ev[4], ev[5] = ev[5], ev[4]
        with self.assertRaises(RecoveryEvidenceError):
            audit_recovery(self.m, self.dir, completed=True)

    def test_tampered_first_image_rejected(self):
        (self.dir / 'recovery_checkpoint.jpg').write_bytes(b'x' * 500)
        with self.assertRaises(RecoveryEvidenceError):
            audit_recovery(self.m, self.dir, completed=True)

    def test_same_station_twice_rejected(self):
        self.m['recovery']['searched_station'] = 'water'
        with self.assertRaises(RecoveryEvidenceError):
            audit_recovery(self.m, self.dir, completed=True)


class ExplanationTests(unittest.TestCase):
    def test_explanation_client_validates_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            img = Path(d) / 'c.jpg'; Image.new('RGB', (64, 48)).save(img)
            sha = hashlib.sha256(img.read_bytes()).hexdigest()
            ok = describe_station_local(img, transport=lambda u, p: {'model': PRIMARY_MODEL, 'image_sha256': sha,
                                                                     'real_inference': True, 'text_ja': '台の上に救急箱がある。'})
            self.assertEqual(ok['purpose'], 'explanation_only_not_decision')
            with self.assertRaises(LocalInferenceError):
                describe_station_local(img, transport=lambda u, p: {'model': PRIMARY_MODEL, 'image_sha256': '0' * 64,
                                                                    'real_inference': True, 'text_ja': 'x'})
            with self.assertRaises(LocalInferenceError):
                describe_station_local(img, url='http://evil.example:8765/v1/describe', transport=lambda u, p: {})


if __name__ == '__main__':
    unittest.main()
