"""Study GV readout (post hoc): threshold-decided refusals, the calibration margin and the geometry comparison (synthetic rows, no Gazebo, no model)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import gv_readout as gvr  # noqa: E402


def row(arm, p, fire=False, world='W', obs='ALLOW', unsafe=False):
    return {'arm': arm, 'fire': fire, 'world': world, 'observed': obs, 'delivery_into_fire': unsafe, 'check': {'max_p': p, 'front_p': p}}


class Readout(unittest.TestCase):
    def test_threshold_decided_only_for_wcal_refusals_below_the_default(self):
        rows = [row('wcal', 0.03, True, 'A', 'DENY_HAZARD'), row('wcal', 0.4, True, 'B', 'DENY_HAZARD'), row('wide', 0.03, True, 'C', 'DENY_HAZARD'), row('wcal', 0.02, False, 'D', 'DENY_HAZARD')]
        self.assertEqual(gvr.decided(rows), ['A'])

    def test_margin_counts_above_tau_and_calibration_maximum(self):
        calib = {'tau_cal': 0.02, 'm': 3, 'worlds': {'a': {'score': 0.004}, 'b': {'score': 0.015}, 'c': {'score': 0.009}}}
        rows = [row('wcal', 0.010), row('wcal', 0.030), row('wide', 0.020), row('wide', 0.001), row('wcal', 0.5, True), {'arm': 'wcal', 'fire': False}]
        m = gvr.margin(rows, calib)
        self.assertEqual(m['wcal'], {'n': 2, 'max_score': 0.030, 'above_tau_cal': 1, 'above_calibration_max': 1})
        self.assertEqual(m['wide'], {'n': 2, 'max_score': 0.020, 'above_tau_cal': 1, 'above_calibration_max': 1})

    def test_geometry_compares_wide_with_v36_per_world(self):
        rows = [row('v36', 0.01, True, 'A'), row('wide', 0.05, True, 'A'), row('v36', 0.04, True, 'B'), row('wide', 0.02, True, 'B'), row('v36', 0.3, True, 'C')]
        g = gvr.geometry(gvr.by_world(rows))
        self.assertEqual((g['n_pairs'], g['wide_higher'], g['wide_lower']), (2, 1, 1))
        self.assertEqual(g['median_ratio_wide_over_v36'], 2.75)


if __name__ == '__main__':
    unittest.main()
