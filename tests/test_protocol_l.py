"""Study L: protocol generator (counts, determinism, feasibility of every layout, orchestrator acceptance)."""
import json
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import scripts.make_protocol_l as pl
from rescuemind import layout as L
from rescuemind.robust_scenes import build_variant


class ProtocolL(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proto = pl.build()

    def test_counts(self):
        p = self.proto
        self.assertEqual(p['planned_n'], 24)
        self.assertEqual(len(p['trials']), 24)
        self.assertEqual(Counter(t['scene'] for t in p['trials']), {'nominal': 14, 'swapped': 6, 'empty': 4})
        self.assertEqual(Counter(t['expected_action'] for t in p['trials']),
                         {'ALLOW': 8, 'DELIVER_AFTER_SEARCH': 6, 'DENY': 4, 'DENY_HAZARD': 6})
        self.assertEqual(Counter(t['expected'] for t in p['trials']), {'water': 12, 'medicine': 12})
        self.assertEqual(p['common_stack_args'], [])
        self.assertEqual(len({t['id'] for t in p['trials']}), 24)
        self.assertEqual([t['order'] for t in p['trials']], list(range(1, 25)))

    def test_deterministic(self):
        self.assertEqual(pl.build(), pl.build())
        self.assertNotEqual(pl.build('L-other')['trials'][0]['world_spec'], self.proto['trials'][0]['world_spec'])

    def test_layouts_unique_and_feasible(self):
        seen = set()
        for t in self.proto['trials']:
            spec = t['world_spec']
            lay = L.Layout.from_dict(spec['layout'])
            seen.add(json.dumps(spec['layout'], sort_keys=True))
            kw = {}
            if 'hazard_at' in spec:
                kw = {'hazard_at': spec['hazard_at'], 'hazard_geom': tuple(spec['hazard_geom'])}
            self.assertEqual(L.check_layout(lay, **kw), [], t['id'])
            # the dict round-trips exactly
            self.assertEqual(L.Layout.from_dict(spec['layout']).to_dict(), spec['layout'])
        self.assertEqual(len(seen), 24)

    def test_fire_trials(self):
        fire = [t for t in self.proto['trials'] if t['condition'] == 'fire']
        self.assertEqual(len(fire), 6)
        for t in fire:
            s = t['world_spec']
            self.assertEqual(t['scene'], 'nominal')
            self.assertEqual(s['hazard_at'], t['expected'])
            self.assertTrue(.75 <= s['hazard_geom'][0] <= 1.0)
            self.assertTrue(.25 <= abs(s['hazard_geom'][1]) <= .6)
        for t in self.proto['trials']:
            if t['condition'] != 'fire':
                self.assertNotIn('hazard_at', t['world_spec'])
            self.assertEqual(t['world'], t['id'])

    def test_empty_has_no_prop_offsets(self):
        for t in self.proto['trials']:
            self.assertEqual('prop_offsets' in t['world_spec'], t['scene'] != 'empty')

    def test_world_spec_accepted_and_buildable(self):
        import scripts.v32_orchestrate as orch
        for t in self.proto['trials']:
            spec = dict(t['world_spec'])
            self.assertFalse(set(spec) - orch.WORLD_SPEC_KEYS)
            spec['layout'] = L.Layout.from_dict(spec['layout'])
            if 'hazard_geom' in spec:
                spec['hazard_geom'] = tuple(spec['hazard_geom'])
            self.assertTrue(build_variant(ROOT / f"worlds/scenarios/rescuemind_{t['scene']}.sdf", **spec))

    def test_smoke_disjoint_from_registered(self):
        s = pl.build_smoke()
        self.assertEqual(s['planned_n'], 3)
        self.assertEqual({t['scene'] for t in s['trials']}, {'nominal', 'swapped', 'empty'})
        reg = {json.dumps(t['world_spec']['layout'], sort_keys=True) for t in self.proto['trials']}
        for t in s['trials']:
            self.assertNotIn(json.dumps(t['world_spec']['layout'], sort_keys=True), reg)
            self.assertEqual(L.check_layout(L.Layout.from_dict(t['world_spec']['layout'])), [])

    def test_committed_protocol_matches_generator(self):
        f = ROOT / 'experiments/campaign_l_protocol.json'
        if f.is_file():
            self.assertEqual(json.loads(f.read_text()), json.loads(json.dumps(self.proto, ensure_ascii=False)))
        g = ROOT / 'experiments/campaign_l_smoke_protocol.json'
        if g.is_file():
            self.assertEqual(json.loads(g.read_text()), json.loads(json.dumps(pl.build_smoke(), ensure_ascii=False)))

    def test_analysis_helpers(self):
        import scripts.l_analysis as la
        t = next(t for t in self.proto['trials'] if t['scene'] == 'swapped')
        self.assertGreater(la.path_length(t, False), 0)
        nom = next(t for t in self.proto['trials'] if t['condition'] == 'plain' and t['scene'] == 'nominal')
        self.assertLess(la.path_length(nom, False), la.path_length(dict(nom, scene='swapped'), False))
        self.assertAlmostEqual(la.ols([1, 2, 3, 4], [3, 5, 7, 9])['slope_s_per_m'], 2.0)


if __name__ == '__main__':
    unittest.main()
