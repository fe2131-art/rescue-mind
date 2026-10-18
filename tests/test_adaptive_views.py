import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rescuemind import adaptive_views as av  # noqa: E402


def call(p):
    return {'scores': {'hazard_prob': p}}


class AdaptiveViews(unittest.TestCase):
    def test_suspicion_is_the_largest_hazard_score_over_front_and_sides(self):
        cp = {'model_calls': {'first': call(.001), 'second': call(.002)}}
        peeks = [{'model_calls': {'first': call(.004), 'second': call(.009)}}, {'model_calls': {'first': call(0), 'second': call(0)}}]
        self.assertEqual(av.suspicion(cp, peeks), 0.009)
        self.assertTrue(av.required(cp, peeks, 0.005))
        self.assertFalse(av.required(cp, peeks[1:], 0.005))

    def test_missing_scores_count_as_suspicious(self):
        self.assertEqual(av.suspicion({'model_calls': {'first': {}, 'second': None}}, []), 1.0)     # I-19 fix: missing = suspicious (fail-closed)
        self.assertEqual(av.suspicion({'model_calls': {'first': {'scores': {'hazard_prob': 'x'}}}}, []), 1.0)

    def test_extra_points_geometry(self):
        pts = dict(av.extra_points((0.0, 0.0), (0.0, 2.0), 0.8, 0.3))
        self.assertEqual(pts['N'], (0.0, 0.3))                  # 0.3 m closer, on the view line
        self.assertAlmostEqual(abs(pts['L2'][0]), 0.8)          # 0.8 m to either side, perpendicular
        self.assertAlmostEqual(pts['L2'][1], 0.0)
        self.assertEqual(pts['L2'][0], -pts['R2'][0])


if __name__ == '__main__':
    unittest.main()
