"""Study L: layout randomisation support keeps the default arena byte-identical and samples feasible layouts."""
import importlib.util
import json
import math
import random
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind import layout as L
from rescuemind.camera_aim import station_centers
from rescuemind.robust_scenes import build_variant, hazard_xy, platform_side_offset
from scripts.v32_orchestrate import build_plan, waypoint_config_path, WORLD_SPEC_KEYS

SCENES = ROOT / 'worlds/scenarios'


def _wp():
    return json.loads((ROOT / 'configs/gazebo_waypoints.json').read_text())


def _poses(sdf: bytes):
    w = ET.fromstring(sdf).find('world')
    return {m.get('name'): [float(v) for v in m.findtext('pose').split()] for m in w.findall('model') if m.findtext('pose')}


class DefaultLayoutTests(unittest.TestCase):
    def test_default_equals_current_configs(self):
        wp, centers = L.default_layout().to_configs()
        self.assertEqual(wp, _wp())
        self.assertEqual(centers, json.loads((ROOT / 'configs/gazebo_station_centers.json').read_text()))
        self.assertTrue(L.default_layout().is_default())

    def test_default_matches_sdf_models(self):
        poses = _poses(build_variant(SCENES / 'rescuemind_nominal.sdf'))
        d = L.default_layout()
        for key, model in (('water', 'aid_station_water'), ('medicine', 'aid_station_medicine'), ('B', 'shelter_B')):
            self.assertEqual(poses[model][:2], list(d.center(key)))
            self.assertEqual(poses[model][5], d.pose(key)[2])

    def test_default_is_feasible(self):
        self.assertEqual(L.check_layout(L.default_layout()), [])

    def test_dict_round_trip(self):
        for lay in (L.default_layout(), L.sample_layout(random.Random(3))):
            self.assertEqual(L.Layout.from_dict(json.loads(json.dumps(lay.to_dict()))), lay)

    def test_bad_layout_rejected(self):
        with self.assertRaises(ValueError):
            L.Layout.from_dict({'water': [1, 2], 'medicine': [0, 0, 0], 'B': [0, 0, 0]})
        with self.assertRaises(ValueError):
            L.Layout.from_dict({'water': [1, 2, float('nan')], 'medicine': [0, 0, 0], 'B': [0, 0, 0]})


class SamplingTests(unittest.TestCase):
    def test_200_seeds_satisfy_constraints(self):
        for seed in range(200):
            lay = L.sample_layout(random.Random(seed))
            self.assertEqual(L.check_layout(lay), [], f'seed {seed}')
            # independent re-statement of the headline constraints
            c = {n: lay.center(n) for n in L.NAMES}
            wp = {n: lay.waypoint(n) for n in L.NAMES}
            for n in L.NAMES:
                self.assertLessEqual(abs(c[n][0]), 4.5)
                self.assertLessEqual(abs(c[n][1]), 3.5)
                self.assertTrue(2.2 <= math.hypot(*c[n]) <= 4.0)
                self.assertGreaterEqual(math.hypot(*wp[n]), 1.0)
                self.assertLessEqual(abs(lay.pose(n)[2]), math.radians(45) + 1e-9)
            for a in L.NAMES:
                for b in L.NAMES:
                    if a < b:
                        self.assertGreaterEqual(math.dist(c[a], c[b]), 2.5)
                        self.assertGreaterEqual(math.dist(wp[a], wp[b]), 1.5)
            for s in ('water', 'medicine'):
                self.assertGreaterEqual(math.dist(wp[s], wp['B']), 1.0)
            # start region (robot spawns at the origin) clear of every footprint
            for n in L.NAMES:
                self.assertGreaterEqual(L._dist_point_rect(0, 0, L._footprint(lay, n)), 0.6)
            # straight-leg clearance 0.6 m from the stations the leg is not heading to
            for name, a, b, own in L.executed_legs(lay, 0.4):
                for n in L.NAMES:
                    if n not in own:
                        self.assertGreaterEqual(L._dist_seg_rect(a, b, L._footprint(lay, n)), 0.6, (seed, name, n))

    def test_sampling_deterministic_and_varied(self):
        a = [L.sample_layout(random.Random(s)).to_dict() for s in range(5)]
        b = [L.sample_layout(random.Random(s)).to_dict() for s in range(5)]
        self.assertEqual(a, b)
        self.assertGreater(len({json.dumps(x) for x in a}), 1)

    def test_infeasible_layouts_flagged(self):
        d = L.default_layout()
        crowded = L.Layout((2.0, 2.0, 0.0), (2.0, 1.0, 0.0), d.B)
        self.assertTrue(L.check_layout(crowded))
        outside = L.Layout((5.5, 2.0, 0.0), d.medicine, d.B)
        self.assertTrue(any('outside arena' in v for v in L.check_layout(outside)))
        # a station standing in the straight leg to the other one
        blocking = L.Layout((3.0, 0.0, 0.0), (3.9, 0.1, 0.0), (-2.5, -2.0, 0.0))
        self.assertTrue(L.check_layout(blocking))

    def test_derived_waypoint_standoff(self):
        lay = L.Layout((3.0, 0.0, 0.0), (0.0, 3.0, 0.0), (-3.0, 0.0, 0.0))
        self.assertEqual(lay.waypoint('water'), (1.8, 0.0))
        self.assertEqual(lay.waypoint('medicine'), (0.0, 1.8))


