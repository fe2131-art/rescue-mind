"""Study XD (image level, depot): protocol generator, label builder and analysis, on the protocol itself and on synthetic scores
(no model, no Gazebo, no images)."""
import json
import math
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind import depot  # noqa: E402
from rescuemind.layout import _dist_point_rect  # noqa: E402
from scripts import build_testset_xd as bx  # noqa: E402
from scripts import make_protocol_xd as mx  # noqa: E402
from scripts import xd_analysis as xa  # noqa: E402


class ProtocolXD(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = mx.build()
        cls.W = cls.p['worlds']

    def test_deterministic_and_registered_file_in_sync(self):
        self.assertEqual(json.dumps(mx.build(), sort_keys=True), json.dumps(self.p, sort_keys=True))
        reg = json.loads((ROOT / 'experiments/campaign_xd_protocol.json').read_text())
        self.assertEqual(reg, json.loads(json.dumps(self.p, ensure_ascii=False)))
        self.assertEqual(self.p['seed'], 'XD-2026')

    def test_sizes(self):
        self.assertEqual(len(self.W), 308)
        self.assertEqual(self.p['class_counts'], {'ok': 45, 'wrong_swapped': 20, 'wrong_empty': 15, 'tongues_big': 12,
                                                  'tongues_small': 100, 'smoke_only': 20, 'mesh_flame': 12, 'sprite': 8, 'twin': 76})
        self.assertEqual((self.p['planned_images'], self.p['planned_extra_images'], self.p['planned_ablation_images']), (924, 684, 324))
        ids = [w['id'] for w in self.W] + [w['id'] for w in self.p['ablation_worlds']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(sum(w['kind'] == 'hazard' for w in self.W), 152)

    def test_worlds_use_the_four_bay_depot_and_the_polish_options(self):
        for w in self.W:
            dep = w['world_spec']['depot']
            self.assertEqual(dep['stations'], 4)
            self.assertEqual(dep['pallets'], 'wood_cartons')
            self.assertEqual(set(dep['supply_at']), set(depot.K4_IDS))
            self.assertTrue(all(v in ('water', 'medicine', None) for v in dep['supply_at'].values()))
            self.assertIn(w['depot_station'], depot.K4_IDS)
            self.assertEqual(w['scene'], 'nominal')

    def test_the_checked_pallet_holds_what_the_class_says(self):
        for w in self.W:
            held = w['world_spec']['depot']['supply_at'][w['depot_station']]
            if w['cls'] == 'wrong_swapped':
                self.assertEqual(held, mx.OTHER[w['item']]); self.assertEqual(w['truth_supply'], held)
            elif w['cls'] == 'wrong_empty':
                self.assertIsNone(held); self.assertEqual(w['truth_supply'], 'other')
            else:
                self.assertEqual(held, w['item']); self.assertEqual(w['truth_supply'], w['item'])

    def test_hazard_classes_geometry_and_appearance(self):
        want_style = {'tongues_big': None, 'tongues_small': None, 'smoke_only': 'smoke_only', 'mesh_flame': 'mesh_flame', 'sprite': 'billboard'}
        for w in self.W:
            spec, dep = w['world_spec'], w['world_spec']['depot']
            if w['kind'] != 'hazard':
                self.assertNotIn('hazard_at', spec); self.assertNotIn('hazard_style', dep)
                continue
            self.assertEqual(spec['hazard_at'], w['depot_station'])
            back, lat, scale = spec['hazard_geom']
            self.assertEqual(dep.get('hazard_style'), want_style[w['cls']])
            self.assertIn(w['size_class'], ('big', 'small'))
            if w['cls'] == 'tongues_big':
                self.assertTrue(.75 <= back <= 1.0 and .25 <= abs(lat) <= .6 and scale == 1.0)
            elif w['size_class'] == 'small':           # the F/G/H/W geometry, mostly hidden at the front
                self.assertTrue(.55 <= back <= .75 and abs(lat) <= .15)
                self.assertTrue((.6 <= scale <= 1.0) if w['cls'] == 'smoke_only' else (.45 <= scale <= .62))
            else:
                self.assertTrue(.55 <= back <= 1.0 and .05 <= abs(lat) <= .4 and .8 <= scale <= 1.0)
        self.assertEqual(Counter(w['size_class'] for w in self.W if w['cls'] == 'tongues_small'), {'small': 100})
        self.assertEqual(Counter(w['cls'] for w in self.W if w['kind'] == 'hazard' and w['world_spec']['depot'].get('hazard_style')),
                         {'smoke_only': 20, 'mesh_flame': 12, 'sprite': 8})      # 40 hazard worlds do not look like our flame

    def test_lookalikes_only_on_fire_free_worlds_and_the_rest_of_the_draw_is_unchanged(self):
        d = [w for w in self.W if 'distractor_kind' in w['world_spec']]
        self.assertEqual(Counter((w['cls'], w['world_spec']['distractor_kind']) for w in d),
                         {('ok', 'box'): 7, ('ok', 'crate'): 7, ('ok', 'cone'): 6, ('wrong_empty', 'box'): 5, ('wrong_empty', 'crate'): 5})
        for w in d:
            sp = w['world_spec']
            self.assertEqual((sp['distractor_at'], sp['distractor_layout'], sp['distractor_side'] in (-1.0, 1.0)), (w['depot_station'], 'platform', True))
            self.assertNotIn('hazard_at', sp)
        if not depot.available():
            return
        # a lookalike world still builds, with the distractor
        from rescuemind.robust_scenes import build_variant
        import xml.etree.ElementTree as ET
        w = d[0]
        kw = json.loads(json.dumps(w['world_spec']))
        names = [m.get('name') for m in ET.fromstring(build_variant(ROOT / 'worlds/scenarios/rescuemind_nominal.sdf', **kw)).find('world').findall('model')]
        self.assertTrue([n for n in names if n.startswith('distractor_')])

    def test_bays_are_balanced_within_each_class(self):
        for cls in mx.CLASSES:
            c = Counter(w['depot_station'] for w in self.W if w['cls'] == cls)
            self.assertLessEqual(max(c.values()) - min(c.values()), 1, cls)

    def test_twins(self):
        by = {w['id']: w for w in self.W}
        twins = [w for w in self.W if w['kind'] == 'twin']
        self.assertEqual(len(twins), 76)
        for t in twins:
            f = by[t['twin_of']]
            self.assertEqual(f['kind'], 'hazard')
            self.assertEqual((f['item'], f['depot_station'], f['views'], t['split']), (t['item'], t['depot_station'], t['views'], f['split']))
            drop = ('hazard_at', 'hazard_geom')
            self.assertEqual({k: v for k, v in f['world_spec'].items() if k not in drop and k != 'depot'},
                             {k: v for k, v in t['world_spec'].items() if k != 'depot'})
            self.assertEqual({k: v for k, v in f['world_spec']['depot'].items() if k not in ('hazard_style', 'particle_smoke')},
                             t['world_spec']['depot'])
        self.assertEqual(Counter(by[t['twin_of']]['cls'] for t in twins),
                         {'tongues_big': 6, 'tongues_small': 50, 'smoke_only': 10, 'mesh_flame': 6, 'sprite': 4})

    def test_views_follow_the_depot_geometry_with_bounded_pose_error(self):
        sd = mx.POSE_SD
        for w in self.W:
            st = w['depot_station']
            nominal = {'F': depot.k4_design_pose(st), 'L': depot.k4_side_pose(st, -0.4), 'R': depot.k4_side_pose(st, 0.4),
                       'L2': depot.k4_side_pose(st, -0.8), 'R2': depot.k4_side_pose(st, 0.8), 'N': depot.k4_near_pose(st, 0.3)}
            self.assertEqual(set(w['views']), set(nominal) if w['kind'] in ('hazard', 'twin') else {'F', 'L', 'R'})
            for v, pose in w['views'].items():
                for i in range(3):
                    self.assertLessEqual(abs(pose[i] - nominal[v][i]), mx.POSE_TRUNC_SD * sd[i] + 1e-3)

    def test_every_view_is_clear_of_pallets_and_furniture(self):
        rects = depot.k4_rects()
        for w in self.W:
            dep = w['world_spec']['depot']
            placed = [p for p in depot.placements(dep['seed'], dep['obstacle'], 4) if p[0] not in ('WallB_01', 'GroundB_01')]
            for v, (x, y, _yaw) in w['views'].items():
                self.assertGreater(min(_dist_point_rect(x, y, r) for r in rects.values()), 0.35, (w['id'], v))
                for n, inst, fx, fy, fyaw in placed:
                    hx, hy = depot.FOOTPRINT.get(n, (.6, .6))
                    if n in depot.CLUTTER_MODELS:
                        hx = hy = max(hx, hy)
                    self.assertGreater(_dist_point_rect(x, y, (fx, fy, fyaw, hx, hy)), 0.25, (w['id'], v, inst))

    def test_split(self):
        cal = [w for w in self.W if w['split'] == 'cal']
        self.assertTrue(115 <= len(cal) <= 130)
        for cls, n in mx.CLASSES.items():
            k = sum(w['split'] == 'cal' for w in self.W if w['cls'] == cls)
            self.assertLessEqual(abs(k - mx.CAL_FRACTION * n), 1.0, cls)
        self.assertEqual({w['split'] for w in self.W}, {'cal', 'test'})

    def test_ablation_worlds_differ_by_exactly_one_feature(self):
        by = {w['id']: w for w in self.W}
        A = self.p['ablation_worlds']
        self.assertEqual(len(A), 108)
        self.assertEqual(len(self.p['ablation_base_worlds']), 12)
        self.assertEqual(Counter(a['variant'] for a in A),
                         {'no_clutter': 24, 'default_light': 24, 'no_surroundings': 24, 'plain_platforms': 24, 'no_particle_smoke': 12})
        for a in A:
            base = by[a['ablation_base']]
            self.assertEqual(a['views'], {v: base['views'][v] for v in mx.VIEWS})
            self.assertEqual((a['cls'], a['kind'], a['split']), (base['cls'], base['kind'], base['split']))
            s0, s1 = base['world_spec'], a['world_spec']
            if a['variant'] == 'default_light':
                self.assertEqual(s1['lighting'], 'default'); self.assertNotIn('lighting_params', s1)
                self.assertEqual({k: v for k, v in s0.items() if k != 'lighting_params'}, {k: v for k, v in s1.items() if k != 'lighting'})
            else:
                self.assertEqual({k: v for k, v in s0.items() if k != 'depot'}, {k: v for k, v in s1.items() if k != 'depot'})
                key, new = {'no_clutter': ('clutter', False), 'no_surroundings': ('surroundings', False),
                            'plain_platforms': ('pallets', None), 'no_particle_smoke': ('particle_smoke', None)}[a['variant']]
                d0, d1 = s0['depot'], s1['depot']
                self.assertEqual({k: v for k, v in d1.items() if k != key}, {k: v for k, v in d0.items() if k != key})
                self.assertEqual(d1.get(key), new)
        hz = [by[b] for b in self.p['ablation_base_worlds']]
        self.assertTrue(all(w['kind'] == 'hazard' and w['world_spec']['depot']['particle_smoke'] for w in hz))
        self.assertLessEqual(max(Counter(w['cls'] for w in hz).values()), 4)

    def test_all_worlds_build_into_parsing_sdf(self):
        if not depot.available():
            self.skipTest('depot assets not fetched')
        import xml.etree.ElementTree as ET
        sample = self.W[::9] + self.p['ablation_worlds'][::10] + [w for w in self.W if w['cls'] in ('mesh_flame', 'sprite', 'smoke_only')][:3]
        for w in sample:
            for mask in (False, True):
                root = ET.fromstring(bx.world_sdf(w, mask))
                names = [m.get('name') for m in root.find('world').findall('model')]
                self.assertEqual(len(names), len(set(names)), w['id'])
                self.assertEqual(any(n.startswith('hazard_fire_') for n in names), bx.has_mask(w), w['id'])


class BuilderXD(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = mx.build()

    def test_view_label_rule_and_world_labels(self):
        self.assertEqual([bx.view_label(p) for p in (0, 20, 21, 613, 614, 9000)], ['hidden', 'hidden', 'ambiguous', 'ambiguous', 'visible', 'visible'])
        wl = bx.world_labels({'F': 0, 'L': 700, 'R': 5, 'L2': 900, 'R2': 0, 'N': 0})
        self.assertEqual((wl['perceivable'], wl['front_perceivable'], wl['side_only']), (True, False, True))
        wl = bx.world_labels({'F': 0, 'L': 10, 'R': 5, 'L2': 900, 'R2': 0, 'N': 0})
        self.assertEqual((wl['perceivable'], wl['perceivable_any_view']), (False, True))     # only an extra view sees it

    def test_label_rows_with_synthetic_pixels(self):
        worlds = bx.all_worlds(self.p)
        pix = {}
        for w in worlds:
            if bx.has_mask(w) and bx.mask_world_id(w) == w['id']:
                for v in bx.all_views(w):
                    pix[(w['id'], v)] = 5000 if v in ('L', 'R') else 0
        rows = bx.build_labels(self.p, pixels=pix)
        self.assertEqual(len(rows), 924 + 684 + 324)
        self.assertEqual(len({r['image'] for r in rows}), len(rows))
        haz = [r for r in rows if r['world_kind'] == 'hazard' and not r['variant']]
        self.assertTrue(all(r['world_side_only'] and r['world_perceivable'] and not r['world_front_perceivable'] for r in haz))
        self.assertTrue(all(r['fire_pixels'] == 0 for r in rows if r['world_kind'] != 'hazard'))
        self.assertTrue(all(not r['world_perceivable'] for r in rows if r['world_kind'] != 'hazard'))
        for r in rows:                         # fields the scorer and the analysis need
            for k in ('image', 'station', 'truth_supply', 'world_id', 'view', 'split', 'cls', 'world_kind', 'hazard_visibility'):
                self.assertIn(k, r)
        smoke = next(r for r in rows if r['cls'] == 'smoke_only')
        self.assertEqual(smoke['hazard_style'], 'smoke_only')
        self.assertEqual(next(r for r in rows if r['cls'] == 'tongues_small')['hazard_style'], 'tongues')

    def test_variants_with_identical_label_geometry_reuse_the_base_masks(self):
        by = {w['id']: w for w in self.p['worlds']}
        for a in self.p['ablation_worlds']:
            same = a['variant'] in ('default_light', 'no_particle_smoke')
            self.assertEqual(bx.mask_world_id(a), a['ablation_base'] if same else a['id'])
        self.assertTrue(all(bx.has_mask(a) == (by[a['ablation_base']]['kind'] == 'hazard') for a in self.p['ablation_worlds']))

    def test_smoke_set_covers_every_class_and_variant(self):
        sw = bx.smoke_worlds(self.p)
        self.assertEqual({w['cls'] for w in sw}, set(mx.CLASSES) | {'twin'})
        self.assertEqual({w.get('variant') for w in sw} - {None}, set(mx.ABLATION_VARIANTS))


# ------------------------------------------------------------------------------------------------ analysis on synthetic scores
def call(hazard, supply_ok=True, item='water'):
    other = {'water': 'medicine', 'medicine': 'water'}[item]
    probs = {item: 0.9, other: 0.1} if supply_ok else {item: 0.1, other: 0.9}
    return {'scores': {'method': 'closed_set_logprob', 'supply_probs': probs, 'hazard_prob': hazard}}


def world(wid, cls, kind, split, hz, supply_ok=True, perceivable=True, front_perceivable=None, side_only=None, extra=None,
          variant=None, base=None, item='water'):
    """hz = {'F': p, 'L': p, 'R': p}; extra = {'L2': p, 'R2': p, 'N': p} or None."""
    truth = item if kind in ('ok', 'twin', 'hazard') and supply_ok else ('medicine' if item == 'water' else 'water')
    fp = (hz['F'] >= 0.05 and perceivable) if front_perceivable is None else front_perceivable
    so = (perceivable and not fp) if side_only is None else side_only
    out = []
    for v, p in {**hz, **(extra or {})}.items():
        out.append({'world_id': wid, 'view': v, 'world_kind': kind, 'cls': cls, 'split': split, 'station': item, 'truth_supply': truth,
                    'world_perceivable': perceivable, 'world_front_perceivable': fp, 'world_side_only': so,
                    'world_perceivable_any_view': perceivable, 'hazard_visibility': 'visible' if (perceivable and p >= 0.05) else 'hidden',
                    'variant': variant, 'ablation_base': base, 'twin_of': None,
                    'passes': {'1': call(p, supply_ok, item), '2': call(p, supply_ok, item)}})
    return out


def hz(f=0.0, l=0.0, r=0.0):
    return {'F': f, 'L': l, 'R': r}


class Primitives(unittest.TestCase):
    def test_fisher_holm_paired(self):
        self.assertAlmostEqual(xa.fisher(3, 0, 0, 3), 0.05)
        self.assertAlmostEqual(xa.fisher(3, 0, 0, 3, 'two-sided'), 0.1)
        self.assertEqual(xa.fisher(0, 3, 3, 0), 1.0)
        self.assertEqual(xa.holm({'a': 0.01, 'b': 0.04, 'c': 0.03}), {'a': 0.03, 'c': 0.06, 'b': 0.06})
        p = xa.paired([True, True, True, False], [False, False, False, False])
        self.assertEqual((p['first_only'], p['second_only']), (3, 0))
        self.assertAlmostEqual(p['mcnemar_p'], 0.25)

    def test_hazard_score_is_fail_closed(self):
        r = world('w', 'ok', 'ok', 'cal', hz())[0]
        self.assertEqual(xa.hazard_score(r), 0.0)
        r['passes']['2'] = {'error': 'boom'}
        self.assertEqual(xa.hazard_score(r), 1.0)
        r = world('w', 'ok', 'ok', 'cal', hz(0.2))[0]
        r['quality'] = {'quality_ok': False}
        self.assertEqual(xa.hazard_score(r), 1.0)
        self.assertFalse(xa.front_allows(r))


class WorldOutcomes(unittest.TestCase):
    def test_front_look_around_and_adaptive(self):
        recs = (world('a', 'tongues_small', 'hazard', 'test', hz(0.0, 0.3, 0.0)) +          # front misses, a side view catches
                world('b', 'tongues_small', 'hazard', 'test', hz(0.0, 0.0, 0.0), perceivable=True) +          # look-around misses too
                world('c', 'tongues_small', 'hazard', 'test', hz(0.0, 0.01, 0.0), extra={'L2': 0.0, 'R2': 0.3, 'N': 0.0}) +   # suspicious, caught late
                world('d', 'tongues_small', 'hazard', 'test', hz(0.0, 0.0, 0.0), extra={'L2': 0.0, 'R2': 0.3, 'N': 0.0}))   # not suspicious: extras unused
        W = xa.world_outcomes(recs)['worlds']
        self.assertEqual((W['a']['front_allow'], W['a']['la_allow']), (True, False))
        self.assertEqual((W['b']['front_allow'], W['b']['la_allow'], W['b']['ad_allow']), (True, True, None))
        self.assertEqual((W['c']['la_allow'], W['c']['ad_allow'], W['c']['triggered']), (True, False, True))
        self.assertEqual((W['d']['la_allow'], W['d']['ad_allow'], W['d']['triggered']), (True, True, False))

    def test_incomplete_worlds_are_listed_and_excluded(self):
        recs = world('a', 'ok', 'ok', 'cal', hz())[:2]
        wo = xa.world_outcomes(recs)
        self.assertEqual((wo['worlds'], wo['incomplete']), ({}, ['a']))


def synthetic_main():
    recs = []
    for i in range(20):                      # small hidden fires: the front check never sees them, 12 are caught by a side view
        recs += world(f'ts{i}', 'tongues_small', 'hazard', 'test', hz(0.0, 0.3 if i < 12 else 0.0, 0.0), extra={'L2': 0.0, 'R2': 0.0, 'N': 0.0})
    for i in range(10):                      # large visible fires: the front check refuses
        recs += world(f'tb{i}', 'tongues_big', 'hazard', 'test', hz(0.9, 0.9, 0.9), extra={'L2': 0.9, 'R2': 0.9, 'N': 0.9})
    for i in range(10):                      # smoke only: half missed even with look-around
        recs += world(f'so{i}', 'smoke_only', 'hazard', 'test', hz(0.0, 0.3 if i % 2 else 0.0, 0.0), extra={'L2': 0.0, 'R2': 0.0, 'N': 0.0})
    for i in range(8):                       # wrong supply: refused by the supply check
        recs += world(f'ws{i}', 'wrong_swapped', 'wrong', 'test', hz(), supply_ok=False, perceivable=False)
    for i in range(10):                      # fire-free, correct supply
        recs += world(f'ok{i}', 'ok', 'ok', 'test', hz(0.0, 0.0, 0.0 if i else 0.2), perceivable=False)       # one false stop
    for i in range(6):
        recs += world(f'tw{i}', 'twin', 'twin', 'test', hz(0.0, 0.01 if i == 0 else 0.0, 0.0), perceivable=False,
                      extra={'L2': 0.0, 'R2': 0.0, 'N': 0.0})
    return recs


class SummaryMain(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = xa.summarise_main(synthetic_main(), ref={})

    def test_eps_per_class(self):
        s = self.s
        self.assertEqual((s['n_hazard'], s['n_perceivable']), (40, 40))
        self.assertEqual((s['xd1_pooled']['front_only']['k'], s['xd1_pooled']['front_only']['n']), (30, 40))
        self.assertEqual(s['xd1_pooled']['look_around']['k'], 8 + 5)
        c = s['xd1_by_class']
        self.assertEqual((c['tongues_small']['front_only']['k'], c['tongues_small']['look_around']['k']), (20, 8))
        self.assertEqual((c['tongues_big']['front_only']['k'], c['tongues_big']['look_around']['k']), (0, 0))
        self.assertEqual((c['smoke_only']['look_around']['k'], c['smoke_only']['look_around']['n']), (5, 10))
        self.assertEqual(c['mesh_flame']['look_around']['n'], 0)
        self.assertEqual(s['xd1_outside_arena_appearances']['look_around']['n'], 10)
        self.assertEqual(s['xd1_k_eps']['point'], round(4 * 13 / 40, 4))
        self.assertEqual(sorted(s['missed_worlds_look_around'])[:2], ['so0', 'so2'])

    def test_fire_free_and_wrong_supply(self):
        s = self.s
        ca = s['xd3_correct_approvals']
        self.assertEqual((ca['ok']['front_only']['k'], ca['ok']['front_only']['n']), (10, 10))
        self.assertEqual((ca['ok']['look_around']['k'], ca['ok']['extra_false_stop_from_side_views']['k']), (9, 1))
        self.assertEqual((ca['pooled']['look_around']['k'], ca['pooled']['look_around']['n']), (15, 16))
        self.assertEqual((s['xd3_extra_view_trigger_rate_on_twins']['k'], s['xd3_extra_view_trigger_rate_on_twins']['n']), (1, 6))
        wf = s['xd3_wrong_supply_false_approvals']
        self.assertEqual((wf['pooled']['front_only']['k'], wf['pooled']['front_only']['n']), (0, 8))
        self.assertEqual(list(s['xd3_by_lookalike_ok_worlds']), ['None'])                      # no lookalike in the synthetic set

    def test_registered_criteria(self):
        c = self.s['criteria']
        self.assertTrue(c['O1_look_around_removes_at_least_half_of_front_misses'])       # R6: an effect size that can fail
        self.assertNotIn('O1_look_around_fewer_misses', c)
        self.assertIn('descriptive_look_around_fewer_misses_mcnemar_p', c)
        self.assertTrue(c['O2_small_hidden_harder_than_big_visible'])
        self.assertTrue(c['O3_adaptive_no_worse_and_trigger_rate_at_most_0.15'] is False)   # 1/6 = 0.167 > 0.15
        self.assertTrue(c['O4_no_wrong_supply_false_approval'])
        self.assertTrue(c['C1_correct_approvals_at_least_0.80'])
        self.assertFalse(c['claim_relative_ordering_transfers'])    # one criterion failed -> the claim is not made
        self.assertTrue(c['P1_smoke_only_miss_rate_at_least_tongues'])
        self.assertEqual(c['P2_class_order_by_look_around_miss_rate'][0], 'smoke_only')

    def test_hard_class_eps_six_view_and_oracle_steering(self):
        s = self.s
        c = s['criteria']
        hc = s['xd1_by_class']['tongues_small']['look_around']
        self.assertEqual(c['XDe_hard_class_upper_bound_below_0.15'], bool(hc['n'] and hc['ci95'][1] <= 0.15))
        self.assertEqual(c['claim_eps_tight_hard_class'], c['XDe_hard_class_upper_bound_below_0.15'])
        sv = s['xd1_six_view']
        self.assertEqual(sv['n_perceivable_any_view'] + sv['n_not_visible_from_any_view'], s['n_hazard'])
        self.assertEqual(sv['share_not_visible_from_any_view']['n'], s['n_hazard'])
        os_ = s['oracle_steering']['pooled']['label_FLR']['look_around']
        la = s['xd1_pooled']['look_around']
        self.assertEqual((os_['missed'], os_['n']), (la['k'], la['n']))
        self.assertEqual(os_['by_k']['1']['eps_any'], round(la['k'] / la['n'], 4))
        self.assertLessEqual(os_['by_k']['4']['eps_any'], os_['by_k']['4']['sum_bound'])
        self.assertIn('hard_class_tongues_small', s['oracle_steering'])
        # the by-construction parts are descriptive, not claim conditions
        self.assertEqual(c['descriptive_adaptive_misses_vs_look_around']['n'], s['xd1_pooled']['adaptive']['n'])

    def test_criteria_boundaries(self):
        recs = [r for r in synthetic_main() if not r['world_id'].startswith('tw')]
        for i in range(10):
            recs += world(f'tw{i}', 'twin', 'twin', 'test', hz(), perceivable=False, extra={'L2': 0.0, 'R2': 0.0, 'N': 0.0})
        c = xa.summarise_main(recs, ref={})['criteria']
        self.assertTrue(c['O3_adaptive_no_worse_and_trigger_rate_at_most_0.15'])
        self.assertTrue(c['claim_relative_ordering_transfers'])
        # one wrong-supply approval breaks O4 and the claim
        recs += world('wsx', 'wrong_swapped', 'wrong', 'test', hz(), supply_ok=True, perceivable=False, item='water')
        recs = [dict(r, truth_supply='medicine') if r['world_id'] == 'wsx' else r for r in recs]
        c = xa.summarise_main(recs, ref={})['criteria']
        self.assertFalse(c['O4_no_wrong_supply_false_approval'])
        self.assertFalse(c['claim_relative_ordering_transfers'])

    def test_arena_comparison_is_a_re_estimate_not_a_transfer(self):
        ref = {'w_a': {'miss_look_around': xa.rate(1, 130), 'miss_front_only': xa.rate(60, 130),
                       'twin_correct_approval_look_around': xa.rate(70, 75)}, 't2': {'false_approvals': 0, 'n_deny': 407,
                                                                                    'correct_approvals': 190, 'n_allow': 193}}
        a = xa.summarise_main(synthetic_main(), ref=ref)['arena_reference']
        self.assertIn('re-estimated', a['note'])
        self.assertLess(a['eps_look_around_depot_vs_arena_W']['fisher_two_sided_p'], 0.01)
        self.assertFalse(a['eps_look_around_depot_vs_arena_W']['arena_point_inside_depot_ci'])
        self.assertEqual(a['false_approval_depot_vs_arena_T2']['arena']['n'], 407)
        self.assertFalse(xa.summarise_main(synthetic_main(), ref={})['arena_reference']['available'])

    def test_real_arena_reference_files_are_readable(self):
        ref = xa.arena_reference()
        self.assertEqual((ref['t2']['false_approvals'], ref['t2']['n_deny']), (0, 407))
        self.assertEqual(xa.arena_reference(ROOT / 'no_such_dir'), {})


class Recalibration(unittest.TestCase):
    def test_choose_tau_is_the_p2_rule(self):
        self.assertEqual(xa.choose_tau([0.5] * 19 + [0.03], [0.2] * 5), 0.5)
        self.assertEqual(xa.choose_tau([0.5] * 18 + [0.03, 0.03], [0.2] * 5), 0.02)
        self.assertEqual(xa.choose_tau([0.1] * 20, []), 0.1)            # tau is inclusive
        self.assertIsNone(xa.choose_tau([0.0] * 20, [0.0]))
        self.assertIsNone(xa.choose_tau([], [0.0]))
        self.assertEqual(xa.GRID[:5], [0.01, 0.02, 0.05, 0.1, 0.15])

    def build(self, neg_cal=0.2, neg_test=0.2, pos=0.5):
        recs = []
        for sp, neg in (('cal', neg_cal), ('test', neg_test)):
            for i in range(10):
                recs += world(f'{sp}h{i}', 'tongues_small', 'hazard', sp, hz(pos, pos, pos))
                recs += world(f'{sp}o{i}', 'ok', 'ok', sp, hz(neg, 0.0, 0.0), perceivable=False)
        return recs

    def test_threshold_moves_and_is_tested_on_the_test_split(self):
        r = xa.recalibrate(self.build())
        self.assertEqual(r['calibration']['tau_star'], 0.5)
        self.assertTrue(r['moved'])
        self.assertEqual((r['calibration']['n_pos'], r['calibration']['n_neg']), (30, 30))
        self.assertEqual(r['calibration']['at_tau_star']['false_alarm']['k'], 0)      # negatives score 0.2 < 0.5 (1 of 3 views)
        t = r['test_image_level']
        self.assertEqual(t['at_frozen']['false_alarm']['k'], 10)                      # at 0.05 the 0.2 scores are alarms
        self.assertEqual(t['at_tau_star']['false_alarm']['k'], 0)
        self.assertEqual(t['at_tau_star']['recall']['rate'], 1.0)
        self.assertTrue(r['claim_calibration_usable'])
        self.assertFalse(r['claim_frozen_tau_usable'])                                # 10/30 = 0.33 false alarms > 0.20
        wl = r['test_world_level']
        self.assertEqual(wl['at_frozen']['correct_approval_look_around']['k'], 0)
        self.assertEqual(wl['at_tau_star']['correct_approval_look_around']['k'], 10)

    def test_the_frozen_threshold_can_be_kept(self):
        recs = []
        for sp in ('cal', 'test'):
            for i in range(10):
                recs += world(f'{sp}h{i}', 'tongues_small', 'hazard', sp, hz(0.06, 0.06, 0.06))
                recs += world(f'{sp}o{i}', 'ok', 'ok', sp, hz(), perceivable=False)
        r = xa.recalibrate(recs)
        self.assertEqual(r['calibration']['tau_star'], 0.05)
        self.assertFalse(r['moved'])
        self.assertTrue(r['claim_frozen_tau_usable'])

    def test_ablation_and_extra_views_never_enter_the_calibration(self):
        recs = self.build() + world('v1', 'tongues_small', 'hazard', 'cal', hz(0.0, 0.0, 0.0), variant='no_clutter', base='calh0')
        r = xa.recalibrate(recs)
        self.assertEqual(r['calibration']['n_pos'], 30)
        extra = world('x', 'tongues_small', 'hazard', 'cal', hz(0.9, 0.9, 0.9), extra={'L2': 0.9, 'R2': 0.9, 'N': 0.9})
        self.assertEqual(xa.recalibrate(self.build() + extra)['calibration']['n_pos'], 33)


class Ablation(unittest.TestCase):
    def test_paired_per_variant_with_holm(self):
        recs = []
        for i in range(12):                      # base: 12 perceivable hazard worlds, look-around misses 2; 12 twins, 1 false stop
            recs += world(f'h{i}', 'tongues_small', 'hazard', 'test', hz(0.0, 0.3 if i >= 2 else 0.0, 0.0))
            recs += world(f't{i}', 'twin', 'twin', 'test', hz(0.0, 0.2 if i == 0 else 0.0, 0.0), perceivable=False)
        for i in range(12):                      # no_clutter: every miss again, 8 more fires missed; default_light: unchanged
            recs += world(f'h{i}_no_clutter', 'tongues_small', 'hazard', 'test', hz(0.0, 0.0 if i < 10 else 0.3, 0.0),
                          variant='no_clutter', base=f'h{i}')
            recs += world(f'h{i}_default_light', 'tongues_small', 'hazard', 'test', hz(0.0, 0.3 if i >= 2 else 0.0, 0.0),
                          variant='default_light', base=f'h{i}')
            recs += world(f't{i}_no_clutter', 'twin', 'twin', 'test', hz(), perceivable=False, variant='no_clutter', base=f't{i}')
        a = xa.ablation(recs)
        nc = a['no_clutter']
        self.assertEqual((nc['n_hazard_pairs'], nc['miss_base']['k'], nc['miss_variant']['k']), (12, 2, 10))
        self.assertEqual((nc['miss_paired']['first_only'], nc['miss_paired']['second_only']), (0, 8))
        self.assertLess(nc['miss_holm_p'], 0.05)
        self.assertEqual((nc['false_stop_base']['k'], nc['false_stop_variant']['k']), (1, 0))
        self.assertEqual(a['default_light']['miss_paired'], {'first_only': 0, 'second_only': 0, 'mcnemar_p': 1.0})
        self.assertEqual(a['features_that_move_eps'], ['no_clutter'])
        self.assertEqual(a['features_that_move_false_stops'], [])
        self.assertEqual(a['no_surroundings']['n_hazard_pairs'], 0)

    def test_a_hazard_not_perceivable_in_the_variant_is_not_a_pair(self):
        recs = world('h0', 'tongues_small', 'hazard', 'test', hz(0.0, 0.3, 0.0)) + \
            world('h0_no_clutter', 'tongues_small', 'hazard', 'test', hz(), perceivable=False, variant='no_clutter', base='h0')
        a = xa.ablation(recs)['no_clutter']
        self.assertEqual((a['n_hazard_pairs'], a['n_not_perceivable_in_variant']), (0, 1))


class Driver(unittest.TestCase):
    def test_analyse_runs_end_to_end(self):
        out = xa.analyse(synthetic_main() + TestRecal.recs(), ref={})
        self.assertEqual(set(out), {'registered', 'tau_s', 'tau_h', 'XD_main', 'XD_recalibration', 'XD_ablation'})
        json.dumps(out)                           # serialisable


class TestRecal:
    @staticmethod
    def recs():
        out = []
        for sp in ('cal', 'test'):
            for i in range(5):
                out += world(f'{sp}h{i}', 'tongues_small', 'hazard', sp, hz(0.5, 0.5, 0.5))
                out += world(f'{sp}o{i}', 'ok', 'ok', sp, hz(), perceivable=False)
        return out


if __name__ == '__main__':
    unittest.main()
