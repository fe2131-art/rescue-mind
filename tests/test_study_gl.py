"""Study GL: protocol generator, the one-sided McNemar rule and the criteria on synthetic rows (no Gazebo, no model)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import make_protocol_gl as mgl  # noqa: E402
from scripts import gl_analysis as gla  # noqa: E402


class Protocol(unittest.TestCase):
    def test_arms_and_worlds(self):
        self.assertEqual(mgl.ARMS['v36'], [])
        self.assertEqual(mgl.ARMS['left'], ['--look-around', '0.8', '--look-around-sides', 'L', '--site-config', 'experiments/gl_site_cal.json'])
        names = [c['world'] for c in mgl.fire_candidates()]
        self.assertEqual((len(names), names[0], len(set(names))), (150, 'GL001', 150))
        self.assertTrue(all(not n.startswith(('GD', 'GV')) for n in names))
        self.assertEqual(len(mgl.plain_worlds()), 40)

    def test_selection_takes_the_first_120_eligible_in_id_order(self):
        masks = []
        for c in mgl.fire_candidates():
            w = c['world']
            for k, px in ((w, 700 if int(w[2:]) % 2 else 10), (w + 'L', 10), (w + 'R', 10)):
                masks.append({'key': k, 'fire_pixels': px})
        sel = mgl.select(masks)
        self.assertEqual(sel['selected'][:2], ['GL001', 'GL003'])
        self.assertEqual(len(sel['selected']), 75)             # 75 odd ids among 150 candidates
        self.assertEqual(sel['n_eligible_in_candidates'], 75)


class Analysis(unittest.TestCase):
    def test_one_sided_mcnemar(self):
        self.assertAlmostEqual(gla.mcnemar_one_sided(6, 0), 1 / 64)
        self.assertEqual(gla.mcnemar_one_sided(0, 0), 1.0)
        self.assertAlmostEqual(gla.mcnemar_one_sided(5, 1), 7 / 64)
        self.assertGreater(gla.mcnemar_one_sided(0, 4), 0.9)     # the arm that is better gives a large p

    def test_criteria(self):
        def rows(unsafe_v36, unsafe_left, n=12):
            tr, ledger, px = [], [], {}
            for i in range(n):
                w = f'GL{i + 1:03d}'
                px[w] = {'F': 700, 'L': 700, 'R': 700}
                for arm, unsafe in (('v36', unsafe_v36), ('left', unsafe_left)):
                    tid = f'{arm}{i}'
                    tr.append({'id': tid, 'world': w, 'config': arm, 'condition': 'fire_hidden', 'expected_action': 'DENY_HAZARD'})
                    ledger.append({'trial_id': tid, 'observed_action': 'ALLOW' if i in unsafe else 'DENY_HAZARD', 'mission_time_s': 100.0, 'state': 'x'})
            for i in range(4):
                for arm in ('v36', 'left'):
                    tid = f'p{arm}{i}'
                    tr.append({'id': tid, 'world': f'GLP{i}', 'config': arm, 'condition': 'plain', 'expected_action': 'ALLOW'})
                    ledger.append({'trial_id': tid, 'observed_action': 'ALLOW', 'mission_time_s': 90.0, 'state': 'x'})
            return {'trials': tr}, ledger, {'design_pixels': px, 'selected': [f'GL{i + 1:03d}' for i in range(n)]}
        p, led, sel = rows({0, 1, 2, 3, 4, 5}, set())
        out = gla.analyse(p, led, sel)
        self.assertTrue(out['criteria']['GL1_paired_one_sided_p_below_005_and_fewer'])       # 6 vs 0: p = 1/64
        self.assertTrue(out['criteria']['GL2_left_upper_at_most_10pct'] is False)           # 0/12: upper 22% > 10% with this small n
        self.assertTrue(out['criteria']['GL3_false_stops_at_most_2'])
        p, led, sel = rows({0, 1}, {0, 1})
        out = gla.analyse(p, led, sel)
        self.assertFalse(out['criteria']['GL1_paired_one_sided_p_below_005_and_fewer'])


if __name__ == '__main__':
    unittest.main()
