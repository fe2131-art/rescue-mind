"""I-21 polish (study XD): pallets with wrapped cartons, smoke-only hazard, alternative flame appearances, clutter ablation.
Pure SDF/geometry tests (no Gazebo): options off = identical output, footprint unchanged, masks consistent."""
import math
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind import depot  # noqa: E402
from rescuemind.robust_scenes import build_variant  # noqa: E402

SCENE = ROOT / 'worlds/scenarios/rescuemind_nominal.sdf'
K4 = {'stations': 4, 'surroundings': False}
FIRE = dict(hazard_at='W2', hazard_geom=(0.6, 0.0, 0.6))


def world(**kw):
    return ET.fromstring(build_variant(SCENE, **kw)).find('world')


def model(w, name):
    return next(m for m in w.findall('model') if m.get('name') == name)


def platforms(w):
    return [m for m in w.findall('model') if m.get('name', '').startswith('aid_station_')]


class OptionsOff(unittest.TestCase):
    def test_explicit_off_equals_absent(self):
        for extra in ({}, {'particle_smoke': True}):
            kw = dict(depot={**K4, **extra}, **FIRE)
            off = dict(depot={**K4, **extra, 'pallets': None, 'hazard_style': None, 'clutter': True}, **FIRE)
            self.assertEqual(build_variant(SCENE, **kw), build_variant(SCENE, **off))
            self.assertEqual(build_variant(SCENE, **kw, hazard_mask=True), build_variant(SCENE, **off, hazard_mask=True))
        off = dict(depot={'seed': 3, 'surroundings': False, 'hazard_style': 'tongues'}, hazard_at='water')
        self.assertEqual(build_variant(SCENE, depot={'seed': 3, 'surroundings': False}, hazard_at='water'),
                         build_variant(SCENE, **off))                      # 'tongues' is the default look
        self.assertEqual(build_variant(SCENE, depot={'surroundings': False}), build_variant(SCENE))   # the arena itself

    def test_unknown_values_are_rejected(self):
        with self.assertRaises(ValueError):
            build_variant(SCENE, depot={**K4, 'pallets': 'gold'})
        with self.assertRaises(ValueError):
            build_variant(SCENE, depot={**K4, 'hazard_style': 'lava'}, **FIRE)
        with self.assertRaises(ValueError):
            depot.depot_options({'hazard_style': 'lava'})
        with self.assertRaises(KeyError):
            depot.restyle_hazard(world(depot=K4), 'hazard_fire_nowhere', 'smoke_only')


