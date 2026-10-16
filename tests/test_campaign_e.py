"""Campaign E: protocol generator, randomised world construction and runner wiring."""
import json
import math
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import scripts.make_protocol_e as pe
import scripts.run_campaign as rc
from rescuemind.robust_scenes import STATIONS, build_variant

ROOT = Path(__file__).resolve().parents[1]


def _pose(world, prefix):
    m = next(m for m in world.findall('model') if m.get('name', '').startswith(prefix))
    return [float(v) for v in m.findtext('pose').split()]


class Protocol(unittest.TestCase):
    def test_deterministic_and_balanced(self):
        a, b = pe.build(), pe.build()
        self.assertEqual(a, b)
        from collections import Counter
        c = Counter(t['expected_action'] for t in a['trials'])
        self.assertEqual(c, {'ALLOW': 20, 'DELIVER_AFTER_SEARCH': 16, 'DENY': 12, 'DENY_HAZARD': 8,
                             'DENY_HAZARD_AFTER_SEARCH': 4})
        self.assertNotEqual(pe.build('E-pilot')['trials'][0]['world_spec'], a['trials'][0]['world_spec'])

    def test_fire_placement_matches_expectation(self):
        for t in pe.build()['trials']:
            spec = t['world_spec']
            if t['expected_action'] == 'DENY_HAZARD':
                self.assertEqual(spec['hazard_at'], t['expected'])
            if t['expected_action'] == 'DENY_HAZARD_AFTER_SEARCH':
                self.assertNotEqual(spec['hazard_at'], t['expected'])
                self.assertEqual(t['scene'], 'swapped')

    def test_distractor_never_overlaps_the_supply(self):
        for t in pe.build()['trials']:
            spec = t['world_spec']
            if not spec.get('distractor_at') or t['scene'] == 'empty':
                continue
            xml = build_variant(ROOT / f"worlds/scenarios/rescuemind_{t['scene']}.sdf", **spec)
            world = ET.fromstring(xml).find('world')
            d = _pose(world, 'distractor_')
            sx, sy = STATIONS[t['expected']]
            props = [_pose(world, n) for n in ('sealed_water_bottles', 'first_aid_case')]
            near = min(props, key=lambda p: math.hypot(p[0] - sx, p[1] - sy))
            self.assertGreater(math.hypot(d[0] - near[0], d[1] - near[1]), 0.30, t['id'])
            # on the platform (0.9 m square, centre at the station)
            self.assertLess(max(abs(d[0] - sx), abs(d[1] - sy)), 0.45, t['id'])

    def test_world_spec_keys_are_accepted_by_orchestrator(self):
        import scripts.v32_orchestrate as orch
        for t in pe.build()['trials']:
            self.assertFalse(set(t['world_spec']) - orch.WORLD_SPEC_KEYS)


class Runner(unittest.TestCase):
    def _summ(self, tmp, mission, result):
        d = Path(tmp) / 'abcdef0123456789'
        d.mkdir()
        (d / 'mission.json').write_text(json.dumps(mission))
        (d / 'stack_result.json').write_text(json.dumps(result))
        return d

    def test_hazard_after_search_is_its_own_outcome(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            d = self._summ(tmp, {'checkpoint': {'decision': {'reason': 'visible_hazard_at_checkpoint', 'allow': False}},
                                 'recovery': {'first_checkpoint': {'decision': {}}}},
                           {'state': 'COMPLETED_EXPECTED_DENIAL'})
            row = rc.summarize({'id': 'E001', 'order': 1, 'scene': 'swapped', 'expected': 'water',
                                'expected_action': 'DENY_HAZARD_AFTER_SEARCH'}, d, 0, 1.0)
        self.assertEqual(row['observed_action'], 'DENY_HAZARD_AFTER_SEARCH')
        self.assertTrue(row['correct'])
        self.assertFalse(row['delivered'])


if __name__ == '__main__':
    unittest.main()
