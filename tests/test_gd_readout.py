"""Study GD readout (post hoc): the margin of the calibration on the fire-free runs (synthetic rows, no Gazebo, no model)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import gd_readout as gdr  # noqa: E402


def row(arm, p, fire=False):
    return {'arm': arm, 'fire': fire, 'check': {'max_p': p}}


class Margin(unittest.TestCase):
    def test_counts_above_tau_and_above_the_calibration_maximum(self):
        calib = {'tau_cal': 0.02, 'm': 3, 'worlds': {'a': {'score': 0.004}, 'b': {'score': 0.015}, 'c': {'score': 0.009}}}
        rows = [row('cal', 0.010), row('cal', 0.030), row('v36', 0.020), row('v36', 0.001), row('cal', 0.5, fire=True), {'arm': 'cal', 'fire': False}]
        m = gdr.margin(rows, calib)
        self.assertEqual(m['calibration_max_score'], 0.015)
        self.assertEqual(m['cal'], {'n': 2, 'max_score': 0.030, 'above_tau_cal': 1, 'above_calibration_max': 1})
        self.assertEqual(m['v36'], {'n': 2, 'max_score': 0.020, 'above_tau_cal': 1, 'above_calibration_max': 1})

    def test_no_calibration_yields_none(self):
        m = gdr.margin([row('cal', 0.01)], {})
        self.assertIsNone(m['cal']['above_tau_cal'])


if __name__ == '__main__':
    unittest.main()
