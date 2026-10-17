#!/usr/bin/env python3
"""Study XD (image level, DRAFT): the v3.6 station check re-measured in the four-bay relief depot (R5 review, item 4).

  python3 scripts/make_protocol_xd.py            # -> experiments/campaign_xd_protocol.json  (seed XD-2026, deterministic)
  python3 scripts/make_protocol_xd.py --force    # while the registration is still a draft: overwrite the file

Generated BEFORE anything is rendered.  200 main worlds (600 images: front + left + right) of the k = 4 depot, drawn over
the factors the depot adds to the arena:
  * clutter seed (movable clutter, pallet jack in the north aisle in 25% of the worlds) and continuous random lighting;
  * the supply arrangement over the four pallets (inventory arrangement or a random re-arrangement incl. empty pallets);
  * the checked bay (W1 M1 W2 M2, balanced) and the requested supply;
  * lookalikes: a cone, crate or box on the checked pallet in 30 of the fire-free worlds;
  * the hazard: none / our ellipsoid flames, large and visible or small and partly hidden (the G/W geometry) / SMOKE ONLY /
    an alternative flame (jagged mesh; alpha-textured sprites) -- the last two classes come from outside the development
    loop of the arena flame (docs/design/I21_realistic_depot.md);
  * supply platforms drawn as wooden pallets with stretch-wrapped cartons (rescuemind.depot, visual only).
Classes (worlds): ok 45 | wrong supply 35 (swapped 20, empty 15) | hazard 80 (tongues_big 12, tongues_small 28, smoke_only 20,
mesh_flame 12, sprite 8) | twin 40 (every second hazard world again, same everything, no hazard).  The hazard worlds
also get three extra views (+-0.8 m, 0.3 m closer: the I-20 suspicion-triggered rule), as do the twins.
A calibration split (40% of the worlds per class, twins with their hazard world) is held apart for the tau_h recalibration.
Realism ablation: 12 hazard worlds with their twins are rendered again with one realism feature off at a time
(no clutter | default lighting | no warehouse around the bays | plain grey platforms | no particle plume), same poses.
Labels come from the generator and the renders (flat-magenta masks), never from a model.
"""
from __future__ import annotations
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind import depot  # noqa: E402
from rescuemind.robust_scenes import random_lighting  # noqa: E402

SEED = 'XD-2026'
OUT = ROOT / 'experiments/campaign_xd_protocol.json'
IDS = depot.K4_IDS
INVENTORY = depot.K4_INVENTORY
OTHER = {'water': 'medicine', 'medicine': 'water'}
# class -> (number of worlds, kind of truth)
CLASSES = {'ok': 45, 'wrong_swapped': 20, 'wrong_empty': 15,
           'tongues_big': 12, 'tongues_small': 28, 'smoke_only': 20, 'mesh_flame': 12, 'sprite': 8}
HAZARD_CLASSES = ('tongues_big', 'tongues_small', 'smoke_only', 'mesh_flame', 'sprite')
STYLE = {'tongues_big': None, 'tongues_small': None, 'smoke_only': 'smoke_only', 'mesh_flame': 'mesh_flame', 'sprite': 'billboard'}
TWIN_EVERY = 2
OBSTACLE_P = 0.25
CAL_FRACTION = 0.4
SIDE_OFFSET_M = 0.4
EXTRA_SIDE_M, NEAR_M = 0.8, 0.3
POSE_SD = (0.011, 0.023, 0.024)        # x [m], y [m], yaw [rad]: arrival error of the closed-loop runs F/G/H (study W)
POSE_TRUNC_SD = 2.5
MIN_FIRE_PX = 614
VIEWS = ('F', 'L', 'R')
VIEWS_EXTRA = ('L2', 'R2', 'N')
N_LOOKALIKE_OK, N_LOOKALIKE_EMPTY = 20, 10
ABLATION_N = 12
ABLATION_VARIANTS = ('no_clutter', 'default_light', 'no_surroundings', 'plain_platforms', 'no_particle_smoke')
# prop models of the depot: the first water / medicine prop keeps the scene's name, later ones are named <name>_<pallet>
PROP_NAMES = tuple(n if not i else f'{n}_{i}' for n in ('sealed_water_bottles', 'first_aid_case') for i in ('', 'M1', 'W2', 'M2'))


