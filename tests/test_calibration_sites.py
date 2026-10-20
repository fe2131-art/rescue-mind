"""Split-conformal threshold at a site: the rank rule, the guarantee on exchangeable draws, and the world-score extraction (synthetic scores, no model)."""
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import calibration_sites as cs  # noqa: E402


class Threshold(unittest.TestCase):
    def test_rank_rule_and_the_maximum_fallback(self):
        cal = [i / 100 for i in range(1, 100)]                      # m = 99
        tau, bound = cs.threshold(cal, 0.05)                         # r = ceil(0.95 * 100) = 95
        self.assertAlmostEqual(tau, 0.95)
        self.assertAlmostEqual(bound, 1 - 95 / 100)
        tau, bound = cs.threshold(cal[:19], 0.01)                    # r = ceil(0.99 * 20) = 20 > m = 19 -> the maximum, bound 1/20
        self.assertEqual(tau, cal[18])
        self.assertAlmostEqual(bound, 1 / 20)

    def test_false_stop_rate_is_at_most_alpha_on_exchangeable_draws(self):
        rng = random.Random(3)
        for alpha in (0.05, 0.10):
            stops, n = 0, 0
            for _ in range(3000):
                cal = [rng.lognormvariate(-6, 1) for _ in range(40)]
                tau, bound = cs.threshold(cal, alpha)
                for _ in range(5):
                    stops += rng.lognormvariate(-6, 1) > tau
                    n += 1
            self.assertLessEqual(stops / n, alpha + 0.01)

    def test_world_scores_take_the_largest_of_the_three_views_and_filter(self):
        mk = lambda w, v, p, kind='twin', **k: {'world_id': w, 'world_kind': kind, 'view': v, 'extra_view': False, 'passes': {'1': {'scores': {'hazard_prob': p}}}, **k}
        rec = [mk('a', 'F', .1), mk('a', 'L', .3), mk('a', 'R', .2), mk('a', 'L2', .9, extra_view=True), mk('b', 'F', .05, split='test'),
               mk('c', 'F', .5, 'hazard', split='test', world_perceivable_any_view=True), mk('d', 'F', .5, 'hazard', split='test', world_perceivable_any_view=False)]
        self.assertEqual(cs.world_scores(rec, 'twin'), {'a': .3, 'b': .05})
        self.assertEqual(cs.world_scores(rec, 'twin', 'test'), {'b': .05})
        self.assertEqual(cs.world_scores(rec, 'hazard', 'test', perceivable_only=True), {'c': .5})

    def test_evaluate_counts_stops_above_and_misses_at_or_below(self):
        r = cs.evaluate([.1, .2, .3, .4], [.05, .35, .5], [.2, .4, .6], 0.2)
        self.assertEqual(r['tau'], .4)                                   # r = ceil(0.8 * 5) = 4 -> the 4th smallest
        self.assertEqual(r['held_out_false_stops'], 1)                   # only .5 exceeds .4
        self.assertEqual(r['fire_misses'], 2)                            # .2 and .4 do not exceed .4


if __name__ == '__main__':
    unittest.main()