class BuildVariantTests(unittest.TestCase):
    CASES = [dict(), dict(hazard_at='water'), dict(hazard_at='medicine', hazard_geom=(0.75, 0.5, 0.6)),
             dict(distractor_at='water'),
             dict(distractor_at='medicine', distractor_layout='platform', distractor_kind='crate'),
             dict(lighting='dim_evening', distractor_at='water', hazard_at='medicine'),
             dict(prop_offsets={'sealed_water_bottles': (0.05, -0.02, 0.3)}, hazard_at='water', hazard_mask=True)]

    def test_default_layout_same_bytes(self):
        for scene in ('nominal', 'swapped', 'empty'):
            src = SCENES / f'rescuemind_{scene}.sdf'
            for kw in self.CASES:
                ref = build_variant(src, **kw)
                self.assertEqual(build_variant(src, layout=L.default_layout(), **kw), ref, (scene, kw))
                self.assertEqual(build_variant(src, layout=L.default_layout().to_dict(), **kw), ref)
                self.assertEqual(build_variant(src, layout=None, **kw), ref)

    def test_layout_moves_everything_together(self):
        lay = L.Layout((3.0, 1.0, 0.4), (-1.0, 3.2, -0.5), (1.0, -3.0, 0.2))
        for scene in ('nominal', 'swapped'):
            poses = _poses(build_variant(SCENES / f'rescuemind_{scene}.sdf', layout=lay, hazard_at='medicine',
                                         distractor_at='water', distractor_layout='platform'))
            self.assertEqual(poses['aid_station_water'], [3.0, 1.0, 0.0, 0.0, 0.0, 0.4])
            self.assertEqual(poses['aid_station_medicine'][:2], [-1.0, 3.2])
            self.assertEqual(poses['shelter_B'][:2], [1.0, -3.0])
            self.assertAlmostEqual(poses['shelter_B'][5], 0.2)
            self.assertAlmostEqual(poses['first_aid_case' if scene == 'nominal' else 'sealed_water_bottles'][5], -0.5)
            hx, hy = hazard_xy('medicine', stations=lay.centers())
            self.assertEqual(poses['hazard_fire_medicine'][:2], [float(f'{hx:g}'), float(f'{hy:g}')])
            ox, oy = platform_side_offset('water', 1.0, stations=lay.centers())
            self.assertEqual(poses['distractor_box_water'][:2], [float(f'{3.0 + ox:g}'), float(f'{1.0 + oy:g}')])
            self.assertNotEqual(poses['hazard_fire_medicine'][:2], list(hazard_xy('medicine')))

    def test_swapped_scene_prop_follows_original_station(self):
        lay = L.Layout((3.0, 1.0, 0.0), (-1.0, 3.2, 0.0), (1.0, -3.0, 0.0))
        nominal = _poses(build_variant(SCENES / 'rescuemind_nominal.sdf', layout=lay))
        swapped = _poses(build_variant(SCENES / 'rescuemind_swapped.sdf', layout=lay))
        self.assertEqual(nominal['sealed_water_bottles'][:2], [3.0, 1.0])
        self.assertEqual(swapped['sealed_water_bottles'][:2], [-1.0, 3.2])    # swapped scene exchanges the props

    def test_empty_platform_decision_unchanged_by_layout(self):
        lay = L.Layout((3.0, 1.0, 0.0), (-1.0, 3.2, 0.0), (1.0, -3.0, 0.0))
        poses = _poses(build_variant(SCENES / 'rescuemind_empty.sdf', layout=lay, distractor_at='water',
                                     distractor_layout='platform'))
        self.assertEqual(poses['distractor_box_water'][:2], [3.0, 1.0])       # empty platform: centred


