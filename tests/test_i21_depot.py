"""I-21 phase 2: the four-station depot (rescuemind.depot K4_*), its per-run configuration and the world builder."""
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from rescuemind import depot  # noqa: E402
from rescuemind.camera_aim import station_centers  # noqa: E402
from rescuemind.robust_scenes import build_variant, truth_for_depot  # noqa: E402
from rescuemind.stations import StationSet, check_centers  # noqa: E402

SCENE = ROOT / 'worlds/scenarios/rescuemind_nominal.sdf'
SWAPPED = ROOT / 'worlds/scenarios/rescuemind_swapped.sdf'
EMPTY = ROOT / 'worlds/scenarios/rescuemind_empty.sdf'


def world(src=SCENE, **kw):
    return ET.fromstring(build_variant(src, **kw)).find('world')


def pose(w, name):
    m = next(m for m in w.findall('model') if m.get('name') == name)
    return [float(t) for t in m.findtext('pose').split()]


class Geometry(unittest.TestCase):
    def test_layout_is_feasible_in_every_generated_world(self):
        self.assertEqual(depot.check_k4_layout(seeds=range(10)), [])

    def test_the_check_catches_bad_layouts(self):
        def with_center(i, xy):
            lay = depot.k4_layout(); lay['centers'][i] = (*xy, 0.0)
            return lay
        near = with_center('W2', (-2.0, 0.6))                                   # too close to M1 and to the start's other bays
        self.assertTrue(depot.check_k4_layout(near, seeds=range(1)))
        outside = with_center('M2', (0.0, -5.0))
        self.assertTrue(any('outside' in b or 'radius' in b for b in depot.check_k4_layout(outside, seeds=range(1))))
        lay = depot.k4_layout(); lay['waypoints']['W2'] = (1.0, 0.6)           # a leg would pass over / touch other waypoints
        self.assertTrue(depot.check_k4_layout(lay, seeds=range(1)))

    def test_furniture_near_a_leg_is_dropped_only_in_the_four_bay_depot(self):
        k2 = {inst for _, inst, *_ in depot.placements(1, False, 2)}
        k4 = {inst for _, inst, *_ in depot.placements(1, False, 4)}
        self.assertTrue(k4 < k2 | {i for i in k4 if '_c' in i})                    # clutter slots differ, furniture only shrinks
        racks = lambda k: [(x, y) for n, _, x, y, _ in depot.placements(1, False, k) if n == 'ShelfD_01']
        for k in (2, 4):                                                          # no rack beside shelter B in either depot
            self.assertFalse([xy for xy in racks(k) if -3.6 <= xy[1] <= 0.0], k)
        for n, inst, x, y, yaw in depot.placements(1, True, 4):
            if n not in ('WallB_01', 'GroundB_01'):
                self.assertFalse(depot._inside(x, y, depot.OPERATING_AREA_K4) and '_c' in inst, inst)

    def test_the_two_station_depot_is_unchanged(self):
        self.assertEqual(depot.placements(7, True), depot.placements(7, True, 2))
        self.assertEqual(depot.placements(7, True)[:3], depot.placements(7, True, 2)[:3])
        self.assertEqual(len(depot.placements(3)), len(depot.placements(3, False, 2)))
        self.assertEqual(depot.operating_area(2), depot.OPERATING_AREA)
        self.assertEqual(build_variant(SCENE), build_variant(SCENE, depot=None))

    def test_four_bays_two_water_two_medicine(self):
        ss = depot.k4_station_set()
        self.assertEqual(ss.ids, depot.K4_IDS)
        self.assertEqual(sorted(ss.supply(i) for i in ss.ids), ['medicine', 'medicine', 'water', 'water'])
        self.assertEqual(ss.order('water'), ['W1', 'W2', 'M1', 'M2'])
        self.assertEqual(depot.K4_CENTERS['W1'][:2], (2.0, 2.0))          # the arena's two bays keep their poses
        self.assertEqual(depot.K4_CENTERS['M1'][:2], (-2.0, 2.0))
        self.assertEqual(depot.K4_WAYPOINTS['W1'], (1.18, 1.13))


