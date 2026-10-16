"""v2.4 negative-scene completion: deny must be independently observed."""
from __future__ import annotations
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from rescuemind.v24_trial_outcome import classify_negative_run, TrialClassificationError
from tests.test_v22_scenes_and_denials import fixtures, RUN

WAYPOINTS={'water':[1.18,1.13],'medicine':[-1.18,1.13],'B':[2.15,-1.12]}

def setup(path):
    m,r,mission,obs=fixtures(path)
    mission['intent']={'item':'water'}
    mission['events'].insert(2,{'stage':'checkpoint_denial_dwell_finished',
                              't_wall_s':9.5,'commanded_linear':0.0,
                              'commanded_angular':0.0})
    # Create enough post-decision ROS observations to check station dwell.
    extra=[]
    start=mission['mission_start_unix_ns']
    for i in range(5):
        extra.append({'kind':'odom','wall_unix_ns':start+int((8.0+i*.5)*1e9),
                      'ros_stamp_ns':10_000_000_000+i*500_000_000,
                      'x':1.18,'y':1.13,'frame_id':'odom','child_frame_id':'base_link'})
    allrows=obs+extra
    allrows[1:]=sorted(allrows[1:],key=lambda v:v['wall_unix_ns'])
    m.write_text(json.dumps(mission))
    r.write_text('\n'.join(json.dumps(v) for v in allrows)+'\n')
    return m,r,mission,allrows

class DenialOutcomeTests(unittest.TestCase):
    def test_valid_denial_needs_stationary_obs(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/RUN;path.mkdir();setup(path)
            result=classify_negative_run(path,scene='swapped',run_id=RUN,waypoints=WAYPOINTS)
            self.assertEqual(result['state'],'COMPLETED_EXPECTED_DENIAL')
    def test_empty_also_allowed_as_expected_denial(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/RUN;path.mkdir();setup(path)
            self.assertEqual(classify_negative_run(path,scene='empty',run_id=RUN,waypoints=WAYPOINTS)['scene'],'empty')
    def test_nominal_never_becomes_expected_denial(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/RUN;path.mkdir();setup(path)
            with self.assertRaises(TrialClassificationError):
                classify_negative_run(path,scene='nominal',run_id=RUN,waypoints=WAYPOINTS)
    def test_bad_runid(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/RUN;path.mkdir();setup(path)
            with self.assertRaises(TrialClassificationError):
                classify_negative_run(path,scene='empty',run_id='aaaaaaaaaaaaaaaa',waypoints=WAYPOINTS)
    def test_missing_hold(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/RUN;path.mkdir();m,_,data,_=setup(path)
            data['events']=[e for e in data['events'] if e.get('stage')!='checkpoint_denial_dwell_finished']
            m.write_text(json.dumps(data))
            with self.assertRaises(TrialClassificationError):
                classify_negative_run(path,scene='empty',run_id=RUN,waypoints=WAYPOINTS)
    def test_short_hold(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/RUN;path.mkdir();m,_,data,_=setup(path)
            next(e for e in data['events'] if e.get('stage')=='checkpoint_denial_dwell_finished')['t_wall_s']=7.1
            m.write_text(json.dumps(data))
            with self.assertRaises(TrialClassificationError):
                classify_negative_run(path,scene='empty',run_id=RUN,waypoints=WAYPOINTS)
    def test_nonzero_command_at_hold(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/RUN;path.mkdir();m,_,data,_=setup(path)
            next(e for e in data['events'] if e.get('stage')=='checkpoint_denial_dwell_finished')['commanded_linear']=.5
            m.write_text(json.dumps(data))
            with self.assertRaises(TrialClassificationError):
                classify_negative_run(path,scene='empty',run_id=RUN,waypoints=WAYPOINTS)
    def test_missing_jev_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/RUN;path.mkdir();m,_,data,_=setup(path)
            data['checkpoint']['model_calls']['jev']['real_model']=False
            m.write_text(json.dumps(data))
            with self.assertRaises(TrialClassificationError):
                classify_negative_run(path,scene='swapped',run_id=RUN,waypoints=WAYPOINTS)
    def test_robot_leaving_station_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/RUN;path.mkdir();_,r,_,records=setup(path)
            records[-1]['x']=2.15;records[-1]['y']=-1.12
            r.write_text('\n'.join(json.dumps(v) for v in records)+'\n')
            with self.assertRaises(TrialClassificationError):
                classify_negative_run(path,scene='swapped',run_id=RUN,waypoints=WAYPOINTS)
    def test_synthetic_crash_is_not_denial(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/RUN;path.mkdir();m,_,data,_=setup(path)
            data['checkpoint']=None;m.write_text(json.dumps(data))
            with self.assertRaises(TrialClassificationError):
                classify_negative_run(path,scene='swapped',run_id=RUN,waypoints=WAYPOINTS)
    def test_nominal_orchestration_wont_classify_denial(self):
        from scripts.v22_orchestrate import build_plan
        plan=build_plan('live','避難所Bに飲料水を届けて',mission_timeout=400,scene='nominal')
        self.assertIn('--run-live',str(plan['mission'].argv))
    def test_live_mission_contains_stationary_hold(self):
        import inspect
        from ros import gazebo_waypoint_mission as g
        src=inspect.getsource(g.run_ros)
        self.assertIn('checkpoint_denial_dwell_finished',src)
        self.assertIn('publish()',src)
        self.assertIn('denial dwell watchdog',src)

if __name__=='__main__': unittest.main()
