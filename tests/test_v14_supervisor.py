import importlib.util
import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rescuemind.stack_supervisor import Supervisor, ManagedCommand, StackFailure

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('v14_orchestrate', ROOT/'scripts/v14_orchestrate.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class FakeProc:
    pid = 123456
    def __init__(self, code=None):
        self.code = code
        self.returncode = code
    def poll(self): return self.code
    def wait(self, timeout=None): return self.code


class SupervisorTests(unittest.TestCase):
    def test_dry_plan_has_required_services_and_no_bypass(self):
        p=cli.build_plan('live', '避難所Bに医療物資を届けて', mission_timeout=400)
        self.assertEqual([x.name for x in p['services']], ['gazebo','bridge','velocity_guard'])
        self.assertIn('--run-live',p['mission'].argv[-1])
        self.assertIn('/rescuemind_test_arena.sdf',p['services'][0].argv[-1])
        self.assertNotIn('--legacy-direct-motion-check',p['mission'].argv[-1])

    def test_dry_plan_contains_provenance_paths_when_requested(self):
        p=cli.build_plan('live','x',mission_timeout=400,evidence_dir=Path('/tmp/a run'))
        self.assertIn('checkpoint.jpg',p['mission'].argv[-1])
        self.assertIn('mission.json',p['mission'].argv[-1])
        self.assertIn("'/tmp/a run/mission.json'",p['mission'].argv[-1])

    def test_shell_escapes_user_instruction(self):
        instruction="x'; touch /tmp/a_fake_injection ; echo '"
        cmd=cli.shell_exec(['echo', instruction])
        self.assertEqual(shlex.split(cmd[-1].split('exec ',1)[1]), ['echo',instruction])

    def test_live_configuration_rejected_without_keys(self):
        from unittest.mock import patch
        with patch.dict('os.environ', {'TYPESAFE_API_KEY':'', 'DASHSCOPE_API_KEY':'', 'DASHSCOPE_BASE_URL':''}):
            with self.assertRaisesRegex(RuntimeError,'Jev mandatory'):
                cli.check_prerequisites('live')

    def test_exit_propagation(self):
        with tempfile.TemporaryDirectory() as t:
            with Supervisor(Path(t),spawn=lambda *a,**kw: FakeProc(12)) as sup:
                sup.start_service(ManagedCommand('gz',('gz','sim')))
                with self.assertRaisesRegex(StackFailure,'exited early'):
                    sup.ensure_alive()

    def test_readiness_refuses_failed_service(self):
        with tempfile.TemporaryDirectory() as t:
            with Supervisor(Path(t),spawn=lambda *a,**kw: FakeProc(1),
                            monotonic=lambda: 0.,sleep=lambda _:None) as sup:
                sup.start_service(ManagedCommand('bridge',('bash','bridge.sh')))
                with self.assertRaises(StackFailure):
                    sup.wait_readiness(lambda: True,10)

    def test_readiness_success_and_timeout(self):
        with tempfile.TemporaryDirectory() as t:
            values=iter([0.,0.,1.,2.,3.,4.])
            s=Supervisor(Path(t),monotonic=lambda:next(values),sleep=lambda _:None)
            with self.assertRaisesRegex(StackFailure,'deadline|timeout'):
                s.wait_readiness(lambda:False,2,1)
        with tempfile.TemporaryDirectory() as t:
            s=Supervisor(Path(t))
            s.wait_readiness(lambda:True,2)
            s.shutdown()

    def test_real_subprocess_finishes_and_logs(self):
        with tempfile.TemporaryDirectory() as t:
            with Supervisor(Path(t)) as sup:
                rc=sup.run_mission(ManagedCommand('test', (sys.executable,'-c','print(123)')),5)
            self.assertEqual(rc,0)
            self.assertIn('123',(Path(t)/'test.log').read_text())

    def test_real_subprocess_failure(self):
        with tempfile.TemporaryDirectory() as t:
            with Supervisor(Path(t)) as sup:
                with self.assertRaisesRegex(StackFailure,'mission failed'):
                    sup.run_mission(ManagedCommand('test',(sys.executable,'-c','raise SystemExit(7)')),5)

    def test_plan_cli_no_ros_required(self):
        x=subprocess.run([sys.executable,str(ROOT/'scripts/v14_orchestrate.py'),'--plan','--scenario','live'],
                         capture_output=True,text=True,timeout=10)
        self.assertEqual(x.returncode,0,x.stderr)
        self.assertEqual(json.loads(x.stdout)['scenario'],'live')

    def test_run_without_ros_fails_before_launch(self):
        # Test check only; no subprocess launch in CI. Never create a fake API result.
        with patch.object(cli.shutil,'which',return_value=None),patch.object(cli,'ROOT',ROOT):
            with self.assertRaisesRegex(StackFailure,'Missing prerequisites'):
                cli.check_prerequisites('motion-check')

    def test_invalid_command_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            with Supervisor(Path(t)) as sup:
                with self.assertRaises(ValueError):
                    sup.start_service(ManagedCommand('bad',tuple()))


if __name__ == '__main__': unittest.main()

# The ablation intentionally tests *software policy*, not perceived images.
class CausalAblationTests(unittest.TestCase):
    def test_approved_only_when_all_synthetic_gates_pass(self):
        sp=importlib.util.spec_from_file_location('v14_causal',ROOT/'scripts/v14_causal_ablation.py')
        mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod)
        rows,totals=mod.evaluate()
        self.assertEqual(len(rows),12)
        self.assertEqual(totals['dual_safety_gate']['false_approvals'],0)
        self.assertEqual(totals['dual_safety_gate']['true_approvals'],1)
        self.assertGreater(totals['jev_label_only']['false_approvals'],0)
        self.assertGreater(totals['qwen_label_only']['false_approvals'],0)