class Pallets(unittest.TestCase):
    def setUp(self):
        self.plain = world(depot=K4)
        self.dressed = world(depot={**K4, 'pallets': 'wood_cartons', 'seed': 5})

    def test_collision_and_footprint_are_unchanged(self):
        a, b = platforms(self.plain), platforms(self.dressed)
        self.assertEqual([m.get('name') for m in a], [m.get('name') for m in b])
        self.assertEqual(len(a), 4)
        for m0, m1 in zip(a, b):
            self.assertEqual(ET.tostring(m0.find('link/collision')), ET.tostring(m1.find('link/collision')))
            self.assertEqual(m0.findtext('pose'), m1.findtext('pose'))
            self.assertEqual(m0.findtext('static'), m1.findtext('static'))
            self.assertEqual(len(m1.findall('link/collision')), 1)
            self.assertIsNone(m1.find("link/visual[@name='v']"))            # the grey box is gone ...
            self.assertGreater(len(m1.findall('link/visual')), 20)            # ... replaced by pallet + cartons
        # everything else of the world is identical
        rest = lambda w: [ET.tostring(m) for m in w.findall('model') if not m.get('name', '').startswith('aid_station_')]
        self.assertEqual(rest(self.plain), rest(self.dressed))

    def test_visuals_stay_inside_the_footprint_and_below_the_supply(self):
        for m in platforms(self.dressed):
            for v in m.findall('link/visual'):
                px, py, pz, _r, _p, yaw = [float(t) for t in v.findtext('pose').split()]
                sx, sy, sz = [float(t) for t in v.find('geometry/box/size').text.split()]
                hx = abs(math.cos(yaw)) * sx / 2 + abs(math.sin(yaw)) * sy / 2
                hy = abs(math.sin(yaw)) * sx / 2 + abs(math.cos(yaw)) * sy / 2
                self.assertLessEqual(abs(px) + hx, 0.45 + 1e-6, v.get('name'))
                self.assertLessEqual(abs(py) + hy, 0.45 + 1e-6, v.get('name'))
                self.assertGreaterEqual(pz - sz / 2, -1e-9, v.get('name'))
                name = v.get('name')
                if not name.startswith('top_'):                              # pallet + plinth end at the platform top
                    self.assertLessEqual(pz + sz / 2, depot.PLATFORM_TOP + 1e-6, name)
                else:                                                         # cartons beside the supply: low, off its centre
                    self.assertLessEqual(pz + sz / 2, depot.PLATFORM_TOP + 0.21, name)
                    self.assertGreater(max(abs(px), abs(py)), 0.2, name)

    def test_top_cartons_are_behind_and_do_not_touch_a_platform_distractor(self):
        names = {'W1': 'aid_station_water', 'M1': 'aid_station_medicine', 'W2': 'aid_station_W2', 'M2': 'aid_station_M2'}
        for st, pname in names.items():
            for side in (-1.0, 1.0):
                for kind in ('box', 'crate', 'cone'):
                    w = world(depot={**K4, 'pallets': 'wood_cartons', 'seed': 5}, distractor_at=st, distractor_layout='platform',
                              distractor_kind=kind, distractor_side=side)
                    cx0, cy0 = [float(t) for t in model(w, pname).findtext('pose').split()[:2]]
                    dm = next(m for m in w.findall('model') if m.get('name', '').startswith('distractor_'))
                    bx, by = [float(t) for t in dm.findtext('pose').split()[:2]]
                    for v in model(w, pname).findall('link/visual'):
                        if v.get('name', '').startswith('top_carton'):
                            x, y = [float(t) for t in v.findtext('pose').split()[:2]]
                            self.assertGreaterEqual(math.hypot(cx0 + x - bx, cy0 + y - by), 0.36, (st, side, kind))
        # 'behind' = away from the start: both cartons are on the far side of the platform centre
        for m in platforms(self.dressed):
            wx, wy = [float(t) for t in m.findtext('pose').split()[:2]]
            n = math.hypot(wx, wy)
            dots = []
            for v in m.findall('link/visual'):
                if v.get('name', '').startswith('top_carton'):
                    x, y = [float(t) for t in v.findtext('pose').split()[:2]]
                    dots.append(x * wx / n + y * wy / n)
            self.assertEqual(len(dots), 2)
            self.assertGreater(max(dots), 0.2)
            self.assertGreater(min(dots), -0.05)

    def test_deterministic_and_seed_dependent(self):
        a = build_variant(SCENE, depot={**K4, 'pallets': 'wood_cartons', 'seed': 5})
        self.assertEqual(a, build_variant(SCENE, depot={**K4, 'pallets': 'wood_cartons', 'seed': 5}))
        self.assertNotEqual(a, build_variant(SCENE, depot={**K4, 'pallets': 'wood_cartons', 'seed': 6}))

    def test_rotated_platform_puts_the_cartons_at_the_corners_nearest_the_wall(self):
        for yaw in (0.0, 0.7, -2.0):
            w = world(depot=K4)
            m = model(w, 'aid_station_M2')
            x, y = depot.K4_CENTERS['M2'][:2]
            m.find('pose').text = f'{x:g} {y:g} 0 0 0 {yaw:g}'
            self.assertIn('aid_station_M2', depot.dress_platforms(w, {'pallets': 'wood_cartons', 'seed': 1}))
            n = math.hypot(x, y)
            world_dot = lambda lx, ly: ((lx * math.cos(yaw) - ly * math.sin(yaw)) * x + (lx * math.sin(yaw) + ly * math.cos(yaw)) * y) / n
            corners = sorted((world_dot(sx * .3, sy * .3) for sx in (-1, 1) for sy in (-1, 1)), reverse=True)
            got = sorted((world_dot(*[float(t) for t in v.findtext('pose').split()[:2]])
                          for v in m.findall('link/visual') if v.get('name', '').startswith('top_carton')), reverse=True)
            self.assertEqual(len(got), 2)
            for a, b in zip(got, corners[:2]):
                self.assertAlmostEqual(a, b, places=3)

    def test_two_station_depot_platforms_too_and_masks_keep_them(self):
        w = world(depot={'surroundings': False, 'pallets': 'wood_cartons'}, hazard_at='water', hazard_mask=True)
        self.assertEqual(len(platforms(w)), 2)
        self.assertGreater(len(model(w, 'aid_station_water').findall('link/visual')), 20)


