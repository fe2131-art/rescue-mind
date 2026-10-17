"""Fast checks of the campaign H change-rate Monte-Carlo (scripts/h_change_rate_model.py); fixed rates, no result files."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import h_change_rate_model as m  # noqa: E402

R = {'p_det': 0.8, 'p_fs': 0.05,
     'time_s': {'deliver_direct': 122.0, 'deliver_search': 150.0, 'deny_direct': 35.0, 'deny_search': 75.0,
                'deliver_skip': 75.0, 'deny_memory': 3.0}}
N = 1500


def unsafe(policy, q, **kw):
    return m.simulate(policy, q, R, n_seq=N, **kw)['unsafe_per_100']


class ChangeRateModel(unittest.TestCase):
    def test_m1age_equals_m1_when_gate_cannot_bite(self):
        # with two missions per sequence, memory is always one mission old -> identical streams and results
        for q in (0.0, 0.2):
            self.assertEqual(m.simulate('M1age', q, R, n_seq=N, n_missions=2), m.simulate('M1', q, R, n_seq=N, n_missions=2))

    def test_m1age_between_m0_and_m1_when_world_changes(self):
        self.assertLess(unsafe('M1age', 0.2), unsafe('M1', 0.2))
        self.assertGreater(unsafe('M1age', 0.2), unsafe('M0', 0.2))

    def test_m2_matches_m0(self):
        for q in (0.0, 0.1, 0.3, 0.5):
            self.assertAlmostEqual(unsafe('M2', q), unsafe('M0', q), delta=1.5)

    def test_m1_unsafe_increases_with_q(self):
        u = [unsafe('M1', q) for q in (0.0, 0.1, 0.3, 0.5)]
        self.assertTrue(all(a < b for a, b in zip(u, u[1:])), u)

    def test_bound_check_and_break_even(self):
        fine, be, bc = m.fine_analysis(R, n_seq=300)
        self.assertEqual(len(fine['q']), 21)
        self.assertEqual(set(be), set(m.POLICIES))
        for p in ('M0', 'M2'):
            self.assertTrue(all(row['holds_within_4se'] for row in bc[p]))
        self.assertEqual(set(be['M1']['unsafe_per_100']), {'0.05', '0.1', '0.2'})


if __name__ == '__main__':
    unittest.main()
