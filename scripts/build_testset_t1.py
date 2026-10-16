#!/usr/bin/env python3
"""Paper test set T1: continuously randomised Gazebo images, held out from all development.

  python3 scripts/build_testset_t1.py --spec-only   # write experiments/vlm_testset_t1/spec.json
  python3 scripts/build_testset_t1.py               # render images + labels.jsonl (no other stack running)

60 worlds (24 nominal / 18 swapped / 18 empty) x 2 stations x 5 viewpoints = 600 images.
Factors drawn from seed 'T1-2026' (see experiments/PREREGISTRATION_T1.md):
  * lighting   : continuous sun azimuth/elevation, intensity, ambient level, warm/cool tint
  * props      : each supply moved +-0.15 m on its platform and rotated freely
  * fire       : 16 worlds (10 nominal), random station, random position behind the platform
  * distractor : 27 worlds, cardboard box (seen in dev) / blue crate / orange traffic cone (both new),
                 standing on the platform beside the supply (alone and centred on an empty platform)
  * viewpoint  : 0.8-1.9 m, bearing +-0.75 rad around the approach direction, yaw jitter +-0.15 rad
Labels come from the generator (never from a model).  The fire label is three-way
(visible / hidden / ambiguous) from the image geometry; see hazard_visibility().
"""
from __future__ import annotations
import argparse
import json
import math
import os
import random
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind.robust_scenes import (STATIONS, build_variant, hazard_visibility, hazard_xy,  # noqa: E402
                                      platform_side_offset, random_lighting, truth_for)

PROP = {'water': 'sealed_water_bottles', 'medicine': 'first_aid_case'}

SEED = 'T1-2026'
OUT = ROOT / 'experiments/vlm_testset_t1'
VIEWS = 5


def make_spec(seed: str = SEED) -> list[dict]:
    rng = random.Random(seed)
    # strata (scene, condition): fire is concentrated on nominal worlds, where only the hazard
    # question can prevent an approval; the cone (orange, not fire) too, where it could cause
    # a false hazard alarm; the crate mostly on empty platforms, where it could be mistaken for a supply
    strata = ([('nominal', 'fire')] * 10 + [('nominal', 'cone')] * 5 + [('nominal', 'box')] * 2 +
              [('nominal', 'crate')] * 2 + [('nominal', None)] * 5 +
              [('swapped', 'fire')] * 3 + [('swapped', 'box')] * 2 + [('swapped', 'crate')] * 2 + [('swapped', None)] * 11 +
              [('empty', 'fire')] * 3 + [('empty', 'box')] * 4 + [('empty', 'crate')] * 5 + [('empty', None)] * 6)
    rng.shuffle(strata)
    worlds = []
    for i, (scene, cond) in enumerate(strata):
        fire, distract = cond == 'fire', (cond if cond in ('box', 'crate', 'cone') else None)
        w = {'id': f't1_{i:02d}', 'scene': scene, 'lighting_params': random_lighting(rng),
             'prop_offsets': {name: [round(rng.uniform(-.15, .15), 3), round(rng.uniform(-.15, .15), 3),
                                     round(rng.uniform(-math.pi, math.pi), 3)]
                              for name in ('sealed_water_bottles', 'first_aid_case')}}
        if fire:
            w['hazard_at'] = rng.choice(sorted(STATIONS))
            w['hazard_geom'] = [round(rng.uniform(.75, 1.10), 3), round(rng.uniform(-.8, .8), 3)]
        if distract:
            st = rng.choice(sorted(STATIONS))
            w['distractor_at'] = st
            w['distractor_kind'] = distract
            w['distractor_side'] = rng.choice([-1.0, 1.0])
            # amendment 1: the distractor stands on the platform beside the supply (campaign-E layout);
            # the supply on that platform is kept on the other half
            w['distractor_layout'] = 'platform'
            if scene != 'empty':
                other = {'water': 'medicine', 'medicine': 'water'}
                prop = PROP[st] if scene == 'nominal' else PROP[other[st]]
                ox, oy = platform_side_offset(st, -w['distractor_side'], 0.10)
                w['prop_offsets'][prop][:2] = [round(ox + rng.uniform(-.04, .04), 3), round(oy + rng.uniform(-.04, .04), 3)]
        w['views'] = {}
        for station, (sx, sy) in sorted(STATIONS.items()):
            keep_out = []
            if w.get('hazard_at') == station:
                keep_out.append(hazard_xy(station, *w['hazard_geom']))
            views = []
            while len(views) < VIEWS:
                dist = rng.uniform(0.8, 1.9)
                bearing = math.atan2(-sy, -sx) + rng.uniform(-0.75, 0.75)
                x, y = sx + dist * math.cos(bearing), sy + dist * math.sin(bearing)
                if any(math.hypot(x - kx, y - ky) < 0.55 for kx, ky in keep_out):
                    continue
                yaw = math.atan2(sy - y, sx - x) + rng.uniform(-0.15, 0.15)
                views.append([round(x, 3), round(y, 3), round(yaw, 3), round(dist, 3)])
            w['views'][station] = views
        worlds.append(w)
    return worlds