class Configs(unittest.TestCase):
    def test_per_run_files_round_trip_through_the_mission_readers(self):
        spec = importlib.util.spec_from_file_location('rm_i21d', ROOT / 'ros/gazebo_waypoint_mission.py')
        mission = importlib.util.module_from_spec(spec); spec.loader.exec_module(mission)
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as td:
            wp, ct = depot.write_k4_configs(Path(td))
            cfg = json.loads(wp.read_text())
            ss = StationSet.from_config(cfg)
            self.assertEqual(ss, depot.k4_station_set())
            self.assertNotIn('water', cfg); self.assertNotIn('medicine', cfg)
            self.assertEqual(cfg['limits'], json.loads((ROOT / 'configs/gazebo_waypoints.json').read_text())['limits'])
            centers = mission.load_centers(SimpleNamespace(centers=str(ct)))
            check_centers(centers, ss)
            self.assertEqual(centers['W2'], depot.K4_CENTERS['W2'][:2])
            for item in ('water', 'medicine'):
                for st in ss.order(item):                                     # every station of the order is routable
                    r = mission.route_from_config(wp, item, station=st)
                    self.assertEqual((r[0][1], r[0][2]), (st, list(depot.K4_WAYPOINTS[st])))
                    self.assertEqual(r[1][1:], ('B', list(depot.K4_WAYPOINTS['B'])))
            with self.assertRaises(ValueError):                                # the locked default centres are the arena's two
                station_centers(json.loads(ct.read_text()))
            # the orchestrator audits against the run folder's own files
            import v32_orchestrate as orch
            self.assertEqual(orch.waypoint_config_path(Path(td)), wp)

    def test_orchestrator_plan_passes_the_depot_files(self):
        import v32_orchestrate as orch
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = orch.main(['--plan', '--scenario', 'live', '--scene', 'nominal', '--world-spec',
                            json.dumps({'depot': {'seed': 1, 'stations': 4, 'surroundings': False}, 'hazard_at': 'W2'})])
        self.assertEqual(rc, 0)
        argv = ' '.join(json.loads(out.getvalue())['mission'])
        self.assertIn('--config', argv); self.assertIn('--centers', argv)


