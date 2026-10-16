"""Scenario selection must change SDF only, not weaken Jev/guard topology."""
import unittest
from pathlib import Path
from scripts.v22_orchestrate import build_plan

class PlanTests(unittest.TestCase):
    def test_three_scene_worlds_run_same_mission(self):
        for s in ('nominal','swapped','empty'):
            plan=build_plan('live','避難所Bに飲料水を届けて',mission_timeout=400,scene=s)
            self.assertEqual(plan['scene'],s)
            self.assertTrue(plan['services'][0].argv[-1].endswith('rescuemind_'+s+'.sdf'))
            self.assertTrue(any('guard' in x.name for x in plan['services']))
            self.assertTrue(any('--run-live' in arg for arg in plan['mission'].argv))
            self.assertTrue(any('--cmd_vel' not in arg for arg in plan['mission'].argv))
    def test_invalid_scene_rejected(self):
        with self.assertRaises(ValueError):
            build_plan('live','x',mission_timeout=400,scene='invalid')
    def test_motion_lane_not_claimed_as_ai(self):
        plan=build_plan('motion-check','x',mission_timeout=400,scene='nominal')
        self.assertIn('--motion-check',str(plan['mission'].argv))
        self.assertNotIn('--run-live',str(plan['mission'].argv))
    def test_rosbag_has_clock(self):
        plan=build_plan('live','x',mission_timeout=400,scene='swapped',
                        evidence_dir=Path('/tmp/1234567890abcdef'),capture_rosbag=True)
        bag=next(x for x in plan['services'] if x.name=='rosbag_recorder')
        self.assertIn('/clock',bag.argv[-1])
        self.assertIn('--use-sim-time',bag.argv[-1])
if __name__=='__main__':unittest.main()

class TrialAuditTests(unittest.TestCase):
    def test_expected_denial_is_distinct_from_crash(self):
        import json,tempfile
        from scripts.v22_audit_trials import evaluate
        from tests.test_v22_scenes_and_denials import fixtures,RUN
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/RUN;path.mkdir()
            m,r,mission,_=fixtures(path)
            mission['intent']={'item':'water'}
            m.write_text(json.dumps(mission))
            (path/'stack_plan.json').write_text(json.dumps({'scenario':'live','scene':'swapped'}))
            (path/'stack_result.json').write_text(json.dumps({'scene':'swapped','state':'FAILED','run_id':RUN}))
            result=evaluate(path)
            self.assertTrue(result['verified'])
            self.assertEqual(result['observed'],'DENY_AND_STATIONARY')
            # Error without Jev checkpoint evidence must NOT be counted as success.
            mission.pop('checkpoint');m.write_text(json.dumps(mission))
            result=evaluate(path)
            self.assertFalse(result['verified'])
    def test_nominal_cannot_fake_positive_with_failed_status(self):
        import json,tempfile
        from scripts.v22_audit_trials import evaluate
        from tests.test_v22_scenes_and_denials import fixtures,RUN
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/RUN;path.mkdir()
            m,r,mission,_=fixtures(path)
            mission['intent']={'item':'water'}
            m.write_text(json.dumps(mission))
            (path/'stack_plan.json').write_text(json.dumps({'scenario':'live','scene':'nominal'}))
            (path/'stack_result.json').write_text(json.dumps({'scene':'nominal','state':'FAILED','run_id':RUN}))
            result=evaluate(path)
            self.assertFalse(result['verified'])
