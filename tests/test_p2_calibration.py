"""P2: the registered calibration rule, on synthetic scores (no model, no data files)."""
import unittest

import scripts.p2_calibration as p2


def recs(hazard_probs, none_probs):
    return ([{'category': 'smoke', 'hazard_prob': x} for x in hazard_probs] +
            [{'category': 'none', 'hazard_prob': x} for x in none_probs])


class CalibrationRule(unittest.TestCase):
    def test_grid(self):
        self.assertEqual(p2.GRID[:5], [0.01, 0.02, 0.05, 0.1, 0.15])
        self.assertEqual(p2.GRID[-1], 0.95)
        self.assertEqual(len(p2.GRID), 21)

    def test_largest_tau_with_recall_at_least_95(self):
        # 20 hazard images: 19 score 0.5, one scores 0.03 -> recall 0.95 holds up to tau 0.5 and is lost above it
        c = recs([0.5] * 19 + [0.03], [0.2] * 10)
        self.assertEqual(p2.choose_tau(c), 0.5)
        # two low ones -> recall 0.90 at tau 0.5; the largest tau with recall >= 0.95 is then 0.02
        c = recs([0.5] * 18 + [0.03, 0.03], [0.2] * 10)
        self.assertEqual(p2.choose_tau(c), 0.02)

    def test_tau_is_inclusive(self):
        self.assertEqual(p2.choose_tau(recs([0.1] * 20, [0.0] * 5)), 0.1)

    def test_no_feasible_tau(self):
        self.assertIsNone(p2.choose_tau(recs([0.0] * 20, [0.0] * 5)))

    def test_wording_lower_false_alarm_wins_and_ties_go_to_h36(self):
        h36 = recs([0.5] * 20, [0.6] * 4 + [0.0] * 6)           # tau 0.5 -> FA 0.4
        h35 = recs([0.5] * 20, [0.6] * 1 + [0.0] * 9)           # tau 0.5 -> FA 0.1
        w, info = p2.choose_wording({'h36': h36, 'h35': h35})
        self.assertEqual(w, 'h35')
        self.assertAlmostEqual(info['h35']['cal_fa'], 0.1)
        tie = recs([0.5] * 20, [0.6] * 2 + [0.0] * 8)
        self.assertEqual(p2.choose_wording({'h36': tie, 'h35': tie})[0], 'h36')

    def test_infeasible_wording_is_excluded(self):
        bad = recs([0.0] * 20, [0.0] * 5)
        good = recs([0.5] * 20, [0.0] * 5)
        self.assertEqual(p2.choose_wording({'h36': bad, 'h35': good})[0], 'h35')
        self.assertIsNone(p2.choose_wording({'h36': bad, 'h35': bad})[0])

    def test_claim_boundaries(self):
        self.assertTrue(p2.claim(0.90, 0.20))
        self.assertFalse(p2.claim(0.899, 0.10))
        self.assertFalse(p2.claim(0.95, 0.201))

    def test_endpoint_has_wilson_ci(self):
        e = p2.endpoint(recs([0.5] * 9 + [0.0], [0.5] * 2 + [0.0] * 8), 0.05)
        self.assertEqual((e['recall']['k'], e['recall']['n']), (9, 10))
        self.assertEqual((e['false_alarm']['k'], e['false_alarm']['n']), (2, 10))
        self.assertLess(e['recall']['ci95'][0], 0.9)


if __name__ == '__main__':
    unittest.main()