class Worlds(unittest.TestCase):
    def test_four_platforms_with_props_per_the_inventory(self):
        w = world(depot={'stations': 4, 'surroundings': False})
        names = [m.get('name') for m in w.findall('model')]
        for i, (x, y, _) in depot.K4_CENTERS.items():
            plat = {'W1': 'aid_station_water', 'M1': 'aid_station_medicine'}.get(i, f'aid_station_{i}')
            self.assertEqual(pose(w, plat)[:2], [x, y])
        water = [n for n in names if n.startswith('sealed_water_bottles')]
        med = [n for n in names if n.startswith('first_aid_case')]
        self.assertEqual((len(water), len(med)), (2, 2))
        self.assertEqual(sorted(pose(w, n)[:2] for n in water), sorted([[2.0, 2.0], list(depot.K4_CENTERS['W2'][:2])]))
        self.assertEqual(sorted(pose(w, n)[:2] for n in med), sorted([[-2.0, 2.0], list(depot.K4_CENTERS['M2'][:2])]))
        self.assertEqual(len(names), len(set(names)))

    def test_nominal_two_station_scene_is_untouched_by_other_depot_settings(self):
        a = build_variant(SCENE, depot={'seed': 2, 'surroundings': False})
        self.assertEqual(a, build_variant(SCENE))                  # depot without stations=4: platforms as before

    def test_scene_variants_swap_and_empty_pallets(self):
        sw = depot.supply_map(ET.parse(SWAPPED).getroot().find('world'))
        self.assertEqual(sw, {'W1': 'medicine', 'M1': 'water', 'W2': 'water', 'M2': 'medicine'})
        em = depot.supply_map(ET.parse(EMPTY).getroot().find('world'))
        self.assertEqual((em['W1'], em['M1']), (None, None))
        sup = depot.supply_map(ET.parse(SCENE).getroot().find('world'), {'W2': None, 'M2': 'water'})
        self.assertEqual(sup, {'W1': 'water', 'M1': 'medicine', 'W2': None, 'M2': 'water'})
        w = world(depot={'stations': 4, 'surroundings': False, 'supply_at': {'W2': None, 'M2': 'water'}})
        names = [m.get('name') for m in w.findall('model')]
        self.assertEqual(sorted(n for n in names if n.startswith('sealed_water')), ['sealed_water_bottles', 'sealed_water_bottles_M2'])
        self.assertEqual([n for n in names if n.startswith('first_aid')], ['first_aid_case'])
        with self.assertRaises(ValueError):
            depot.supply_map(ET.parse(SCENE).getroot().find('world'), {'W9': 'water'})
        with self.assertRaises(ValueError):
            depot.supply_map(ET.parse(SCENE).getroot().find('world'), {'W1': 'toy'})

    def test_hazard_and_distractor_follow_the_pallet_ids(self):
        w = world(depot={'stations': 4, 'surroundings': False, 'supply_at': {'W2': None}}, hazard_at='W2', distractor_at='M2',
                  distractor_layout='platform')
        fx, fy = pose(w, 'hazard_fire_W2')[:2]
        from rescuemind.robust_scenes import hazard_xy
        ex, ey = hazard_xy('W2', stations={'W2': depot.K4_CENTERS['W2'][:2]})
        self.assertAlmostEqual(fx, ex, places=4); self.assertAlmostEqual(fy, ey, places=4)
        wx, wy = depot.K4_CENTERS['W2'][:2]
        self.assertLess(((fx - wx) ** 2 + (fy - wy) ** 2) ** .5, 1.2)               # next to W2 ...
        self.assertGreater(((fx - 2) ** 2 + (fy - 2) ** 2) ** .5, 3)                # ... not at W1
        self.assertIn('distractor_box_M2', [m.get('name') for m in w.findall('model')])
        with self.assertRaises(KeyError):
            build_variant(SCENE, depot={'stations': 4, 'surroundings': False}, hazard_at='water')

    def test_truth_labels(self):
        sup = {'W1': 'water', 'M1': 'medicine', 'W2': None, 'M2': 'water'}
        self.assertEqual(truth_for_depot(sup, 'W2', hazard_at='W2'), {'truth_supply': 'other', 'truth_hazard': True})
        self.assertEqual(truth_for_depot(sup, 'M2'), {'truth_supply': 'water', 'truth_hazard': False})

    def test_bad_depot_settings(self):
        for bad in ({'stations': 3, 'surroundings': False},):
            with self.assertRaises(ValueError):
                build_variant(SCENE, depot=bad)
        from rescuemind.layout import default_layout
        with self.assertRaises(ValueError):
            build_variant(SCENE, depot={'stations': 4, 'surroundings': False}, layout=default_layout())


@unittest.skipUnless(depot.available(), 'depot assets not fetched (scripts/fetch_depot_assets.sh)')
class WithSurroundings(unittest.TestCase):
    def test_full_four_bay_depot_world_parses_and_meshes_resolve(self):
        w = world(depot={'seed': 4, 'stations': 4, 'obstacle': True, 'particle_smoke': True}, hazard_at='M2')
        names = [m.get('name') for m in w.findall('model')]
        self.assertIn('depot_wallb_01_0', names); self.assertIn('depot_palletjack', names)
        self.assertEqual(len(names), len(set(names)))
        for uri in w.iter('uri'):
            t = uri.text.strip()
            if t.startswith('file://') and 'aws-wh' in t:
                self.assertTrue(Path(t[len('file://'):]).is_file(), t)
        self.assertIn(b'particle_emitter', build_variant(SCENE, depot={'seed': 4, 'stations': 4, 'particle_smoke': True}, hazard_at='M2'))


if __name__ == '__main__':
    unittest.main()