def labels_for(w: dict, station: str, view: list) -> dict:
    x, y, yaw, dist = view
    truth = truth_for(w['scene'], station, hazard_at=w.get('hazard_at'))
    hpos = hazard_xy(station, *w['hazard_geom']) if w.get('hazard_at') == station else None
    vis = hazard_visibility(station, w.get('hazard_at'), (x, y), yaw, hpos)
    supply_ok = truth['truth_supply'] == station
    expected = ('ambiguous' if supply_ok and vis == 'ambiguous' else
                'allow' if supply_ok and vis == 'hidden' else 'deny')
    return {**truth, 'hazard_visibility': vis, 'truth_hazard_visible': vis == 'visible', 'expected': expected}


def set_pose(x, y, yaw):
    req = (f'name: "rescue_diffbot" position {{x: {x:.4f} y: {y:.4f} z: 0.16}} '
           f'orientation {{z: {math.sin(yaw / 2):.6f} w: {math.cos(yaw / 2):.6f}}}')
    subprocess.run(['gz', 'service', '-s', '/world/rescuemind_arena/set_pose', '--reqtype', 'gz.msgs.Pose',
                    '--reptype', 'gz.msgs.Boolean', '--timeout', '3000', '--req', req], check=True, capture_output=True)


def render(spec: list[dict]):
    import numpy as np
    import rclpy
    from PIL import Image as PImage
    from sensor_msgs.msg import Image
    from rescuemind.ros_qos import image_qos
    (OUT / 'images').mkdir(parents=True, exist_ok=True)
    wdir = ROOT / 'worlds/testset_t1'
    wdir.mkdir(parents=True, exist_ok=True)
    rows = []
    rclpy.init()
    node = rclpy.create_node('rescuemind_testset_t1')
    latest = {'msg': None}
    node.create_subscription(Image, '/camera', lambda m: latest.__setitem__('msg', m), image_qos())
    for wi, w in enumerate(spec):
        world = wdir / f"rescuemind_{w['id']}.sdf"
        kw = {k: w[k] for k in ('lighting_params', 'prop_offsets', 'hazard_at', 'distractor_at',
                                'distractor_kind', 'distractor_side', 'distractor_layout') if k in w}
        if 'hazard_geom' in w:
            kw['hazard_geom'] = tuple(w['hazard_geom'])
        world.write_bytes(build_variant(ROOT / f"worlds/scenarios/rescuemind_{w['scene']}.sdf", **kw))
        procs = [subprocess.Popen(['gz', 'sim', '-s', '-r', '--headless-rendering', '-v', '1', str(world)],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True),
                 subprocess.Popen(['bash', str(ROOT / 'scripts/bridge_direct_gazebo.sh')],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)]
        try:
            time.sleep(9)
            for station in sorted(STATIONS):
                for k, view in enumerate(w['views'][station]):
                    set_pose(*view[:3])
                    latest['msg'] = None
                    t0 = time.monotonic()
                    while time.monotonic() - t0 < 1.6 or (latest['msg'] is None and time.monotonic() - t0 < 10):
                        rclpy.spin_once(node, timeout_sec=0.05)
                    m = latest['msg']
                    arr = np.frombuffer(bytes(m.data), np.uint8).reshape(m.height, m.width, 3)
                    name = f"{w['id']}_{station}_{k}.jpg"
                    PImage.fromarray(arr).save(OUT / 'images' / name, quality=90)
                    rows.append({'image': f'images/{name}', 'world_id': w['id'], 'station': station, 'scene': w['scene'],
                                 'hazard_at': w.get('hazard_at'), 'distractor_at': w.get('distractor_at'),
                                 'distractor_kind': w.get('distractor_kind'), **labels_for(w, station, view),
                                 'pose': view[:3], 'distance_m': view[3]})
            print(f'[{wi + 1}/{len(spec)}] {w["id"]} {w["scene"]}', flush=True)
        finally:
            for p in procs:
                for sig in (signal.SIGINT, signal.SIGKILL):
                    try:
                        os.killpg(p.pid, sig); p.wait(timeout=6); break
                    except Exception:
                        continue
            time.sleep(2)
    (OUT / 'labels.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    print('images', len(rows))
    node.destroy_node(); rclpy.shutdown()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--spec-only', action='store_true')
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    spec = make_spec()
    sp = OUT / 'spec.json'
    if sp.is_file() and json.loads(sp.read_text()) != spec:
        sys.exit('spec.json differs from the generator output; refusing to overwrite a registered spec')
    sp.write_text(json.dumps(spec, indent=1) + '\n')
    counts = {}
    for w in spec:
        for st in STATIONS:
            for v in w['views'][st]:
                e = labels_for(w, st, v)['expected']
                counts[e] = counts.get(e, 0) + 1
    print('worlds', len(spec), 'expected labels', counts)
    if not a.spec_only:
        render(spec)


if __name__ == '__main__':
    main()