class SmokeOnly(unittest.TestCase):
    def hazard(self, mask, extra=None):
        return model(world(depot={**K4, 'hazard_style': 'smoke_only', **(extra or {})}, **FIRE, hazard_mask=mask), 'hazard_fire_W2')

    def test_no_flames_static_and_no_collision(self):
        m = self.hazard(False)
        names = [v.get('name') for v in m.findall('link/visual')]
        self.assertFalse([n for n in names if n.startswith('flame')])
        self.assertGreaterEqual(len([n for n in names if n.startswith('smoke')]), 5)
        self.assertEqual(m.findall('.//collision'), [])
        self.assertEqual(m.findtext('static'), 'true')
        default = model(world(depot=K4, **FIRE), 'hazard_fire_W2')
        self.assertEqual(m.findtext('pose'), default.findtext('pose'))       # same place as the default fire

    def test_mask_is_flat_magenta_and_opaque(self):
        m = self.hazard(True)
        for v in m.findall('link/visual'):
            if v.get('name') == 'charred_base':
                continue
            self.assertEqual(v.findtext('material/emissive'), '1 0 1 1')
            self.assertIsNone(v.find('transparency'))
        plain = self.hazard(False)
        self.assertEqual([v.get('name') for v in m.findall('link/visual')], [v.get('name') for v in plain.findall('link/visual')])

    def test_scale_and_particle_plume(self):
        small = model(world(depot={**K4, 'hazard_style': 'smoke_only'}, hazard_at='W2', hazard_geom=(.6, 0, .5)), 'hazard_fire_W2')
        big = self.hazard(False)
        top = lambda m: max(float(v.findtext('pose').split()[2]) for v in m.findall('link/visual'))
        self.assertLess(top(small), top(big))
        b = build_variant(SCENE, depot={**K4, 'hazard_style': 'smoke_only', 'particle_smoke': True}, **FIRE)
        self.assertIn(b'particle_emitter', b)
        self.assertNotIn(b'particle_emitter', build_variant(SCENE, depot={**K4, 'hazard_style': 'smoke_only', 'particle_smoke': True},
                                                            **FIRE, hazard_mask=True))


class MeshFlame(unittest.TestCase):
    def test_obj_is_valid_and_deterministic(self):
        p = depot.flame_mesh_path('t-seed')
        self.assertEqual(p, depot.flame_mesh_path('t-seed'))
        self.assertNotEqual(p, depot.flame_mesh_path('other-seed'))
        v = vn = f = 0
        idx = []
        for line in p.read_text().splitlines():
            if line.startswith('v '):
                v += 1
            elif line.startswith('vn '):
                vn += 1
            elif line.startswith('f '):
                f += 1
                idx += [int(t.split('//')[0]) for t in line.split()[1:]]
        self.assertEqual(v, vn)
        self.assertGreater(f, 300)
        self.assertTrue(1 <= min(idx) and max(idx) <= v)

    def test_model_uses_the_mesh_not_ellipsoids_and_mask_is_flat(self):
        w = world(depot={**K4, 'hazard_style': 'mesh_flame', 'seed': 'abc'}, **FIRE)
        m = model(w, 'hazard_fire_W2')
        flames = [v for v in m.findall('link/visual') if v.get('name', '').startswith('flame')]
        self.assertEqual(len(flames), 3)
        for v in flames:
            self.assertIsNotNone(v.find('geometry/mesh'))
            self.assertIsNone(v.find('geometry/ellipsoid'))
            self.assertTrue(Path(v.findtext('geometry/mesh/uri')[len('file://'):]).is_file())
        mk = model(world(depot={**K4, 'hazard_style': 'mesh_flame', 'seed': 'abc'}, **FIRE, hazard_mask=True), 'hazard_fire_W2')
        for v in mk.findall('link/visual'):
            if v.get('name') != 'charred_base':
                self.assertEqual(v.findtext('material/emissive'), '1 0 1 1')
        self.assertEqual(m.findtext('pose'), model(world(depot=K4, **FIRE), 'hazard_fire_W2').findtext('pose'))