class CameraAimTests(unittest.TestCase):
    def test_locked_by_default(self):
        with self.assertRaises(ValueError):
            station_centers({'water': [3.0, 1.0], 'medicine': [-1.0, 3.2]})

    def test_layout_config_accepted_when_unlocked(self):
        self.assertEqual(station_centers({'water': [3.0, 1.0], 'medicine': [-1.0, 3.2]}, locked=False),
                         {'water': (3.0, 1.0), 'medicine': (-1.0, 3.2)})

    def test_unlocked_still_validates_shape(self):
        for bad in ({'water': [3.0], 'medicine': [0, 1]}, {'water': [3.0, float('inf')], 'medicine': [0, 1]},
                    {'water': [3.0, True], 'medicine': [0, 1]}, {'water': [1, 2]}, [1, 2]):
            with self.assertRaises(ValueError):
                station_centers(bad, locked=False)


class OrchestratorTests(unittest.TestCase):
    def test_layout_is_a_world_spec_key(self):
        self.assertIn('layout', WORLD_SPEC_KEYS)

    def test_build_plan_passes_centers_only_with_layout(self):
        import shlex
        argv_of = lambda **kw: shlex.split(build_plan('live', 'x', mission_timeout=400, scene='nominal', **kw)['mission'].argv[-1])
        base = argv_of()
        self.assertNotIn('--centers', base)
        self.assertNotIn('--config', base)
        with tempfile.TemporaryDirectory() as td:
            lay = L.sample_layout(random.Random(1))
            wp, centers = lay.write_configs(Path(td))
            argv = argv_of(config_path=wp, centers_path=centers)
            self.assertEqual(argv[argv.index('--centers') + 1], str(centers))
            self.assertEqual(argv[argv.index('--config') + 1], str(wp))
            self.assertEqual(waypoint_config_path(Path(td)), wp)
            written = json.loads(wp.read_text())
            self.assertEqual(written['water'], list(lay.waypoint('water')))
            self.assertEqual(written['limits'], _wp()['limits'])
            self.assertEqual(set(written), set(_wp()))
        # no layout in the run folder -> fixed config
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(waypoint_config_path(Path(td)), ROOT / 'configs/gazebo_waypoints.json')

    def test_no_audit_reads_the_fixed_waypoint_file_directly(self):
        src = (ROOT / 'scripts/v32_orchestrate.py').read_text()
        self.assertEqual(src.count("ROOT/'configs/gazebo_waypoints.json'"), 1)     # only inside waypoint_config_path
        self.assertNotIn('gazebo_station_centers.json', src)

    def test_mission_centers_reader(self):
        src = (ROOT / 'ros/gazebo_waypoint_mission.py').read_text()
        self.assertEqual(src.count("ROOT/'configs/gazebo_station_centers.json'"), 1)       # only inside load_centers
        spec = importlib.util.spec_from_file_location('rm_layout', ROOT / 'ros/gazebo_waypoint_mission.py')
        mission = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mission)
        from types import SimpleNamespace
        self.assertEqual(mission.load_centers(SimpleNamespace())['water'], (2.0, 2.0))
        with tempfile.TemporaryDirectory() as td:
            lay = L.sample_layout(random.Random(2))
            _, centers = lay.write_configs(Path(td))
            self.assertEqual(mission.load_centers(SimpleNamespace(centers=str(centers)))['medicine'],
                             lay.center('medicine'))


class FireMaskPoseTests(unittest.TestCase):
    def test_design_pose(self):
        from scripts.fire_mask_at_pose import design_pose, DESIGN_POSE
        for st in ('water', 'medicine'):
            self.assertEqual(design_pose(st), DESIGN_POSE[st])
            self.assertEqual(design_pose(st, L.default_layout().to_dict()), DESIGN_POSE[st])
        lay = L.sample_layout(random.Random(5))
        x, y, yaw = design_pose('water', lay.to_dict())
        wx, wy = lay.waypoint('water')
        self.assertAlmostEqual(math.hypot(wx - x, wy - y), 0.2, places=2)
        cx, cy = lay.center('water')
        self.assertAlmostEqual(math.atan2(cy - y, cx - x), yaw, places=3)


if __name__ == '__main__':
    unittest.main()
