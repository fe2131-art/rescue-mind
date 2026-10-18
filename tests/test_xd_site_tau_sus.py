"""I-33 (exploratory per-site tau_sus): the read-out follows the rule written before the computation."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import xd_site_tau_sus as st  # noqa: E402

F = ROOT / 'experiments/results/devset_xd_h36_tiles.json'


@unittest.skipUnless(F.is_file(), 'XD records not present')
class SiteTauSus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = st.analyse(json.loads(F.read_text())['records'])

    def test_threshold_leaves_at_most_15_percent_of_calibration_worlds(self):
        self.assertGreater(self.out['tau_sus_site'], 0.005)         # the depot's fire-free views score above the arena-calibrated 0.005

    def test_readout_matches_rule(self):
        t, r = self.out['test'], self.out['readout']
        self.assertEqual(r['trigger_rate_at_most_15pct'], t['triggered'] / t['twins_with_extra'] <= 0.15)
        self.assertEqual(r['removes_at_least_half_of_misses'], t['look_around_misses'] - t['adaptive_misses'] >= 0.5 * t['look_around_misses'])
        self.assertEqual(self.out['promising'], all(r.values()))

    def test_adaptive_never_misses_more_than_look_around(self):
        self.assertLessEqual(self.out['test']['adaptive_misses'], self.out['test']['look_around_misses'])


if __name__ == '__main__':
    unittest.main()
