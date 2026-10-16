import io
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.gazebo_transport_contract import (
    EXPECTED, PUBLISHED, GazeboContractError, parse_topic_list,
    audit_runtime_topics, validate_static
)
from scripts.v21_gz_transport_probe import run_probe
from scripts.v21_orchestrate import build_plan

WORLD=ROOT/'worlds/rescuemind_test_arena.sdf'
YAML=ROOT/'configs/ros_gz_bridge_v20.yaml'
OK='\n'.join(sorted(PUBLISHED))+'\n'

class GazeboContractTests(unittest.TestCase):
    def test_actual_static_scene(self):
        r=validate_static(WORLD,YAML)
        self.assertTrue(r['ok'])
        self.assertEqual(r['mappings'],6)  # + /ground_truth/odom (v3.3)

    def test_all_required_topics(self):
        result=audit_runtime_topics(OK)
        self.assertTrue(result['ok'])
        self.assertEqual(result['missing'],[])

    def test_cmd_vel_optional_until_bridge(self):
        self.assertNotIn('/cmd_vel', PUBLISHED)
        self.assertTrue(audit_runtime_topics(OK)['ok'])

    def test_missing_camera_fails(self):
        r=audit_runtime_topics('\n'.join(PUBLISHED-{'/camera'}))
        self.assertFalse(r['ok'])
        self.assertEqual(r['missing'],['/camera'])

    def test_missing_clock_fails(self):
        self.assertIn('/world/rescuemind_arena/clock',audit_runtime_topics(
            '\n'.join(PUBLISHED-{'/world/rescuemind_arena/clock'}))['missing'])

    def test_extra_topics_do_not_fail(self):
        self.assertTrue(audit_runtime_topics(OK+'/extra\n')['ok'])

    def test_partial_names_do_not_match(self):
        self.assertFalse(audit_runtime_topics(OK.replace('/camera\n','/camera_malformed\n'))['ok'])

    def test_empty_list_fails(self):
        with self.assertRaises(GazeboContractError):parse_topic_list(' \n')

    def test_invalid_line_fails(self):
        with self.assertRaises(GazeboContractError):parse_topic_list('command not found\n')

    def test_duplicate_entries_coalesce(self):
        self.assertEqual(parse_topic_list('/scan\n/scan\n'), {'/scan'})

    def test_static_mutation_bad_world(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'scene.sdf'
            path.write_text(WORLD.read_text().replace('name="rescuemind_arena"','name="typo"',1))
            with self.assertRaises(GazeboContractError):validate_static(path,YAML)

    def test_static_mutation_camera_wrong_topic(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'scene.sdf'
            path.write_text(WORLD.read_text().replace('<topic>/camera</topic>','<topic>/wrong_camera</topic>',1))
            with self.assertRaises(GazeboContractError):validate_static(path,YAML)

    def test_static_mutation_bridge_bad_direction(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.yaml'
            path.write_text(YAML.read_text().replace('direction: GZ_TO_ROS','direction: ROS_TO_GZ',1))
            with self.assertRaises(GazeboContractError):validate_static(WORLD,path)

    def test_runtime_retry(self):
        values=['/scan\n', OK]
        def run(*args,**kwargs):
            return SimpleNamespace(returncode=0,stdout=values.pop(0),stderr='')
        result=run_probe(attempts=2,interval=0,runner=run,sleeper=lambda _:None)
        self.assertTrue(result['ok']);self.assertEqual(result['attempts_used'],2)

    def test_runtime_error_fails_closed(self):
        def run(*args,**kwargs):raise FileNotFoundError('gz unavailable')
        result=run_probe(attempts=2,interval=0,runner=run,sleeper=lambda _:None)
        self.assertFalse(result['ok'])
        self.assertEqual(result['attempts_used'],2)

    def test_runtime_nonzero_fails_closed(self):
        def run(*args,**kwargs):
            return SimpleNamespace(returncode=12,stdout=OK,stderr='transport error')
        self.assertFalse(run_probe(attempts=1,runner=run)['ok'])

    def test_orchestrator_probes_transport_before_motion(self):
        plan=build_plan('motion-check','',mission_timeout=400)
        self.assertTrue(plan['readiness'][-1].endswith('v21_live_readiness.sh'))
        self.assertIn('velocity_guard', [x.name for x in plan['services']])

    def test_orchestrator_retains_jev_live(self):
        plan=build_plan('live','避難所Bに水',mission_timeout=400)
        self.assertIn('--run-live',plan['mission'].argv[-1])
        self.assertIn('--instruction',plan['mission'].argv[-1])

if __name__=='__main__':unittest.main()
