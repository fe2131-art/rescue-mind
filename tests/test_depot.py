import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind import depot  # noqa: E402
from rescuemind.robust_scenes import build_variant  # noqa: E402

SCENE = ROOT / 'worlds/scenarios/rescuemind_nominal.sdf'


class Placements(unittest.TestCase):
    def test_deterministic_and_outside_the_operating_area(self):
        a, b = depot.placements(7, True), depot.placements(7, True)
        self.assertEqual(a, b)
        self.assertNotEqual(depot.placements(7), depot.placements(8))
        for n, inst, x, y, yaw in a:
            if n in ('WallB_01', 'GroundB_01'):
                continue
            self.assertFalse(depot._inside(x, y), (inst, x, y))

    def test_default_world_unchanged(self):
        self.assertEqual(build_variant(SCENE), build_variant(SCENE, depot=None))


@unittest.skipUnless(depot.available(), 'depot assets not fetched (scripts/fetch_depot_assets.sh)')
class World(unittest.TestCase):
    def test_depot_world_parses_and_meshes_resolve(self):
        w = ET.fromstring(build_variant(SCENE, depot={'seed': 1, 'obstacle': True})).find('world')
        names = [m.get('name') for m in w.findall('model')]
        self.assertIn('depot_wallb_01_0', names)
        self.assertIn('depot_palletjack', names)
        for uri in w.iter('uri'):
            t = uri.text.strip()
            if t.startswith('file://') and 'aws-wh' in t:
                self.assertTrue(Path(t[len('file://'):]).is_file(), t)
        ground = next(m for m in w.findall('model') if m.get('name') == 'ground')
        self.assertEqual(ground.findall('link/visual'), [])          # warehouse floor replaces the grey plane
        self.assertTrue(ground.findall('link/collision'))

    def test_particle_smoke_only_with_fire_and_never_in_masks(self):
        kw = dict(depot={'seed': 1, 'particle_smoke': True}, hazard_at='water', hazard_geom=(0.6, 0.0, 0.5))
        self.assertIn(b'particle_emitter', build_variant(SCENE, **kw))
        self.assertNotIn(b'particle_emitter', build_variant(SCENE, **kw, hazard_mask=True))
        self.assertNotIn(b'particle_emitter', build_variant(SCENE, depot={'seed': 1, 'particle_smoke': True}))


if __name__ == '__main__':
    unittest.main()
