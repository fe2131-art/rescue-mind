import json
import math
import unittest
from pathlib import Path
from rescuemind.camera_aim import aim_at_station,station_centers
from rescuemind.waypoint import Pose2, wrap, simulate_route
from rescuemind.scene_variants import audit_scenarios

ROOT=Path(__file__).resolve().parents[1]

class CameraAimTests(unittest.TestCase):
    def test_already_aligned(self):
        self.assertTrue(aim_at_station(Pose2(0.,0.,math.pi/4),(1.,1.)).aligned)
    def test_turns_left(self):
        c=aim_at_station(Pose2(0,0,0),(0.,1.))
        self.assertGreater(c.angular,0)
        self.assertFalse(c.aligned)
    def test_turns_right(self):
        self.assertLess(aim_at_station(Pose2(0,0,0),(0.,-1.)).angular,0)
    def test_zero_translation_implicit(self):
        self.assertEqual(len(aim_at_station(Pose2(1,1,0),(2,2)).__dataclass_fields__),3)
    def test_safe_bearing(self):
        with self.assertRaises(ValueError):aim_at_station(Pose2(0,0,0),(0.01,0.01))
    def test_nan_rejected(self):
        with self.assertRaises(ValueError):aim_at_station(Pose2(0,0,0),(float('nan'),2))
    def test_bool_rejected(self):
        with self.assertRaises(ValueError):aim_at_station(Pose2(0,0,0),(True,2))
    def test_bad_limit_rejected(self):
        with self.assertRaises(ValueError):aim_at_station(Pose2(0,0,0),(2,2),tolerance_rad=.5)
    def test_locked_station_centers(self):
        c=json.loads((ROOT/'configs/gazebo_station_centers.json').read_text())
        self.assertEqual(station_centers(c)['water'],(2.,2.))
    def test_wrong_geometry_rejected(self):
        with self.assertRaises(ValueError):station_centers({'water':[2.01,2],'medicine':[-2,2]})
    def test_controller_reaches_heading(self):
        for supply,goal in [('water',(2.,2.)),('medicine',(-2.,2.))]:
            station={'water':(1.18,1.13),'medicine':(-1.16,1.10)}[supply]
            # representative reached pose pointed somewhere else
            pose=Pose2(*station,0.)
            aligned=False
            for _ in range(500):
                c=aim_at_station(pose,goal)
                if c.aligned:
                    aligned=True;break
                pose=Pose2(pose.x,pose.y,wrap(pose.yaw+c.angular*.05))
            self.assertTrue(aligned)
            self.assertLessEqual(abs(c.bearing_error_rad),.1)
    def test_sdf_variant_and_config_are_consistent(self):
        self.assertTrue(audit_scenarios(ROOT/'worlds/scenarios')['pass'])
        c=station_centers(json.loads((ROOT/'configs/gazebo_station_centers.json').read_text()))
        self.assertEqual(c['water'],(2.,2.))
    def test_real_ros_node_uses_aim_gate(self):
        code=(ROOT/'ros/gazebo_waypoint_mission.py').read_text()
        self.assertIn('camera_aim_aligned',code)
        self.assertLess(code.index("'camera_aim_aligned'"),code.index("'checkpoint_frame'"))
        self.assertIn('camera aiming timed out; VLM inference withheld',code)

if __name__=='__main__':unittest.main()