def arrangement(rng) -> dict:
    """Content of the four pallets: the inventory's arrangement, or each pallet re-drawn (water / medicine / empty)."""
    sup = dict(INVENTORY)
    if rng.random() < 0.5:
        for i in IDS:
            if rng.random() < 0.5:
                sup[i] = rng.choices(['water', 'medicine', None], weights=[.4, .4, .2])[0]
    return sup


def hazard_geometry(rng, cls: str, big: bool) -> list:
    if cls == 'tongues_big':                     # campaign E/A geometry, full-size fire
        return [round(rng.uniform(.75, 1.0), 3), round(rng.choice([-1, 1]) * rng.uniform(.25, .6), 3), 1.0]
    if not big:                                  # campaign F/G/H/W geometry: small, behind the supply, mostly hidden at the front
        scale = (rng.uniform(.6, 1.0) if cls == 'smoke_only' else rng.uniform(.45, .62))
        return [round(rng.uniform(.55, .75), 3), round(rng.uniform(-.15, .15), 3), round(scale, 3)]
    return [round(rng.uniform(.55, 1.0), 3), round(rng.choice([-1, 1]) * rng.uniform(.05, .4), 3), round(rng.uniform(.8, 1.0), 3)]


def station_views(st: str, rng, extra_rng, with_extra: bool = True) -> dict:
    """Camera poses of the three standard views and the three extra views of bay `st`, each with its own arrival error."""
    nominal = {'F': depot.k4_design_pose(st), 'L': depot.k4_side_pose(st, -SIDE_OFFSET_M), 'R': depot.k4_side_pose(st, SIDE_OFFSET_M),
               'L2': depot.k4_side_pose(st, -EXTRA_SIDE_M), 'R2': depot.k4_side_pose(st, EXTRA_SIDE_M),
               'N': depot.k4_near_pose(st, NEAR_M)}

    def jit(r, pose):
        return [round(pose[i] + _trunc_gauss(r, POSE_SD[i]), 3) for i in range(3)]
    out = {v: jit(rng, nominal[v]) for v in VIEWS}
    extra = {v: jit(extra_rng, nominal[v]) for v in VIEWS_EXTRA}     # always drawn: the streams do not depend on the class
    if with_extra:
        out.update(extra)
    return out


def _trunc_gauss(rng, sd: float) -> float:
    while True:
        z = rng.gauss(0.0, 1.0)
        if abs(z) <= POSE_TRUNC_SD:
            return z * sd


