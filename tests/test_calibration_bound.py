"""The split-conformal false-stop bound of a calibrated threshold: exact on exchangeable draws, and the W twins give 75 worlds."""
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import calibration_bound as cb  # noqa: E402


class Bound(unittest.TestCase):
    def test_bound_values(self):
        self.assertAlmostEqual(cb.false_stop_bound(75), 1 / 76)
        with self.assertRaises(ValueError):
            cb.false_stop_bound(0)

    def test_monte_carlo_rate_is_at_most_the_bound(self):
        rng = random.Random(7)
        m, trials, hit = 20, 40000, 0
        for _ in range(trials):
            cal = [rng.lognormvariate(-6, 1) for _ in range(m)]
            hit += rng.lognormvariate(-6, 1) >= max(cal)      # tau = max of the calibration scores, the loosest allowed
        self.assertLessEqual(hit / trials, cb.false_stop_bound(m) + 0.005)       # equality in expectation: 1/21 = 0.0476

    def test_world_maxima_take_the_largest_view_and_skip_fire_and_extra_views(self):
        mk = lambda w, v, p, kind='twin', extra=False: {'world_id': w, 'world_kind': kind, 'view': v, 'extra_view': extra, 'passes': {'1': {'scores': {'hazard_prob': p}}}}
        recs = [mk('a', 'F', .001), mk('a', 'L', .004), mk('a', 'R', .002), mk('a', 'L2', .9, extra=True), mk('b', 'F', .003), mk('f', 'F', .9, kind='fire')]
        self.assertEqual(cb.world_maxima(recs), [.003, .004])


if __name__ == '__main__':
    unittest.main()
