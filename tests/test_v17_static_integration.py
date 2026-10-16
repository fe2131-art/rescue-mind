import tempfile
import unittest
from pathlib import Path
from shutil import copytree
from rescuemind.stack_contract import check
ROOT=Path(__file__).resolve().parents[1]

class StaticCrossFileTests(unittest.TestCase):
    def test_actual_project_contract(self):
        result=check(ROOT)
        self.assertTrue(result['ok'],result['issues'])
    def test_bridge_wrong_direction_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            (p/'scripts').mkdir();(p/'worlds').mkdir();(p/'configs').mkdir()
            for name in ('bridge_direct_gazebo.sh','v16_orchestrate.py','v15_live_readiness.sh'):
                (p/'scripts'/name).write_text((ROOT/'scripts'/name).read_text())
            (p/'worlds/rescuemind_test_arena.sdf').write_bytes((ROOT/'worlds/rescuemind_test_arena.sdf').read_bytes())
            (p/'configs/gazebo_waypoints.json').write_bytes((ROOT/'configs/gazebo_waypoints.json').read_bytes())
            (p/'configs/ros_gz_bridge_v20.yaml').write_bytes((ROOT/'configs/ros_gz_bridge_v20.yaml').read_bytes())
            f=p/'configs/ros_gz_bridge_v20.yaml'
            f.write_text(f.read_text().replace('direction: ROS_TO_GZ','direction: GZ_TO_ROS'))
            self.assertIn('bridge_contract_missing:/cmd_vel',check(p)['issues'])
    def test_missing_guard_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            (p/'scripts').mkdir();(p/'worlds').mkdir();(p/'configs').mkdir()
            for name in ('bridge_direct_gazebo.sh','v16_orchestrate.py','v15_live_readiness.sh'):
                (p/'scripts'/name).write_text((ROOT/'scripts'/name).read_text())
            (p/'worlds/rescuemind_test_arena.sdf').write_bytes((ROOT/'worlds/rescuemind_test_arena.sdf').read_bytes())
            (p/'configs/gazebo_waypoints.json').write_bytes((ROOT/'configs/gazebo_waypoints.json').read_bytes())
            (p/'configs/ros_gz_bridge_v20.yaml').write_bytes((ROOT/'configs/ros_gz_bridge_v20.yaml').read_bytes())
            f=p/'scripts/v16_orchestrate.py';f.write_text(f.read_text().replace('start_velocity_guard.sh','off.sh'))
            self.assertIn('launcher_bypasses_guard',check(p)['issues'])
