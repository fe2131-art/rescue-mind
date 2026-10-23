"""Study JI: protocol generator (fresh hard-class worlds with twins and six views), the frozen thresholds and the registered claims on synthetic scores."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from scripts import make_protocol_ji as mji  # noqa: E402
from scripts import ji_analysis as jia  # noqa: E402


class Protocol(unittest.TestCase):
    def test_worlds_twins_and_views(self):
        p = mji.build()
        w = p['worlds']
        self.assertEqual((len(w), p['n_images']), (240, 1440))
        fire = [x for x in w if x['kind'] == 'hazard']
        twins = [x for x in w if x['kind'] == 'twin']
        self.assertEqual((len(fire), len(twins)), (120, 120))
        self.assertTrue(all(x['cls'] == 'tongues_small' and x['size_class'] == 'small' for x in fire))
        self.assertEqual({x['twin_of'] for x in twins}, {x['id'] for x in fire})
        self.assertTrue(all(set(x['views']) == {'F', 'L', 'R', 'L2', 'R2', 'N'} for x in w))
        self.assertTrue(all(x['id'].startswith('ji') for x in w) and {x['split'] for x in w} == {'test'})
        self.assertTrue(all('hazard_at' not in x['world_spec'] for x in twins))

    def test_generator_leaves_the_xd_module_untouched(self):
        import make_protocol_xd as mx
        before = (mx.SEED, dict(mx.CLASSES))
        mji.build()
        self.assertEqual((mx.SEED, dict(mx.CLASSES)), before)

    def test_thresholds_are_frozen_from_xd(self):
        t = json.loads((ROOT / 'experiments/ji_thresholds.json').read_text())
        self.assertEqual(set(t['viewsets']), {'v36_FLR', 'GL_F+L2', 'wide_F+L2+R2', 'all_six'})
        self.assertEqual(t['tau']['all_six']['qwen35'], 0.088)


class Claims(unittest.TestCase):
    def test_claims_on_synthetic_scores(self):
        thr = json.loads((ROOT / 'experiments/ji_thresholds.json').read_text())
        views = ('F', 'L', 'R', 'L2', 'R2', 'N')
        sc = {s: {} for s in ('qwen35',) + jia.JUDGES}
        kind = {}
        for i in range(10):
            f, c = f'jiF{i}', f'jiC{i}'
            kind[f], kind[c] = 'fire', 'clean'
            for v in views:
                # the fire is seen by the gate only from the near view N (and not at all in fires 0-1); the three standard views never see it
                sc['qwen35'][(f, v)] = 0.5 if (v == 'N' and i >= 2) else 0.001
                sc['qwen35'][(c, v)] = 0.001
                for j in jia.JUDGES:
                    sc[j][(f, v)], sc[j][(c, v)] = (0.99 if (j == 'internvl3' and i < 2 and v == 'N') else 0.0), 0.0
        out = jia.analyse(sc, kind, thr)
        g3, g6 = out['viewsets']['v36_FLR']['scorers']['qwen35'], out['viewsets']['all_six']['scorers']['qwen35']
        self.assertEqual((g3['miss'], g6['miss']), (10, 2))
        self.assertEqual(out['paired_six_vs_three'], {'three_only': 8, 'six_only': 0, 'mcnemar_one_sided_p': round(0.5 ** 8, 5)})
        self.assertTrue(out['claims']['JI2_six_views_fewer_misses_than_three'])
        self.assertEqual(out['viewsets']['all_six']['scorers']['qwen35+internvl3']['miss'], 0)        # the veto removes the last two
        self.assertEqual(out['viewsets']['all_six']['scorers']['qwen35+internvl3']['false_stops'], 0)
        self.assertTrue(out['claims']['JI3_gate_six_views_false_stops_at_most_5'])


if __name__ == '__main__':
    unittest.main()
