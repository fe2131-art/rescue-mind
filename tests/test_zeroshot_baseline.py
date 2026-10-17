"""Study Z: the pre-registered threshold-selection rule (synthetic data, no model)."""
import unittest

from scripts.zeroshot_baseline import TAU_H_GRID, TAU_S_GRID, approves, claim_outcome, select_thresholds


def row(expected, station='water', p_station=0.9, hazard=0.01):
    other = (1 - p_station) / 2
    probs = {'water': other, 'medicine': other, 'other': other}
    probs[station] = p_station
    return {'expected': expected, 'station': station, 'supply_probs': probs, 'hazard_max': hazard}


class Grid(unittest.TestCase):
    def test_grids_match_prereg(self):
        self.assertEqual(TAU_S_GRID, [0.34, 0.40, 0.46, 0.52, 0.58, 0.64, 0.70, 0.76, 0.82, 0.88, 0.94])
        self.assertEqual(len(TAU_H_GRID), 19)
        self.assertEqual((TAU_H_GRID[0], TAU_H_GRID[-1]), (0.05, 0.95))


class Approves(unittest.TestCase):
    def test_rule(self):
        r = row('allow', p_station=0.8, hazard=0.2)
        args = (r['station'], r['supply_probs'], r['hazard_max'])
        self.assertTrue(approves(*args, 0.8, 0.25))
        self.assertFalse(approves(*args, 0.85, 0.25))     # supply prob below tau_s
        self.assertFalse(approves(*args, 0.5, 0.2))       # hazard must be strictly below tau_h
        wrong = row('deny', station='medicine')
        wrong['supply_probs'] = {'water': 0.9, 'medicine': 0.05, 'other': 0.05}
        self.assertFalse(approves('medicine', wrong['supply_probs'], 0.0, 0.34, 0.95))   # arg-max is not requested


class Selection(unittest.TestCase):
    def test_fewest_fa_then_most_ca_then_lower_tau_h(self):
        rows = [row('allow', p_station=0.95, hazard=0.02), row('allow', p_station=0.95, hazard=0.12),
                row('deny', p_station=0.95, hazard=0.50)]
        t = select_thresholds(rows)
        # hazard 0.50 deny is refused iff tau_h <= 0.50; the allows at 0.02 / 0.12 are approved iff tau_h > 0.02 / 0.12.
        # FA = 0 needs tau_h <= 0.50; most CA (2) needs tau_h > 0.12 -> tau_h in {0.15 .. 0.50}; lowest = 0.15.
        self.assertEqual((t['dev_false_approvals'], t['dev_correct_approvals']), (0, 2))
        self.assertEqual(t['tau_h'], 0.15)
        self.assertEqual(t['tau_s'], 0.34)      # residual tie in tau_s -> lower value
        self.assertEqual((t['dev_n_deny'], t['dev_n_allow']), (1, 2))

    def test_fa_dominates_ca(self):
        # the deny image is indistinguishable by hazard from allow images; FA minimisation must trade away all CA
        rows = [row('deny', p_station=0.9, hazard=0.30)] + [row('allow', p_station=0.9, hazard=0.30)] * 5
        t = select_thresholds(rows)
        self.assertEqual(t['dev_false_approvals'], 0)
        self.assertEqual(t['dev_correct_approvals'], 0)
        self.assertEqual(t['tau_h'], 0.05)

    def test_supply_threshold_is_used(self):
        rows = [row('deny', p_station=0.45, hazard=0.0), row('allow', p_station=0.9, hazard=0.0)]
        t = select_thresholds(rows)
        self.assertEqual((t['dev_false_approvals'], t['dev_correct_approvals']), (0, 1))
        self.assertEqual(t['tau_s'], 0.46)      # 0.34 and 0.40 would approve the deny image (p=0.45)

    def test_ignores_nothing_but_given_rows(self):
        # selection is a pure function of the rows it is given (no hidden T1/T2 access)
        rows = [row('allow'), row('deny', hazard=0.9)]
        self.assertEqual(select_thresholds(rows), select_thresholds(list(rows)))


class Claim(unittest.TestCase):
    def mk(self, fa_o, fa_z, ca_o, ca_z, pf, pc):
        return {'ours': {'FA': fa_o, 'CA': ca_o}, 'baseline': {'FA': fa_z, 'CA': ca_z},
                'mcnemar': {'deny': {'p': pf}, 'allow': {'p': pc}}}

    def test_outcomes(self):
        self.assertIn('safer', claim_outcome({'t1': self.mk(0, 20, 100, 100, 0.001, 1.0)}))
        self.assertIn('more available', claim_outcome({'t1': self.mk(5, 5, 190, 100, 1.0, 0.001)}))
        self.assertEqual(claim_outcome({'t1': self.mk(0, 20, 100, 190, 0.001, 0.001)}).split(' (')[0],
                         'no significant difference')   # safer but significantly less available -> claim fails
        self.assertTrue(claim_outcome({'t1': self.mk(3, 4, 100, 100, 1.0, 1.0)}).startswith('no significant difference'))


if __name__ == '__main__':
    unittest.main()