def build() -> dict:
    rng = random.Random(SEED)
    pose_rng = random.Random(SEED + '-poses')
    extra_rng = random.Random(SEED + '-extra-poses')
    worlds, n = [], 0
    stations_cycle = {}
    for cls, count in CLASSES.items():                       # fixed class order: the stream does not depend on what follows
        st_list = [IDS[i % 4] for i in range(count)]
        rng.shuffle(st_list)
        stations_cycle[cls] = st_list
    for cls, count in CLASSES.items():
        for k in range(count):
            st = stations_cycle[cls][k]
            item = rng.choice(['water', 'medicine'])
            sup = arrangement(rng)
            hazard = cls in HAZARD_CLASSES
            if cls == 'ok' or hazard:
                sup[st] = item                              # the checked pallet holds the requested supply (a hazard stands behind it)
            elif cls == 'wrong_swapped':
                sup[st] = OTHER[item]
            else:
                sup[st] = None
            big = hazard and (cls == 'tongues_big' or (cls in ('smoke_only', 'mesh_flame', 'sprite') and k % 2 == 1))
            depot_spec = {'seed': rng.randrange(10 ** 6), 'stations': 4, 'supply_at': sup, 'obstacle': rng.random() < OBSTACLE_P,
                          'pallets': 'wood_cartons'}
            spec = {'lighting_params': random_lighting(rng),
                    'prop_offsets': {p: [round(rng.uniform(-.06, .06), 3), round(rng.uniform(-.06, .06), 3),
                                         round(rng.uniform(-math.pi, math.pi), 3)] for p in PROP_NAMES}}
            if hazard:
                depot_spec['particle_smoke'] = rng.random() < 0.5
                if STYLE[cls]:
                    depot_spec['hazard_style'] = STYLE[cls]
                spec['hazard_at'] = st
                spec['hazard_geom'] = hazard_geometry(rng, cls, big)
            spec['depot'] = depot_spec
            n += 1
            worlds.append({'id': f'xd{n:03d}', 'kind': 'hazard' if hazard else ('ok' if cls == 'ok' else 'wrong'), 'cls': cls,
                           'size_class': ('big' if big else 'small') if hazard else None, 'twin_of': None, 'item': item,
                           'depot_station': st, 'truth_supply': sup[st] or 'other', 'scene': 'nominal',
                           'world_spec': spec, 'views': station_views(st, pose_rng, extra_rng, with_extra=hazard)})
    # lookalikes standing on the checked pallet (separate random stream: nothing else moves): a cone / crate / box beside the supply
    # of 20 ok worlds, a crate / box centred on the empty pallet of 10 wrong_empty worlds (campaign E / T1 distractors)
    d_rng = random.Random(SEED + '-distractors')
    for cls, n_d, kinds in (('ok', N_LOOKALIKE_OK, ('box', 'crate', 'cone')), ('wrong_empty', N_LOOKALIKE_EMPTY, ('box', 'crate'))):
        ids = [w for w in worlds if w['cls'] == cls]
        d_rng.shuffle(ids)
        for k, w in enumerate(ids[:n_d]):
            w['world_spec'].update({'distractor_at': w['depot_station'], 'distractor_kind': kinds[k % len(kinds)],
                                    'distractor_layout': 'platform', 'distractor_side': d_rng.choice([-1.0, 1.0])})
    # twins of every second hazard world
    twins = []
    hazard_worlds = [w for w in worlds if w['kind'] == 'hazard']
    for i, w in enumerate(hazard_worlds):
        if i % TWIN_EVERY == 0:
            spec = json.loads(json.dumps(w['world_spec']))
            for key in ('hazard_at', 'hazard_geom'):
                spec.pop(key, None)
            for key in ('hazard_style', 'particle_smoke'):
                spec['depot'].pop(key, None)
            n += 1
            twins.append({'id': f'xd{n:03d}', 'kind': 'twin', 'cls': 'twin', 'size_class': None, 'twin_of': w['id'],
                          'item': w['item'], 'depot_station': w['depot_station'], 'truth_supply': w['truth_supply'],
                          'scene': 'nominal', 'world_spec': spec, 'views': json.loads(json.dumps(w['views']))})
    worlds += twins
    # calibration split: 40% of every class (twins follow their hazard world)
    split_rng = random.Random(SEED + '-split')
    split = {}
    for cls in CLASSES:
        ids = sorted(w['id'] for w in worlds if w['cls'] == cls)
        split_rng.shuffle(ids)
        cut = round(CAL_FRACTION * len(ids))
        split.update({i: 'cal' for i in ids[:cut]})
        split.update({i: 'test' for i in ids[cut:]})
    for w in worlds:
        w['split'] = split[w['twin_of']] if w['twin_of'] else split[w['id']]
    # realism ablation: hazard worlds with a twin, with the particle plume on
    abl_rng = random.Random(SEED + '-ablation')
    cand = [w for w in hazard_worlds if any(t['twin_of'] == w['id'] for t in twins)]
    abl_rng.shuffle(cand)
    chosen, per_cls = [], {}
    for w in cand:                                         # stratified: at most 4 per class, spread over the classes
        if per_cls.get(w['cls'], 0) < 4 and len(chosen) < ABLATION_N:
            chosen.append(w); per_cls[w['cls']] = per_cls.get(w['cls'], 0) + 1
    for w in chosen:                                       # the plume is part of the full world of these (it is what 'no_particle_smoke' removes)
        w['world_spec']['depot']['particle_smoke'] = True
    ablation = []
    by_twin = {t['twin_of']: t for t in twins}
    for w in sorted(chosen, key=lambda x: x['id']):
        for base in (w, by_twin[w['id']]):
            for var in ABLATION_VARIANTS:
                if var == 'no_particle_smoke' and base['kind'] == 'twin':
                    continue
                ablation.append(ablation_world(base, var))
    n_hazard = len(hazard_worlds)
    proto = {'schema': 'rescuemind_study_xd_protocol', 'seed': SEED, 'status': 'DRAFT',
             'n_main_worlds': len(worlds), 'n_hazard_worlds': n_hazard, 'n_twin_worlds': len(twins),
             'class_counts': {c: sum(w['cls'] == c for w in worlds) for c in list(CLASSES) + ['twin']},
             'planned_images': 3 * len(worlds), 'planned_extra_images': len(VIEWS_EXTRA) * (n_hazard + len(twins)),
             'planned_ablation_images': 3 * len(ablation),
             'ablation_base_worlds': [w['id'] for w in sorted(chosen, key=lambda x: x['id'])],
             'ablation_variants': list(ABLATION_VARIANTS), 'cal_fraction': CAL_FRACTION,
             'side_offset_m': SIDE_OFFSET_M, 'extra_views_m': {'side': EXTRA_SIDE_M, 'near': NEAR_M},
             'pose_error_sd': {'x_m': POSE_SD[0], 'y_m': POSE_SD[1], 'yaw_rad': POSE_SD[2], 'truncated_at_sd': POSE_TRUNC_SD},
             'min_fire_px': MIN_FIRE_PX, 'views': list(VIEWS), 'views_extra': list(VIEWS_EXTRA),
             'note': 'views[F|L|R|L2|R2|N] = [x, y, yaw] of the camera: F 0.2 m short of the bay waypoint facing the pallet, L/R '
                     '0.4 m beside it, L2/R2 0.8 m, N 0.3 m closer (rescuemind.depot.k4_*_pose); the checked bay holds the '
                     'requested supply in ok / hazard / twin worlds, the other supply (wrong_swapped) or nothing (wrong_empty). '
                     'The hazard stands behind the checked pallet (robust_scenes.hazard_xy); hazard_geom = [back m, lateral m, scale]',
             'worlds': worlds, 'ablation_worlds': ablation}
    return proto


