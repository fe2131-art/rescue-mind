#!/usr/bin/env python3
"""Study W-a (image level): the miss rate of v3.6, front check only vs front check + look-around, on 150 NEW small,
partly hidden fires (R4 mock review, fix #1).  Built before anything is rendered.

  python3 scripts/make_protocol_w.py      # -> experiments/campaign_w_protocol.json  (seed W-2026, deterministic)

World distribution = campaign F/G/H (scripts/make_protocol_f.py `worlds`, make_protocol_h.py `world_spec`):
  * nominal scene, requested supply water or medicine (50/50), continuous random lighting, supplies moved +-0.06 m
    and rotated;
  * fire worlds (150): a SMALL fire (0.45-0.62 x the full model) straight behind the requested station
    (back 0.55-0.75 m, lateral +-0.15 m), so that it is mostly hidden by the supply at the front checkpoint;
  * fire-free twins (75): every second fire world again, same lighting, supplies, requested item and view poses, no fire.
Each world is rendered from three poses, exactly as the robot sees them in campaign G: the front checkpoint pose and the
two side poses 0.4 m to the left and right of the checkpoint waypoint, each facing the station
(scripts/fire_mask_at_pose.py DESIGN_POSE and --design-sides).  The robot does not reach a waypoint exactly, so every
view gets a small pose error drawn from the spread measured at the checkpoint in the 132 nominal closed-loop F/G/H runs
(std of ground-truth pose minus DESIGN_POSE: x 0.011 m, y 0.023 m, yaw 0.024 rad; truncated at 2.5 std).
"""
from __future__ import annotations
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind.robust_scenes import random_lighting  # noqa: E402

SEED = 'W-2026'
N_FIRE = 150
TWIN_EVERY = 2            # world k of the fire worlds has a twin if k % TWIN_EVERY == 0 -> 75 twins
SIDE_OFFSET_M = 0.4
POSE_SD = (0.011, 0.023, 0.024)        # x [m], y [m], yaw [rad]: arrival error of the closed-loop runs F/G/H
POSE_TRUNC_SD = 2.5
MIN_FIRE_PX = 614                      # a view shows the fire if >= 614 of 307 200 pixels (T1 amendment 2)
DESIGN_POSE = {'water': (1.03, 0.99, 0.769), 'medicine': (-1.03, 0.97, 2.388)}   # == fire_mask_at_pose.DESIGN_POSE
STATION_XY = {'water': (2.0, 2.0), 'medicine': (-2.0, 2.0)}
VIEWS = ('F', 'L', 'R')
VIEWS_EXTRA = ('L2', 'R2', 'N')     # Amendment 1 (I-20): suspicion-triggered extra views, secondary analysis only
EXTRA_SIDE_M, NEAR_M = 0.8, 0.3


def world_spec(rng, fire: bool, item: str) -> dict:
    """Same draw order and ranges as make_protocol_h.world_spec (campaign F/G/H fire geometry)."""
    spec = {'lighting_params': random_lighting(rng),
            'prop_offsets': {n: [round(rng.uniform(-.06, .06), 3), round(rng.uniform(-.06, .06), 3),
                                 round(rng.uniform(-math.pi, math.pi), 3)] for n in ('sealed_water_bottles', 'first_aid_case')}}
    if fire:
        spec['hazard_at'] = item
        spec['hazard_geom'] = [round(rng.uniform(.55, .75), 3), round(rng.uniform(-.15, .15), 3), round(rng.uniform(.45, .62), 3)]
    return spec


def nominal_views(item: str, offset: float = SIDE_OFFSET_M) -> dict:
    """Front waypoint pose and the two side poses (same geometry as fire_mask_at_pose --design-sides)."""
    x, y, yaw = DESIGN_POSE[item]
    sx, sy = STATION_XY[item]
    n = math.hypot(sx - x, sy - y)
    vx, vy = -(sy - y) / n, (sx - x) / n
    out = {'F': (x, y, yaw)}
    for side, k in (('L', -1), ('R', 1)):
        px, py = x + k * offset * vx, y + k * offset * vy
        out[side] = (px, py, math.atan2(sy - py, sx - px))
    return out


def _trunc_gauss(rng, sd: float) -> float:
    while True:
        z = rng.gauss(0.0, 1.0)
        if abs(z) <= POSE_TRUNC_SD:
            return z * sd


