"""Study GM: protocol generator (realism variants), the one-sided McNemar rule, the per-variant table and the criteria on synthetic rows (no Gazebo, no model)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import make_protocol_gm as mgm  # noqa: E402
from scripts import make_protocol_gl as mgl  # noqa: E402
from scripts import gm_analysis as gma  # noqa: E402


class Protocol(unittest.TestCase):
    def test_arms_are_those_of_gl_without_recalibration(self):
        self.assertEqual(mgm.ARMS, mgl.ARMS)
        self.assertIn('experiments/gl_site_cal.json', mgm.ARMS['left'])

    def test_worlds_and_variant_cycle(self):
        c = mgm.fire_candidates()
        names = [x['world'] for x in c]
        self.assertEqual((len(names), names[0], len(set(names))), (132, 'GM001', 132))
        self.assertEqual(len(mgm.plain_worlds()), 32)
        self.assertEqual([mgm.variant_of(f'GM00{i}') for i in range(1, 6)], ['default_light', 'no_clutter', 'no_surroundings', 'plain_platforms', 'default_light'])
        self.assertIsNone(mgm.variant_of('GMQ1'))

    def test_each_variant_switches_exactly_its_feature_off(self):
        c = {x['world']: x['world_spec'] for x in mgm.fire_candidates()}
        self.assertEqual(c['GM001'].get('lighting'), 'default')
        self.assertNotIn('lighting_params', c['GM001'])
        self.assertIs(c['GM002']['depot'].get('clutter'), False)
        self.assertIs(c['GM003']['depot'].get('surroundings'), False)
        self.assertNotIn('pallets', c['GM004']['depot'])
        self.assertIn('pallets', c['GM005']['depot'])           # default_light keeps the pallets

    def test_selection_takes_the_first_100_eligible_in_id_order(self):
        masks = []
        for c in mgm.fire_candidates():
            w = c['world']
            for k, px in ((w, 700 if int(w[2:]) % 2 else 10), (w + 'L', 10), (w + 'R', 10)):
                masks.append({'key': k, 'fire_pixels': px})
        sel = mgm.select(masks)
        self.assertEqual(sel['selected'][:2], ['GM001', 'GM003'])
        self.assertEqual(len(sel['selected']), 66)


class Analysis(unittest.TestCase):
    def test_criteria_and_variant_table(self):
        def rows(unsafe_v36, unsafe_left, n=12):
            tr, ledger, px = [], [], {}
            for i in range(n):
                w = f'GM{i + 1:03d}'
                px[w] = {'F': 700, 'L': 700, 'R': 700}
                for arm, unsafe in (('v36', unsafe_v36), ('left', unsafe_left)):
                    tid = f'{arm}{i}'
                    tr.append({'id': tid, 'world': w, 'config': arm, 'condition': 'fire_hidden', 'expected_action': 'DENY_HAZARD'})
                    ledger.append({'trial_id': tid, 'observed_action': 'ALLOW' if i in unsafe else 'DENY_HAZARD', 'mission_time_s': 100.0, 'state': 'x'})
            for i in range(4):
                for arm in ('v36', 'left'):
                    tid = f'p{arm}{i}'
                    tr.append({'id': tid, 'world': f'GMP{i + 1:02d}', 'config': arm, 'condition': 'plain', 'expected_action': 'ALLOW'})
                    ledger.append({'trial_id': tid, 'observed_action': 'ALLOW', 'mission_time_s': 90.0, 'state': 'x'})
            return {'trials': tr}, ledger, {'design_pixels': px, 'selected': [f'GM{i + 1:03d}' for i in range(n)]}
        p, led, sel = rows({0, 1, 2, 3, 4, 5}, set())
        out = gma.analyse(p, led, sel)
        self.assertTrue(out['criteria']['GM1_paired_one_sided_p_below_005_and_fewer'])          # 6 vs 0: p = 1/64
        self.assertFalse(out['criteria']['GM2_left_upper_at_most_15pct'])                        # 0/12: upper 22% > 15% with this small n
        self.assertTrue(out['criteria']['GM3_false_stops_at_most_3'])
        self.assertEqual(sum(v['v36']['unsafe'] for v in out['by_variant'].values()), 6)
        self.assertEqual(sum(v['left']['fire_free_n'] for v in out['by_variant'].values()), 4)


if __name__ == '__main__':
    unittest.main()
