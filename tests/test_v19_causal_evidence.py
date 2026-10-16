"""Fully synthetic traces: NOT a measurement of Qwen, Jev or Gazebo."""
import json
import tempfile
import unittest
from pathlib import Path
from rescuemind.causal_evidence import audit_causal,CausalEvidenceError

RID='c'*16
START=1_800_000_000_000_000_000
ST=(1.18,1.13);SH=(2.15,-1.12)

def fixtures(folder,scenario='valid'):
    m={'run_id':RID,'run_type':'jev_qwen_live_mission','success':True,
       'mission_start_unix_ns':START,'events':[
            {'stage':'supply_station','arrived':True,'t_wall_s':8.},
            {'stage':'checkpoint_frame','t_wall_s':9.},
            {'stage':'checkpoint_decision','allow':True,'reason':'on_site_supply_confirmed','t_wall_s':12.},
            {'stage':'shelter_approach','arrived':True,'t_wall_s':20.}]}
    if scenario=='decision_early':m['events'][2]['t_wall_s']=7.5
    if scenario=='decision_deny':m['events'][2]['allow']=False
    if scenario=='anchor_missing':m.pop('mission_start_unix_ns')
    (folder/'mission.json').write_text(json.dumps(m),encoding='utf8')
    obs=[{'kind':'meta','run_id':RID,'start_unix_ns':START-2_000_000_000}]
    for i in range(221):
        sec=i/10
        if sec<=8: x,y=ST[0]*sec/8,ST[1]*sec/8
        elif sec<=12:x,y=ST
        elif sec<=20:
            t=(sec-12)/8;x,y=ST[0]+(SH[0]-ST[0])*t,ST[1]+(SH[1]-ST[1])*t
        else:x,y=SH
        if scenario=='premature_movement' and 10<=sec<12: x,y=ST[0]+.6,ST[1]
        if scenario=='premature_shelter' and 10<=sec<12:x,y=SH
        if scenario=='no_post_shelter' and sec>=12:x,y=ST
        if scenario=='missing_dwell' and 8.2<=sec<12:continue
        wall=START+int(sec*1e9)
        if scenario=='backward_clock' and i==90:wall-=2_000_000_000
        obs.append({'kind':'odom','wall_unix_ns':wall,'ros_stamp_ns':2_000_000_000+i*100_000_000,
                   'x':x,'y':y,'frame_id':'odom','child_frame_id':'base_link'})
        obs.append({'kind':'cmd_vel','wall_unix_ns':wall,'linear':0.1,'angular':0.0})
    if scenario=='run_mismatch':obs[0]['run_id']='d'*16
    (folder/'independent.jsonl').write_text('\n'.join(json.dumps(o) for o in obs),encoding='utf8')
    return folder/'mission.json',folder/'independent.jsonl'

class TestCausalEvidence(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)
    def test_nominal_passes(self):
        m,r=fixtures(self.root)
        receipt=audit_causal(m,r,station=ST,shelter=SH)
        self.assertTrue(receipt['pass'])
        self.assertGreater(receipt['stationary_samples_before_decision'],10)
    def test_failure_scenarios(self):
        for mode in ('decision_early','decision_deny','anchor_missing','premature_movement',
                     'premature_shelter','no_post_shelter','missing_dwell','backward_clock','run_mismatch'):
            with self.subTest(mode=mode):
                m,r=fixtures(self.root,mode)
                with self.assertRaises(CausalEvidenceError):
                    audit_causal(m,r,station=ST,shelter=SH)
    def test_anchor_and_stamp_are_distinct_timebases(self):
        m,r=fixtures(self.root)
        v=audit_causal(m,r,station=ST,shelter=SH)
        self.assertEqual(v['event_wall_unix_ns']['decision'],START+12_000_000_000)
    def test_live_causal_contract_wired_to_supervisor(self):
        from scripts import v16_orchestrate
        import inspect
        s=inspect.getsource(v16_orchestrate.main)
        self.assertIn('audit_causal(',s)
        self.assertIn("args.scenario == 'live'",s)
        self.assertIn('authorization_motion_chronology',s)
    def test_offline_run_audit_includes_chronology_for_live(self):
        import inspect
        from scripts import v18_verify_run
        self.assertIn('audit_causal(',inspect.getsource(v18_verify_run.audit_run))
