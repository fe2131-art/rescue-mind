"""Statistics and decision-rule ablations used for the paper (scripts/t1_analysis.py)."""
import unittest

import scripts.t1_analysis as ta


def rec(station, p1, p2, h1=0.0, h2=0.0, expected='allow', **kw):
    mk = lambda p, h: {'scores': {'method': 'closed_set_logprob', 'supply_probs': p, 'hazard_prob': h}, 'latency_s': 1.0}
    return {'station': station, 'passes': {'1': mk(p1, h1), '2': mk(p2, h2)}, 'expected': expected, **kw}


class Stats(unittest.TestCase):
    def test_wilson_known_values(self):
        lo, hi = ta.wilson(0, 396)
        self.assertEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 0.0096, places=4)
        lo, hi = ta.wilson(55, 60)
        self.assertAlmostEqual(lo, 0.8193, places=3)
        self.assertAlmostEqual(hi, 0.9639, places=3)

    def test_mcnemar_exact(self):
        self.assertEqual(ta.mcnemar_exact(0, 0), 1.0)
        self.assertAlmostEqual(ta.mcnemar_exact(0, 6), 0.03125)
        self.assertAlmostEqual(ta.mcnemar_exact(3, 3), 1.0)


class Rules(unittest.TestCase):
    W = {'water': .9, 'medicine': .05, 'other': .05}

    def test_full_rule_needs_both_passes(self):
        r = rec('water', self.W, {'water': .4, 'medicine': .5, 'other': .1})
        self.assertFalse(ta.decide(r))
        self.assertTrue(ta.decide(r, passes='1'))

    def test_threshold_and_hazard(self):
        low = {'water': .45, 'medicine': .30, 'other': .25}
        self.assertFalse(ta.decide(rec('water', low, low)))
        self.assertTrue(ta.decide(rec('water', low, low), tau_s=0.0))
        fire = rec('water', self.W, self.W, h1=.7)
        self.assertFalse(ta.decide(fire))
        self.assertTrue(ta.decide(fire, use_hazard=False))

    def test_errors_fail_closed(self):
        r = rec('water', self.W, self.W)
        r['passes']['2'] = {'error': 'timeout'}
        self.assertFalse(ta.decide(r))

    def test_free_json_labels(self):
        r = {'station': 'water', 'passes': {'1': {'supply': 'water', 'scene': 'clear'}, '2': {'supply': 'water', 'scene': 'unknown'}}}
        self.assertTrue(ta.decide(r))
        r['passes']['2']['scene'] = 'hazard'
        self.assertFalse(ta.decide(r))

    def test_metrics_counts(self):
        rows = [rec('water', self.W, self.W, expected='allow'), rec('water', self.W, self.W, expected='deny')]
        m = ta.metrics(rows, [True, True])
        self.assertEqual((m['false_approvals'], m['correct_approvals']), (1, 1))


if __name__ == '__main__':
    unittest.main()