def extra_views(item: str) -> dict:
    """Amendment 1 (I-20): two wider side poses (+-0.8 m) and a closer front pose (0.3 m nearer the station)."""
    wide = nominal_views(item, EXTRA_SIDE_M)
    x, y, yaw = DESIGN_POSE[item]
    sx, sy = STATION_XY[item]
    n = math.hypot(sx - x, sy - y)
    near = (x + NEAR_M * (sx - x) / n, y + NEAR_M * (sy - y) / n, yaw)
    return {'L2': wide['L'], 'R2': wide['R'], 'N': near}


def jittered_extra_views(item: str, rng) -> dict:
    out = {}
    for v in VIEWS_EXTRA:
        x, y, yaw = extra_views(item)[v]
        out[v] = [round(x + _trunc_gauss(rng, POSE_SD[0]), 3), round(y + _trunc_gauss(rng, POSE_SD[1]), 3),
                  round(yaw + _trunc_gauss(rng, POSE_SD[2]), 3)]
    return out


def jittered_views(item: str, rng) -> dict:
    out = {}
    for v in VIEWS:                       # fixed order so the stream is stable
        x, y, yaw = nominal_views(item)[v]
        out[v] = [round(x + _trunc_gauss(rng, POSE_SD[0]), 3), round(y + _trunc_gauss(rng, POSE_SD[1]), 3),
                  round(yaw + _trunc_gauss(rng, POSE_SD[2]), 3)]
    return out


def build() -> dict:
    rng = random.Random(SEED)
    pose_rng = random.Random(SEED + '-poses')
    extra_rng = random.Random(SEED + '-extra-poses')      # separate stream: F/L/R poses and worlds are unchanged
    items = ['water', 'medicine'] * (N_FIRE // 2)
    rng.shuffle(items)
    worlds = []
    for k, item in enumerate(items):
        spec = world_spec(rng, True, item)
        views = jittered_views(item, pose_rng)
        views.update(jittered_extra_views(item, extra_rng))
        fid = f'wf{k:03d}'
        worlds.append({'id': fid, 'kind': 'fire', 'twin_of': None, 'item': item, 'scene': 'nominal',
                       'world_spec': spec, 'views': views})
        if k % TWIN_EVERY == 0:
            twin = {key: v for key, v in spec.items() if key not in ('hazard_at', 'hazard_geom')}
            worlds.append({'id': f'wt{k:03d}', 'kind': 'twin', 'twin_of': fid, 'item': item, 'scene': 'nominal',
                           'world_spec': json.loads(json.dumps(twin)), 'views': json.loads(json.dumps(views))})
    n_twin = sum(w['kind'] == 'twin' for w in worlds)
    return {'schema': 'rescuemind_study_w_protocol', 'seed': SEED, 'n_fire_worlds': N_FIRE, 'n_twin_worlds': n_twin,
            'planned_images': 3 * len(worlds), 'planned_extra_images': len(VIEWS_EXTRA) * len(worlds), 'side_offset_m': SIDE_OFFSET_M,
            'pose_error_sd': {'x_m': POSE_SD[0], 'y_m': POSE_SD[1], 'yaw_rad': POSE_SD[2], 'truncated_at_sd': POSE_TRUNC_SD},
            'min_fire_px': MIN_FIRE_PX, 'views': list(VIEWS), 'views_extra': list(VIEWS_EXTRA),
            'extra_views_m': {'side': EXTRA_SIDE_M, 'near': NEAR_M},
            'note': 'views[F|L|R] = [x, y, yaw] of the camera; F = front checkpoint, L/R = 0.4 m beside the waypoint facing the '
                    'station; twins share lighting, props, item and poses with their fire world; fire geometry '
                    '[back m, lateral m, scale] as in campaigns F/G/H',
            'worlds': worlds}


def main():
    out = ROOT / 'experiments/campaign_w_protocol.json'
    proto = build()
    if out.is_file() and json.loads(out.read_text()) != json.loads(json.dumps(proto, ensure_ascii=False)):
        sys.exit('registered protocol differs; refusing to overwrite')
    out.write_text(json.dumps(proto, ensure_ascii=False, indent=1) + '\n')
    print(proto['n_fire_worlds'], 'fire worlds,', proto['n_twin_worlds'], 'twins,', proto['planned_images'], 'images')


if __name__ == '__main__':
    main()
