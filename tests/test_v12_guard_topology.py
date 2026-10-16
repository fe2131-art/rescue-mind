import unittest
import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
class TestGuardWiring(unittest.TestCase):
    def test_guard_receives_requested_and_exclusively_publishes_actual_topic(self):
        src=(ROOT/'ros/guarded_cmd_relay.py').read_text()
        task=(ROOT/'ros/gazebo_waypoint_mission.py').read_text()
        self.assertIn("self.create_subscription(Twist,'/rescuemind/cmd_vel_request'",src)
        self.assertIn("self.create_publisher(Twist,'/cmd_vel'",src)
        self.assertIn("default='/rescuemind/cmd_vel_request'",task)
        self.assertIn('independent velocity guard missing',task)
        self.assertIn('a.relay_required=not a.legacy_direct_motion_check',task)
    def test_bridge_still_exposes_guard_output_to_gazebo(self):
        src=(ROOT/'scripts/bridge_direct_gazebo.sh').read_text()
        world=ET.parse(ROOT/'worlds/rescuemind_test_arena.sdf').getroot()
        self.assertIn('ros_gz_bridge_v20.yaml',src)
        from rescuemind.bridge_contract import audit
        self.assertTrue(audit(ROOT/'worlds/rescuemind_test_arena.sdf',ROOT/'configs/ros_gz_bridge_v20.yaml')['ok'])
        self.assertEqual(world.find('.//plugin[@name="gz::sim::systems::DiffDrive"]/topic').text,'/cmd_vel')
    def test_live_cli_cannot_bypass_guard_with_direct_topic(self):
        run=subprocess.run(['python3',str(ROOT/'ros/gazebo_waypoint_mission.py'),
                            '--run-live','--cmd-topic','/cmd_vel'],capture_output=True,text=True)
        self.assertNotEqual(run.returncode,0)
        self.assertIn('guarded missions',run.stderr)
    def test_unguarded_option_not_allowed_for_live_ai(self):
        run=subprocess.run(['python3',str(ROOT/'ros/gazebo_waypoint_mission.py'),
                            '--run-live','--legacy-direct-motion-check'],capture_output=True,text=True)
        self.assertNotEqual(run.returncode,0)
        self.assertIn('only for --motion-check',run.stderr)
