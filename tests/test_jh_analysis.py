"""Study JH analysis: AUC, Fisher, overlap and the JH1 rule on synthetic worlds (no model, no GPU)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import jh_analysis as jh  # noqa: E402


class Pure(unittest.TestCase):
    def test_auc(self):
        self.assertEqual(jh.roc_auc([0.9, 0.8], [0.1, 0.2]), 1.0)
        self.assertEqual(jh.roc_auc([0.5], [0.5]), 0.5)

    def test_fisher_and_phi(self):
        self.assertAlmostEqual(jh.fisher_exact_two_sided(3, 0, 0, 3), 0.1, places=3)
        self.assertAlmostEqual(jh.phi(3, 0, 0, 3), 1.0)
        self.assertAlmostEqual(jh.fisher_exact_two_sided(1, 1, 1, 1), 1.0)

    def test_overlap_counts_and_jh1(self):
        fire = [f'f{i}' for i in range(9)]
        clean = [f'c{i}' for i in range(40)]
        fq = {w: i >= 3 for i, w in enumerate(fire)}            # Q misses f0, f1, f2
        fq.update({w: False for w in clean})
        fj = {w: i != 0 for i, w in enumerate(fire)}            # J misses f0 only (shared) -> joint 1
        fj.update({w: i == 0 for i, w in enumerate(clean)})     # J falsely stops c0
        o = jh.overlap(fq, fj, fire, clean)
        self.assertEqual((o['miss_Q'], o['miss_J'], o['miss_joint']), (3, 1, 1))
        self.assertEqual((o['false_stops_Q'], o['false_stops_J'], o['false_stops_union']), (0, 1, 1))
        self.assertTrue(jh.jh1(o)['holds'])                     # 1 <= floor(2*3/3) = 2 and 1/40 = 2.5% <= 5%
        o2 = dict(o, miss_joint=3)
        self.assertFalse(jh.jh1(o2)['miss_reduction_ok'])
        self.assertFalse(jh.jh1(dict(o, false_stop_union_rate=0.06))['false_stop_ok'])

    def test_tau_rounds_up_to_the_thousandth(self):
        self.assertEqual(jh.tau_of([0.0101] * 10 + [0.0123]), 0.013)


if __name__ == '__main__':
    unittest.main()
