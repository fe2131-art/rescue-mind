import unittest
from rescuemind.v25_evidence import audit_alignment,AlignmentEvidenceError

def record():
    return {'version':'2.5','run_type':'jev_qwen_live_mission','intent':{'item':'water'},'events':[
        {'stage':'supply_station','arrived':True,'t_wall_s':10.},
        {'stage':'camera_aim_aligned','target_station':'water','error_rad':.05,'t_wall_s':11.},
        {'stage':'checkpoint_frame','ros_acquisition_stamp_ns':1000,'t_wall_s':11.7},
        {'stage':'checkpoint_decision','allow':True,'t_wall_s':12.}]}

class EvidenceTests(unittest.TestCase):
    def test_valid(self):self.assertEqual(audit_alignment(record())['status'],'post_aim_fresh_frame')
    def test_legacy_no_claim(self):
        a=record();a['version']='2.4';self.assertEqual(audit_alignment(a)['status'],'legacy_not_v25')
    def test_no_aim(self):
        a=record();del a['events'][1]
        with self.assertRaises(AlignmentEvidenceError):audit_alignment(a)
    def test_wrong_station(self):
        a=record();a['events'][1]['target_station']='medicine'
        with self.assertRaises(AlignmentEvidenceError):audit_alignment(a)
    def test_bad_bearing(self):
        a=record();a['events'][1]['error_rad']=.5
        with self.assertRaises(AlignmentEvidenceError):audit_alignment(a)
    def test_frame_prior(self):
        a=record();a['events'][2]['t_wall_s']=11.2
        with self.assertRaises(AlignmentEvidenceError):audit_alignment(a)
    def test_event_order(self):
        a=record();a['events'][1],a['events'][2]=a['events'][2],a['events'][1]
        with self.assertRaises(AlignmentEvidenceError):audit_alignment(a)
    def test_no_ros_stamp(self):
        a=record();a['events'][2]['ros_acquisition_stamp_ns']=0
        with self.assertRaises(AlignmentEvidenceError):audit_alignment(a)
    def test_duplicates(self):
        a=record();a['events'].append(a['events'][1])
        with self.assertRaises(AlignmentEvidenceError):audit_alignment(a)
    def test_nan_reject(self):
        a=record();a['events'][1]['error_rad']=float('nan')
        with self.assertRaises(AlignmentEvidenceError):audit_alignment(a)
if __name__=='__main__':unittest.main()