def ablation_world(base: dict, variant: str) -> dict:
    """The same world and poses with one realism feature off."""
    spec = json.loads(json.dumps(base['world_spec']))
    dep = spec['depot']
    if variant == 'no_clutter':
        dep['clutter'] = False
    elif variant == 'default_light':
        spec.pop('lighting_params'); spec['lighting'] = 'default'
    elif variant == 'no_surroundings':
        dep['surroundings'] = False
    elif variant == 'plain_platforms':
        dep.pop('pallets', None)
    elif variant == 'no_particle_smoke':
        dep.pop('particle_smoke', None)
    else:
        raise ValueError(variant)
    out = {k: v for k, v in base.items() if k not in ('world_spec', 'id', 'split')}
    out.update({'id': f"{base['id']}_{variant}", 'ablation_base': base['id'], 'variant': variant, 'world_spec': spec,
                'split': base['split'], 'views': {v: base['views'][v] for v in VIEWS}})
    return out


def main(argv=None):
    force = '--force' in (argv if argv is not None else sys.argv[1:])
    proto = build()
    new = json.loads(json.dumps(proto, ensure_ascii=False))
    if OUT.is_file() and json.loads(OUT.read_text()) != new and not force:
        sys.exit('registered protocol differs from the generator output; refusing to overwrite (--force while it is a draft)')
    OUT.write_text(json.dumps(new, ensure_ascii=False, indent=1) + '\n')
    print(proto['n_main_worlds'], 'main worlds', proto['class_counts'], proto['planned_images'], 'images +',
          proto['planned_extra_images'], 'extra +', proto['planned_ablation_images'], 'ablation')


if __name__ == '__main__':
    main()
