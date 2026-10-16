"""Paper test set T1: generator determinism, label rules and world construction."""
import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import scripts.build_testset_t1 as t1
from rescuemind.robust_scenes import build_variant, hazard_visibility

ROOT = Path(__file__).resolve().parents[1]


class T1Spec(unittest.TestCase):
    def test_spec_is_deterministic_and_matches_registered_file(self):
        self.assertEqual(t1.make_spec(), t1.make_spec())
        reg = ROOT / 'experiments/vlm_testset_t1/spec.json'
        self.assertEqual(json.loads(reg.read_text()), json.loads(json.dumps(t1.make_spec())))

    def test_counts(self):
        spec = t1.make_spec()
        self.assertEqual(len(spec), 60)
        self.assertEqual(sum(len(v) for w in spec for v in w['views'].values()), 600)

    def test_label_rules(self):
        w = {'scene': 'nominal', 'hazard_at': None}
        self.assertEqual(t1.labels_for(w, 'water', [1.2, 1.2, .785, 1.1])['expected'], 'allow')
        w = {'scene': 'swapped'}
        self.assertEqual(t1.labels_for(w, 'water', [1.2, 1.2, .785, 1.1])['expected'], 'deny')
        w = {'scene': 'nominal', 'hazard_at': 'water', 'hazard_geom': [.75, .5]}
        self.assertEqual(t1.labels_for(w, 'water', [1.2, 1.2, .785, 1.1])['expected'], 'deny')
        self.assertEqual(t1.labels_for(w, 'water', [1.2, 1.2, 2.0, 1.1])['expected'], 'allow')
        self.assertEqual(t1.labels_for(w, 'water', [1.2, 1.2, 1.6, 1.1])['expected'], 'ambiguous')

    def test_fire_at_other_station_is_hidden(self):
        self.assertEqual(hazard_visibility('water', 'medicine', (1.2, 1.2), .785), 'hidden')

    def test_world_contains_randomised_elements(self):
        w = next(w for w in t1.make_spec() if w.get('hazard_at') and w['scene'] == 'nominal')
        xml = build_variant(ROOT / 'worlds/scenarios/rescuemind_nominal.sdf', lighting_params=w['lighting_params'],
                            prop_offsets=w['prop_offsets'], hazard_at=w['hazard_at'], hazard_geom=tuple(w['hazard_geom']))
        world = ET.fromstring(xml).find('world')
        names = {m.get('name') for m in world.findall('model')}
        self.assertIn(f"hazard_fire_{w['hazard_at']}", names)
        self.assertEqual(world.find("light[@name='sun']/intensity").text, w['lighting_params']['intensity'])
        for kind in ('cone', 'crate', 'box'):
            xml = build_variant(ROOT / 'worlds/scenarios/rescuemind_empty.sdf', distractor_at='water', distractor_kind=kind)
            self.assertTrue(any(m.get('name', '').startswith(f'distractor_{kind}') for m in ET.fromstring(xml).find('world').findall('model')))


if __name__ == '__main__':
    unittest.main()
