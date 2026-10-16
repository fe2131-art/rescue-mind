import unittest
from pathlib import Path
from rescuemind.v25_projection import estimate_projection
R=Path(__file__).resolve().parents[1]
class ProjectionTests(unittest.TestCase):
    def test_nominal_centers_inside_ideal_fov(self):
        p=estimate_projection(R,'nominal')
        self.assertTrue(p['objects']['water']['center_inside_fov_with_margin'])
        self.assertTrue(p['objects']['medicine']['center_inside_fov_with_margin'])
    def test_empty_no_props(self):
        p=estimate_projection(R,'empty')
        self.assertFalse(p['objects']['water']['present'])
        self.assertFalse(p['objects']['medicine']['present'])
    def test_swapped_both_present(self):
        p=estimate_projection(R,'swapped')
        self.assertTrue(p['objects']['water']['present'])
        self.assertTrue(p['objects']['medicine']['present'])
    def test_invalid_scenario(self):
        with self.assertRaises(ValueError):estimate_projection(R,'nonsense')
