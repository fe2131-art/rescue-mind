"""Study GV stop-rule readout (post hoc): rank rule and per-item / per-view summary on synthetic calibration worlds."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import gv_stop_readout as sr  # noqa: E402


class Readout(unittest.TestCase):
    def test_rank_rule(self):
        s = [i / 100 for i in range(1, 101)]
        self.assertEqual(sr.rank_tau(s, 0.02), 0.99)           # ceil(0.98 * 101) = 99th smallest = second largest
        self.assertEqual(sr.rank_tau(s, 0.01), 1.0)
        self.assertIsNone(sr.rank_tau([0.1] * 10, 0.01))       # ceil(0.99 * 11) = 11 > 10

    def test_summary_by_item_and_view(self):
        w = {'a': {'score': 0.02, 'item': 'water', 'views': {'F': 0.01, 'R': 0.02}}, 'b': {'score': 0.06, 'item': 'medicine', 'views': {'F': 0.01, 'R': 0.06}}}
        r = sr.summarise(w)
        self.assertEqual(r['n_at_or_above_default_0.05'], 1)
        self.assertEqual(r['by_item']['medicine']['n_at_or_above_default'], 1)
        self.assertEqual(r['by_view']['R']['max'], 0.06)
        self.assertEqual(r['top'][0]['world'], 'b')


if __name__ == '__main__':
    unittest.main()
