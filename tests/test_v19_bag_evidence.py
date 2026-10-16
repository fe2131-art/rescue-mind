"""Synthetic rosbag metadata checks; not real ROS2 recording."""
import tempfile, unittest, yaml
from pathlib import Path
from rescuemind.bag_evidence import audit_bag_metadata,BagEvidenceError,REQUIRED
from scripts.v16_orchestrate import build_plan

class BagMetadata(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.d=Path(tmp.name)/'rosbag2';self.d.mkdir()
        self.meta={'rosbag2_bagfile_information':{
            'relative_file_paths':['recording_0.db3'],
            'topics_with_message_count':[{'topic_metadata':{'name':t},'message_count':12} for t in REQUIRED]}}
        (self.d/'recording_0.db3').write_bytes(b'\0'*300)
    def save(self): (self.d/'metadata.yaml').write_text(yaml.safe_dump(self.meta))
    def test_valid(self):
        self.save();self.assertTrue(audit_bag_metadata(self.d)['pass'])
    def test_missing_topic(self):
        self.meta['rosbag2_bagfile_information']['topics_with_message_count'].pop()
        self.save()
        with self.assertRaisesRegex(BagEvidenceError,'missing'):audit_bag_metadata(self.d)
    def test_missing_metadata(self):
        with self.assertRaisesRegex(BagEvidenceError,'not finalized'):audit_bag_metadata(self.d)
    def test_low_count(self):
        self.meta['rosbag2_bagfile_information']['topics_with_message_count'][0]['message_count']=0
        self.save()
        with self.assertRaisesRegex(BagEvidenceError,'too few'):audit_bag_metadata(self.d)
    def test_traversal_rejected(self):
        self.meta['rosbag2_bagfile_information']['relative_file_paths']=['../../secrets']
        self.save()
        with self.assertRaisesRegex(BagEvidenceError,'storage paths'):audit_bag_metadata(self.d)
    def test_missing_storage(self):
        (self.d/'recording_0.db3').unlink();self.save()
        with self.assertRaisesRegex(BagEvidenceError,'missing/empty'):audit_bag_metadata(self.d)
    def test_run_plan_has_optional_bag(self):
        d=Path('/tmp')/('f'*16)
        self.assertEqual([c.name for c in build_plan('live','水',mission_timeout=300,evidence_dir=d)['services']][-1],'independent_odom_recorder')
        p=build_plan('live','水',mission_timeout=300,evidence_dir=d,capture_rosbag=True)
        self.assertEqual(p['services'][-1].name,'rosbag_recorder')
        self.assertIn('--topics',p['services'][-1].argv[-1])
