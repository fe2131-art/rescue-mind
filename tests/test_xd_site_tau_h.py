"""I-35 (exploratory per-site tau_h): the selection and the read-out follow the rule written before the computation."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import xd_site_tau_h as st  # noqa: E402

F = ROOT / 'experiments/results/devset_xd_h36_tiles.json'


@unittest.skipUnless(F.is_file(), 'XD records not present')
class SiteTauH(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = st.analyse(json.loads(F.read_text())['records'])

    def test_smallest_grid_value_meeting_95_percent(self):
        rates = {float(k): v for k, v in self.out['calibration_correct_approval_rate'].items()}
        self.assertEqual(self.out['tau_h_site'], min(t for t in st.GRID if rates[t] >= 0.95))

    def test_readout_matches_rule(self):
        b, s, r = self.out['test_frozen_0.05'], self.out['test_site'], self.out['readout']
        self.assertEqual(r['hard_misses_at_most_half'], s['hard_misses'] <= 0.5 * b['hard_misses'])
        self.assertEqual(self.out['promising'], all(r.values()))


if __name__ == '__main__':
    unittest.main()
