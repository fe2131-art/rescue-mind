"""Offline orchestration tests: mocked ROS/Gazebo, real control flow.

The fake service emits a simulated mission result and captures the call order.
This does NOT validate any actual ROS 2 or rosbag2 recording.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import v22_orchestrate as app
from rescuemind.stack_supervisor import StackFailure


class FakeSupervisor:
    events = []
    mission_error = None
    finalization_error = None
    def __init__(self, folder):
        self.log_dir=Path(folder)
        FakeSupervisor.events.append('construct')
    def __enter__(self):
        return self
    def __exit__(self,*exc):
        FakeSupervisor.events.append('shutdown')
    def start_service(self, spec):
        FakeSupervisor.events.append('service:'+spec.name)
    def ensure_alive(self):
        return None
    def wait_readiness(self,*a,**kw):
        FakeSupervisor.events.append('readiness')
    def run_mission(self, spec, timeout):
        FakeSupervisor.events.append('mission')
        (self.log_dir/'mission.json').write_text(json.dumps({'intent':{'item':'water'}}))
        if FakeSupervisor.mission_error:
            raise StackFailure(FakeSupervisor.mission_error)
        return 0
    def stop_service(self, name):
        FakeSupervisor.events.append('finalize:'+name)
        if FakeSupervisor.finalization_error:
            raise StackFailure(FakeSupervisor.finalization_error)
        return {'service':name,'signal':'SIGINT','process_finished_before_metadata_audit':True}


class OrchestrationContractTests(unittest.TestCase):
    def setUp(self):
        FakeSupervisor.events=[]
        FakeSupervisor.mission_error=None
        FakeSupervisor.finalization_error=None
        self.temp_runs=[]
        self.root=Path(app.ROOT)
        self.run_root=self.root/'outputs'/'runs'
        self.before=set(p.name for p in self.run_root.iterdir()) if self.run_root.exists() else set()
        self.stack=self.enterContext(patch.object(app,'Supervisor',FakeSupervisor))
        self.enterContext(patch.object(app,'check_prerequisites',return_value=None))
        self.enterContext(patch.object(app.time,'sleep',return_value=None))
        self.enterContext(patch('rescuemind.runtime_guard_graph.audit_watch_jsonl',return_value={'pass':True}))
        self.enterContext(patch('rescuemind.v26_stationary_evidence.audit_stationarity',return_value={'pass':True}))
        self.enterContext(patch('rescuemind.v27_image_evidence.audit_capture',return_value={'pass':True}))
        self.enterContext(patch('rescuemind.v28_clock_evidence.audit_clock_capture',return_value={'pass':True}))
        self.enterContext(patch('rescuemind.v24_trial_outcome.classify_negative_run',side_effect=self.denial_audit))
        self.enterContext(patch('rescuemind.bag_evidence.audit_bag_metadata',side_effect=self.bag_audit))
        self.enterContext(patch('rescuemind.run_completion.validate',return_value={'pass':True}))
        self.enterContext(patch('rescuemind.motion_evidence.audit_motion',return_value={'pass':True}))
        self.enterContext(patch('rescuemind.causal_evidence.audit_causal',return_value={'pass':True}))
    def tearDown(self):
        if self.run_root.exists():
            for folder in self.run_root.iterdir():
                if folder.name not in self.before:
                    shutil.rmtree(folder)
    def denial_audit(self,*args,**kwargs):
        FakeSupervisor.events.append('audit_denial')
        return {'pass':True}
    def bag_audit(self,*args,**kwargs):
        FakeSupervisor.events.append('audit_bag')
        return {'pass':True}
    def execute(self,scene='swapped',bag=True):
        args=['--run','--scenario','live','--scene',scene]
        if bag:args.append('--capture-rosbag')
        code=app.main(args)
        folders=sorted((p for p in self.run_root.iterdir() if p.name not in self.before),key=lambda p:p.stat().st_mtime)
        self.assertEqual(len(folders),1)
        return code,json.loads((folders[0]/'stack_result.json').read_text())

    def test_denial_finalizes_recorder_before_evidence_audit(self):
        FakeSupervisor.mission_error='mission failed (exit=2); see mission.log'
        code,outcome=self.execute()
        self.assertEqual(code,0)
        self.assertEqual(outcome['state'],'COMPLETED_EXPECTED_DENIAL')
        self.assertEqual(outcome['rosbag_finalization']['signal'],'SIGINT')
        seq=FakeSupervisor.events
        self.assertLess(seq.index('mission'),seq.index('finalize:rosbag_recorder'))
        self.assertLess(seq.index('finalize:rosbag_recorder'),seq.index('audit_denial'))
        self.assertLess(seq.index('finalize:rosbag_recorder'),seq.index('audit_bag'))

    def test_denial_recorder_failure_cannot_be_marked_success(self):
        FakeSupervisor.mission_error='mission failed (exit=2); see mission.log'
        FakeSupervisor.finalization_error='recorder forced kill'
        code,outcome=self.execute()
        self.assertEqual(code,2)
        self.assertEqual(outcome['state'],'FAILED')
        self.assertNotIn('audit_denial',FakeSupervisor.events)
        self.assertNotIn('audit_bag',FakeSupervisor.events)

    def test_denial_missing_bag_metadata_cannot_be_marked_success(self):
        FakeSupervisor.mission_error='mission failed (exit=2); see mission.log'
        def fail(*a,**kw):
            FakeSupervisor.events.append('audit_bag')
            raise ValueError('metadata missing')
        with patch('rescuemind.bag_evidence.audit_bag_metadata',side_effect=fail):
            code,outcome=self.execute()
        self.assertEqual(code,2)
        self.assertEqual(outcome['state'],'FAILED')
        self.assertIn('metadata missing',outcome['negative_evidence_failure'])

    def test_denial_without_optional_bag_still_needs_physical_audit(self):
        FakeSupervisor.mission_error='mission failed (exit=2); see mission.log'
        code,outcome=self.execute(bag=False)
        self.assertEqual(code,0)
        self.assertEqual(outcome['state'],'COMPLETED_EXPECTED_DENIAL')
        self.assertNotIn('finalize:rosbag_recorder',FakeSupervisor.events)
        self.assertIn('audit_denial',FakeSupervisor.events)

    def test_denial_rejected_if_runtime_guard_graph_audit_missing(self):
        from rescuemind.runtime_guard_graph import GraphMonitorFault
        FakeSupervisor.mission_error='mission failed (exit=2); see mission.log'
        with patch('rescuemind.runtime_guard_graph.audit_watch_jsonl',side_effect=GraphMonitorFault('missing runtime monitor log')):
            code,outcome=self.execute(bag=False)
        self.assertEqual(code,2)
        self.assertEqual(outcome['state'],'FAILED')
        self.assertIn('missing runtime monitor log',outcome['negative_evidence_failure'])

    def test_success_rejected_if_runtime_guard_graph_audit_missing(self):
        from rescuemind.runtime_guard_graph import GraphMonitorFault
        with patch('rescuemind.runtime_guard_graph.audit_watch_jsonl',side_effect=GraphMonitorFault('missing runtime monitor log')):
            code,outcome=self.execute(scene='nominal',bag=False)
        self.assertEqual(code,2)
        self.assertEqual(outcome['state'],'FAILED')
        self.assertIn('missing runtime monitor log',outcome['error'])

    def test_live_mission_record_schema_matches_release(self):
        source=(self.root/'ros/gazebo_waypoint_mission.py').read_text()
        self.assertIn("record={'version':'3.1'",source)

    def test_plan_without_rosbag_lists_independent_observer(self):
        from io import StringIO
        import contextlib
        output=StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(app.main(['--plan','--scenario','motion-check']),0)
        spec=json.loads(output.getvalue())
        self.assertTrue(any('odom_evidence_recorder.py' in str(s) for s in spec['services']))
        self.assertFalse(any('rosbag_recorder' in str(s) for s in spec['services']))

    def test_persisted_stack_plan_records_real_service_directories(self):
        code,outcome=self.execute(scene='nominal',bag=True)
        self.assertEqual(code,0)
        run_id=outcome['run_id']
        p=self.run_root/run_id/'stack_plan.json'
        plan=json.loads(p.read_text())
        self.assertEqual(plan['run_id'],run_id)
        self.assertNotIn('<run_id>',json.dumps(plan))
        self.assertIn(run_id,json.dumps(plan['services']))
        self.assertIn('odom_evidence_recorder.py',json.dumps(plan['services']))

    def test_success_finalizes_and_audits_bag(self):
        code,outcome=self.execute(scene='nominal')
        self.assertEqual(code,0)
        self.assertEqual(outcome['state'],'COMPLETED')
        seq=FakeSupervisor.events
        self.assertLess(seq.index('finalize:rosbag_recorder'),seq.index('audit_bag'))

    def test_non_denial_exit_cannot_be_reclassified(self):
        FakeSupervisor.mission_error='mission failed (exit=2); see mission.log'
        code,outcome=self.execute(scene='nominal')
        self.assertEqual(code,2)
        self.assertEqual(outcome['state'],'FAILED')
        self.assertNotIn('audit_denial',FakeSupervisor.events)
        self.assertNotIn('finalize:rosbag_recorder',FakeSupervisor.events)

    def test_mission_timeout_cannot_be_reclassified(self):
        FakeSupervisor.mission_error='mission exceeded timeout; stack teardown'
        code,outcome=self.execute()
        self.assertEqual(code,2)
        self.assertEqual(outcome['state'],'FAILED')
        self.assertNotIn('audit_denial',FakeSupervisor.events)
        self.assertNotIn('finalize:rosbag_recorder',FakeSupervisor.events)

if __name__=='__main__':unittest.main()