class Billboard(unittest.TestCase):
    def test_sprite_and_mask_share_one_silhouette(self):
        import numpy as np
        from PIL import Image
        c, k = depot.flame_sprite_path('b-seed'), depot.flame_sprite_path('b-seed', mask=True)
        a, b = np.asarray(Image.open(c)), np.asarray(Image.open(k))
        self.assertEqual(a.shape, b.shape)
        self.assertEqual(a.shape[2], 4)
        self.assertTrue(set(np.unique(a[..., 3])) <= {0, 255})
        self.assertTrue((a[..., 3] == b[..., 3]).all())
        self.assertGreater(int((a[..., 3] > 0).sum()), 5000)
        on = b[..., 3] > 0
        self.assertTrue((b[on][:, 0] == 255).all() and (b[on][:, 1] == 0).all() and (b[on][:, 2] == 255).all())

    def test_model_planes_and_mask(self):
        m = model(world(depot={**K4, 'hazard_style': 'billboard', 'seed': 'b-seed'}, **FIRE), 'hazard_fire_W2')
        planes = [v for v in m.findall('link/visual') if v.find('geometry/plane') is not None]
        self.assertEqual(len(planes), 3)
        self.assertEqual({v.findtext('material/double_sided') for v in planes}, {'true'})
        self.assertEqual(len({v.findtext('pose').split()[5] for v in planes}), 3)          # three different yaws
        tex = planes[0].findtext('material/pbr/metal/albedo_map')
        self.assertTrue(Path(tex).is_file())
        mk = model(world(depot={**K4, 'hazard_style': 'billboard', 'seed': 'b-seed'}, **FIRE, hazard_mask=True), 'hazard_fire_W2')
        mtex = [v.findtext('material/pbr/metal/albedo_map') for v in mk.findall('link/visual') if v.find('geometry/plane') is not None]
        self.assertTrue(all(t.endswith('_mask.png') for t in mtex))

    def test_third_party_texture_is_used_as_is(self):
        import tempfile
        from PIL import Image
        with tempfile.TemporaryDirectory() as td:
            png = Path(td) / 'fire.png'
            Image.new('RGBA', (32, 48), (255, 120, 0, 255)).save(png)
            self.assertEqual(depot.flame_sprite_path('s', texture=png), png)
            mask = depot.flame_sprite_path('s', mask=True, texture=png)         # the label sprite follows the texture's alpha
            import numpy as np
            self.assertEqual(np.asarray(Image.open(mask)).shape[:2], (48, 32))
            m = depot.billboard_flame_model('h', 0, 0, 1.0, False, 's', png)
            self.assertEqual(m.find('link/visual/material/pbr/metal/albedo_map').text, str(png))


class ClutterAblation(unittest.TestCase):
    def test_clutter_off_drops_only_the_movable_clutter(self):
        for k in (2, 4):
            full = depot.placements(7, True, k)
            bare = depot.placements(7, True, k, clutter=False)
            self.assertEqual([p for p in full if '_c' not in p[1].replace('_palletjack', '')],
                             [p for p in bare if '_c' not in p[1].replace('_palletjack', '')])
            self.assertEqual(len(full) - len(bare), 4)
            self.assertFalse([p for p in bare if p[1].rsplit('_', 1)[-1].startswith('c')])
            jack = lambda ps: next(p for p in ps if p[0] == 'PalletJackB_01')
            self.assertEqual(jack(full), jack(bare))                              # the same random stream
        self.assertEqual(depot.placements(7, True), depot.placements(7, True, 2, clutter=True))


if __name__ == '__main__':
    unittest.main()
