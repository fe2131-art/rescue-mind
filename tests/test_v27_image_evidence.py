import copy, hashlib, json, tempfile, unittest
from pathlib import Path
from rescuemind.v27_image_evidence import audit_capture, ImageEvidenceError

def example(digest):
    q={'width':640,'height':480,'p01_luma':20,'p99_luma':210,
       'dark_fraction':.03,'bright_fraction':.01,'quality_ok':True,'reasons':[]}
    return {'run_type':'jev_qwen_live_mission','run_id':'1234567890abcdef',
      'events':[{'stage':'camera_aim_aligned','t_wall_s':10.},
                {'stage':'checkpoint_stationary_verified','t_wall_s':11.,'stable_elapsed_s':.7},
                {'stage':'checkpoint_image_quality_verified','t_wall_s':11.8,
                 'distinct_frames':2,'ros_stamps_ns':[9000000000,9150000000],
                 'capture_gap_wall_s':.2,'image_quality':q},
                {'stage':'checkpoint_frame','t_wall_s':11.81,'ros_acquisition_stamp_ns':9150000000,
                 'image_sha256':digest},
                {'stage':'checkpoint_decision','t_wall_s':13.,'allow':True}]}

class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        p=Path(self.tmp.name)
        self.image=p/'checkpoint.jpg'
        self.image.write_bytes(b'NOT a real camera image; fixture only'*30)
        self.mission=p/'mission.json'
        self.doc=example(hashlib.sha256(self.image.read_bytes()).hexdigest())
    def tearDown(self):self.tmp.cleanup()
    def audit(self,modified=None):
        self.mission.write_text(json.dumps(self.doc if modified is None else modified))
        return audit_capture(self.mission,self.image)
    def test_good(self):self.assertTrue(self.audit()['passed'])
    def test_changed_bytes(self):
        self.audit();self.image.write_bytes(b'F'*500)
        with self.assertRaisesRegex(ImageEvidenceError,'hash_mismatch'):self.audit()
    def test_missing_quality(self):
        self.doc['events'].pop(2)
        with self.assertRaisesRegex(ImageEvidenceError,'missing'):self.audit()
    def test_duplicate_quality(self):
        self.doc['events'].insert(3,copy.deepcopy(self.doc['events'][2]))
        with self.assertRaisesRegex(ImageEvidenceError,'duplicate'):self.audit()
    def test_stamp_does_not_match(self):
        self.doc['events'][3]['ros_acquisition_stamp_ns']+=1
        with self.assertRaisesRegex(ImageEvidenceError,'stamp'):self.audit()
    def test_bad_sequence(self):
        self.doc['events'][2]['ros_stamps_ns']=[100,100]
        with self.assertRaisesRegex(ImageEvidenceError,'distinct'):self.audit()
    def test_quality_not_ok(self):
        self.doc['events'][2]['image_quality']['quality_ok']=False
        with self.assertRaisesRegex(ImageEvidenceError,'quality'):self.audit()
    def test_too_soon(self):
        self.doc['events'][2]['t_wall_s']=11.1
        with self.assertRaisesRegex(ImageEvidenceError,'too_soon'):self.audit()
    def test_too_short_capture_gap(self):
        self.doc['events'][2]['capture_gap_wall_s']=.01
        with self.assertRaisesRegex(ImageEvidenceError,'gap'):self.audit()
    def test_missing_image(self):
        self.image.unlink()
        with self.assertRaisesRegex(ImageEvidenceError,'missing'):self.audit()
    def test_decision_order(self):
        self.doc['events'][3],self.doc['events'][4]=self.doc['events'][4],self.doc['events'][3]
        with self.assertRaisesRegex(ImageEvidenceError,'out_of_order'):self.audit()
    def test_live_only(self):
        self.doc['run_type']='motion_check_non_ai'
        with self.assertRaisesRegex(ImageEvidenceError,'non_live'):self.audit()
    def test_both_positive_and_denial_wired(self):
        s=(Path(__file__).resolve().parents[1]/'scripts/v22_orchestrate.py').read_text()
        self.assertEqual(s.count("audit_capture(log_dir/'mission.json',log_dir/'checkpoint.jpg')"),2)

if __name__=='__main__':unittest.main()
