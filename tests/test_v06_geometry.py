from pathlib import Path
import json
import unittest
import xml.etree.ElementTree as ET
from rescuemind.arena_geometry import check_route
ROOT=Path(__file__).resolve().parents[1]
class TestSdfGeometry(unittest.TestCase):
 def test_waypoints_not_through_stations(self):
  d=json.loads((ROOT/'configs/gazebo_waypoints.json').read_text())
  for item in ('water','medicine'):
   self.assertTrue(check_route([d[item],d['B']])['safe_in_approximation'])
 def test_sdf_declares_robot_and_semantic_props(self):
  root=ET.parse(ROOT/'worlds/rescuemind_test_arena.sdf').getroot()
  self.assertEqual(root.tag,'sdf')
  models={x.attrib['name']:x for x in root.findall('.//world/model')}
  self.assertTrue({'rescue_diffbot','aid_station_water','aid_station_medicine','shelter_B','sealed_water_bottles','first_aid_case'}<=models.keys())
  plugs=models['rescue_diffbot'].findall('.//plugin')
  self.assertTrue(any('DiffDrive' in p.attrib['name'] for p in plugs))
  sensors=models['rescue_diffbot'].findall('.//sensor')
  self.assertTrue({'gpu_lidar','camera'}<={s.attrib.get('type') for s in sensors})
 def test_static_geometry_warning(self):
  self.assertIn('not_gazebo',check_route([(1,1)])['kind'])
if __name__=='__main__':unittest.main()
