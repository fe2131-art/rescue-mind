import json
import tempfile
import unittest
from pathlib import Path
from copy import deepcopy
from rescuemind.scene_variants import build_scenarios,audit_scenarios,SceneContractError
from rescuemind.negative_evidence import audit_denial,DenialEvidenceError
from rescuemind.gazebo_transport_contract import validate_static

ROOT=Path(__file__).resolve().parents[1]
RUN='1234567890abcdef'


def fixtures(root):
    start=2_000_000_000_000_000_000
    mission={'run_id':RUN,'run_type':'jev_qwen_live_mission','success':False,
             'mission_start_unix_ns':start,
             'checkpoint':{'decision':{'allow':False,'reason':'models_disagree_or_wrong_supply'},
                           'model_calls':{'jev':{'real_model':True},'qwen':{'real_model':True}}},
             'events':[{'stage':'supply_station','arrived':True,'t_wall_s':5.0},
                       {'stage':'checkpoint_decision','allow':False,
                        'reason':'models_disagree_or_wrong_supply','t_wall_s':7.0},
                       {'stage':'error','type':'RuntimeError'}]}
    records=[{'kind':'meta','run_id':RUN,'start_unix_ns':start-1000000000}]
    for i in range(15):
        t=start+int(i*.5*1e9)
        x,y=(1.18,1.13) if i>=10 else (i*.118,i*.113)
        records.append({'kind':'odom','wall_unix_ns':t,'ros_stamp_ns':t-start+100000000,
                        'x':x,'y':y,'frame_id':'odom','child_frame_id':'base_link'})
    # Need >=2 stationary observations post decision at 7.0,7.5 ...
    records += [dict(records[-1],wall_unix_ns=start+int((7.5+i*.5)*1e9)) for i in range(2)]
    # The above appended 8.0 beyond 7.5; 7.5 already included, preserve nondecreasing
    records.sort(key=lambda r:r.get('wall_unix_ns',0))
    mp=root/'mission.json';rp=root/'independent_ros_topics.jsonl'
    mp.write_text(json.dumps(mission))
    rp.write_text('\n'.join(json.dumps(r) for r in records)+'\n')
    return mp,rp,mission,records

class SceneTests(unittest.TestCase):
    def test_scenes_generated_and_audited(self):
        with tempfile.TemporaryDirectory() as td:
            manifest=build_scenarios(ROOT/'worlds/rescuemind_test_arena.sdf',td)
            self.assertEqual(len(manifest['scenes']),3)
            self.assertTrue(audit_scenarios(td)['pass'])
            for s in ('nominal','swapped','empty'):
                self.assertTrue(validate_static(Path(td)/f'rescuemind_{s}.sdf',ROOT/'configs/ros_gz_bridge_v20.yaml')['ok'])
    def test_static_scene_tamper_detected(self):
        with tempfile.TemporaryDirectory() as td:
            build_scenarios(ROOT/'worlds/rescuemind_test_arena.sdf',td)
            p=Path(td)/'rescuemind_swapped.sdf'
            p.write_bytes(p.read_bytes().replace(b'/odom',b'/odom_bad'))
            with self.assertRaises(SceneContractError):audit_scenarios(td)
    def test_scenes_no_color_leak(self):
        import xml.etree.ElementTree as ET
        for s in ('nominal','swapped','empty'):
            root=ET.parse(ROOT/'worlds/scenarios'/f'rescuemind_{s}.sdf').getroot()
            names={m.get('name'):m for m in root.findall('.//world/model')}
            colors=[]
            for station in ('aid_station_water','aid_station_medicine'):
                colors.append(names[station].findtext('link/visual/material/diffuse'))
            self.assertEqual(colors[0],colors[1])
    def test_robots_and_wheels_same(self):
        from xml.etree import ElementTree as ET
        blobs=[]
        for s in ('nominal','swapped','empty'):
            root=ET.parse(ROOT/'worlds/scenarios'/f'rescuemind_{s}.sdf').getroot()
            bot=next(m for m in root.findall('world/model') if m.get('name')=='rescue_diffbot')
            for el in bot.iter():
                if el.text is not None and not el.text.strip(): el.text=None
                el.tail=None
            blobs.append(ET.tostring(bot))
        self.assertEqual(len(set(blobs)),1)

class DenialTests(unittest.TestCase):
    def test_denied_stationary(self):
        with tempfile.TemporaryDirectory() as td:
            m,r,_,_=fixtures(Path(td))
            self.assertTrue(audit_denial(m,r,station=[1.18,1.13],shelter=[2.15,-1.12])['pass'])
    def test_denial_cannot_claim_shelter(self):
        with tempfile.TemporaryDirectory() as td:
            m,r,data,_=fixtures(Path(td))
            data['events'].append({'stage':'shelter_approach','arrived':True})
            m.write_text(json.dumps(data))
            with self.assertRaises(DenialEvidenceError):audit_denial(m,r,station=[1.18,1.13],shelter=[2.15,-1.12])
    def test_denial_requires_jev(self):
        with tempfile.TemporaryDirectory() as td:
            m,r,data,_=fixtures(Path(td))
            data['checkpoint']['model_calls']['jev']['real_model']=False
            m.write_text(json.dumps(data))
            with self.assertRaises(DenialEvidenceError):audit_denial(m,r,station=[1.18,1.13],shelter=[2.15,-1.12])
    def test_denied_robot_leaves(self):
        with tempfile.TemporaryDirectory() as td:
            m,r,_,rows=fixtures(Path(td))
            rows[-1]['x']=2.15;rows[-1]['y']=-1.12
            r.write_text('\n'.join(json.dumps(row) for row in rows)+'\n')
            with self.assertRaises(DenialEvidenceError):audit_denial(m,r,station=[1.18,1.13],shelter=[2.15,-1.12])
    def test_denial_insufficient_after_samples(self):
        with tempfile.TemporaryDirectory() as td:
            m,r,_,rows=fixtures(Path(td))
            rows=[row for row in rows if row.get('wall_unix_ns',0)<2_000_000_007_000_000_000 or row['kind']=='meta']
            r.write_text('\n'.join(json.dumps(row) for row in rows)+'\n')
            with self.assertRaises(DenialEvidenceError):audit_denial(m,r,station=[1.18,1.13],shelter=[2.15,-1.12])
    def test_denial_tampered_run_id(self):
        with tempfile.TemporaryDirectory() as td:
            m,r,data,_=fixtures(Path(td))
            data['run_id']='aaaaaaaaaaaaaaaa';m.write_text(json.dumps(data))
            with self.assertRaises(DenialEvidenceError):audit_denial(m,r,station=[1.18,1.13],shelter=[2.15,-1.12])
    def test_denial_bad_event_order(self):
        with tempfile.TemporaryDirectory() as td:
            m,r,data,_=fixtures(Path(td))
            data['events'][1]['t_wall_s']=4.0;m.write_text(json.dumps(data))
            with self.assertRaises(DenialEvidenceError):audit_denial(m,r,station=[1.18,1.13],shelter=[2.15,-1.12])
if __name__=='__main__':unittest.main()
