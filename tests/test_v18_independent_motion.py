import json,math,unittest,tempfile
from pathlib import Path
from rescuemind.motion_evidence import audit_motion,MotionEvidenceError
from scripts.v16_orchestrate import build_plan

RID='a'*16
ST=(1.18,1.13); SH=(2.15,-1.12)

def make_log(path, *, scenario='nominal', run_id=RID):
    rows=[{'kind':'meta','run_id':run_id,'schema':'rescuemind_ros_observation_v1'}]
    points=[(0,0)]
    for a,b in (((0,0),ST),(ST,SH)):
        for i in range(1,51):points.append((a[0]+(b[0]-a[0])*i/50,a[1]+(b[1]-a[1])*i/50))
    if scenario=='no_shelter':points=points[:52]
    if scenario=='teleport':points[15]=(5,5)
    for i,(x,y) in enumerate(points):
        rows.append({'kind':'odom','ros_stamp_ns':1000000000+i*1000000000,
                     'x':x,'y':y,'frame_id':'odom','child_frame_id':'base_link'})
        rows.append({'kind':'cmd_vel','linear':0.1 if i<len(points)-1 else 0.,'angular':0.1})
    if scenario=='regression':
        items=[r for r in rows if r['kind']=='odom'];items[4]['ros_stamp_ns']=items[3]['ros_stamp_ns']
    if scenario=='no_velocity':
        rows=[r for r in rows if r['kind']!='cmd_vel']
    if scenario=='wrong_frames':
        rows[1]['frame_id']='map'
    path.write_text('\n'.join(json.dumps(r) for r in rows))

class TestMotionEvidence(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'trace.jsonl'
    def test_valid_ordered_motion_pass(self):
        make_log(self.path)
        x=audit_motion(self.path,run_id=RID,station=ST,shelter=SH)
        self.assertTrue(x['pass']);self.assertGreater(x['path_length_m'],3)
        self.assertGreater(x['shelter_sample_index'],x['station_sample_index'])
    def test_run_id_mismatch_rejected(self):
        make_log(self.path)
        with self.assertRaisesRegex(MotionEvidenceError,'run_id'):audit_motion(self.path,run_id='b'*16,station=ST,shelter=SH)
    def test_station_only_rejected(self):
        make_log(self.path,scenario='no_shelter')
        with self.assertRaisesRegex(MotionEvidenceError,'shelter'):audit_motion(self.path,run_id=RID,station=ST,shelter=SH)
    def test_teleport_rejected(self):
        make_log(self.path,scenario='teleport')
        with self.assertRaisesRegex(MotionEvidenceError,'fast'):audit_motion(self.path,run_id=RID,station=ST,shelter=SH)
    def test_stamp_reversal_rejected(self):
        make_log(self.path,scenario='regression')
        with self.assertRaisesRegex(MotionEvidenceError,'duplicate'):audit_motion(self.path,run_id=RID,station=ST,shelter=SH)
    def test_velocity_absent_rejected(self):
        make_log(self.path,scenario='no_velocity')
        with self.assertRaisesRegex(MotionEvidenceError,'velocity'):audit_motion(self.path,run_id=RID,station=ST,shelter=SH)
    def test_wrong_frames_rejected(self):
        make_log(self.path,scenario='wrong_frames')
        with self.assertRaisesRegex(MotionEvidenceError,'frame'):audit_motion(self.path,run_id=RID,station=ST,shelter=SH)
    def test_missing_file_rejected(self):
        with self.assertRaises(OSError):audit_motion(self.path,run_id=RID,station=ST,shelter=SH)
    def test_runtime_starts_observer_in_same_run_id(self):
        plan=build_plan('motion-check','水',mission_timeout=300,evidence_dir=Path('/tmp')/RID)
        self.assertEqual([s.name for s in plan['services']][-1],'independent_odom_recorder')
        self.assertIn(RID,' '.join(plan['services'][-1].argv))
    def test_plan_mode_is_nonrunning(self):
        plan=build_plan('motion-check','水',mission_timeout=300)
        self.assertEqual(len(plan['services']),3)

class TestCrossRecordAudit(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.d=Path(self.tmp.name)
        record={'run_id':RID,'run_type':'motion_check_non_ai','success':True,
                'intent':{'item':'water'},'events':[
                {'stage':'supply_station','arrived':True},
                {'stage':'shelter_approach','arrived':True}]}
        (self.d/'mission.json').write_text(json.dumps(record))
    def test_mission_claim_cannot_overrule_missing_shelter_evidence(self):
        from scripts.v18_verify_run import audit_run
        make_log(self.d/'independent_ros_topics.jsonl',scenario='no_shelter')
        with self.assertRaises(MotionEvidenceError):audit_run(self.d,'motion-check')
    def test_matching_mission_and_observation(self):
        from scripts.v18_verify_run import audit_run
        make_log(self.d/'independent_ros_topics.jsonl')
        proof=audit_run(self.d,'motion-check')
        self.assertTrue(proof['motion']['pass'])
        self.assertFalse(proof['completion']['robot_motion_independently_verified'])
