import unittest
from rescuemind.paired_significance import exact_mcnemar
class TestStats(unittest.TestCase):
    def test_paired_significance(self):
        p=exact_mcnemar([True]*9+[False], [False]*10)
        self.assertEqual(p['a_unsafe_b_safe'],9)
        self.assertAlmostEqual(p['mcnemar_exact_two_sided_p'],.00390625)
    def test_identical(self):
        self.assertEqual(exact_mcnemar([True,False],[True,False])['mcnemar_exact_two_sided_p'],1)
    def test_bad_lengths(self):
        with self.assertRaises(ValueError):exact_mcnemar([True],[])
if __name__=='__main__':unittest.main()
