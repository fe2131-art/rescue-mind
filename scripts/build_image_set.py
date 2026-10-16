#!/usr/bin/env python3
"""Render a labelled checkpoint image set from a seeded world spec (generalises build_testset_t1.py).

  python3 scripts/build_image_set.py --set dh --spec-only     # hazard DEVELOPMENT set (I-11), seed DH-2026
  python3 scripts/build_image_set.py --set dh                 # render images + fire masks + labels
  python3 scripts/build_image_set.py --set t2                 # held-out TEST set T2 (same distribution as T1, seed T2-2026)

Every set uses the T1 labelling rules: supply truth from the scene, fire visibility from a flat-magenta
re-render of the fire (occlusion-aware, T1 amendment 2), expected = allow / deny / ambiguous.
Run inside the container with no other Gazebo stack running.
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
import scripts.build_testset_t1 as t1  # noqa: E402
from rescuemind.robust_scenes import (STATIONS, build_variant, hazard_xy, platform_side_offset,  # noqa: E402
                                      random_lighting)

OTHER = {'water': 'medicine', 'medicine': 'water'}


def dh_spec(seed: str = 'DH-2026') -> list[dict]:
    """Hazard development set: many partly hidden fires plus fire-free confusers (cone, crate, box)."""
    rng = random.Random(seed)
    strata = ([('nominal', 'fire')] * 14 + [('swapped', 'fire')] * 3 + [('empty', 'fire')] * 3 +
              [('nominal', 'cone')] * 4 + [('nominal', 'crate')] * 2 + [('empty', 'crate')] * 2 + [('nominal', 'box')] * 2)
    rng.shuffle(strata)
    worlds = []
    for i, (scene, cond) in enumerate(strata):
        w = {'id': f'dh_{i:02d}', 'scene': scene, 'lighting_params': random_lighting(rng),
             'prop_offsets': {n: [round(rng.uniform(-.15, .15), 3), round(rng.uniform(-.15, .15), 3),
                                  round(rng.uniform(-math.pi, math.pi), 3)] for n in ('sealed_water_bottles', 'first_aid_case')}}
        if cond == 'fire':
            w['hazard_at'] = rng.choice(sorted(STATIONS))
            # wider than T1 on purpose: fires straight behind the supply (occluded) are the failure mode
            w['hazard_geom'] = [round(rng.uniform(.6, 1.1), 3), round(rng.uniform(-.8, .8), 3)]
        elif cond:
            st = rng.choice(sorted(STATIONS))
            w.update(distractor_at=st, distractor_kind=cond, distractor_side=rng.choice([-1.0, 1.0]),
                     distractor_layout='platform')
            if scene != 'empty':
                prop = t1.PROP[st] if scene == 'nominal' else t1.PROP[OTHER[st]]
                ox, oy = platform_side_offset(st, -w['distractor_side'], 0.10)
                w['prop_offsets'][prop][:2] = [round(ox + rng.uniform(-.04, .04), 3), round(oy + rng.uniform(-.04, .04), 3)]
        w['views'] = {}
        for station, (sx, sy) in sorted(STATIONS.items()):
            keep_out = [hazard_xy(station, *w['hazard_geom'][:2])] if w.get('hazard_at') == station else []
            views = []
            while len(views) < 5:
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


def dh2_spec(seed: str = 'DH2-2026') -> list[dict]:
    """Hazard development set 2: SMALL early-stage fires (0.40-0.70 x) straight behind the supply, the size range
    where T1 showed misses.  DH turned out to contain only 4 visible fires below 10 000 px (I-13 log)."""
    rng = random.Random(seed)
    strata = [('nominal', 'fire')] * 20 + [('swapped', 'fire')] * 2 + [('empty', 'fire')] * 2 + \
             [('nominal', 'cone')] * 3 + [('nominal', 'crate')] * 1 + [('empty', 'crate')] * 2
    rng.shuffle(strata)
    worlds = dh_spec(seed + '-base')[:len(strata)]
    out = []
    for i, ((scene, cond), w) in enumerate(zip(strata, worlds)):
        w = {k: v for k, v in w.items() if k not in ('hazard_at', 'hazard_geom', 'distractor_at', 'distractor_kind',
                                                      'distractor_side', 'distractor_layout')}
        w['id'] = f'dh2_{i:02d}'; w['scene'] = scene
        if cond == 'fire':
            w['hazard_at'] = rng.choice(sorted(STATIONS))
            w['hazard_geom'] = [round(rng.uniform(.55, .80), 3), round(rng.uniform(-.30, .30), 3), round(rng.uniform(.40, .70), 3)]
        else:
            st = rng.choice(sorted(STATIONS))
            w.update(distractor_at=st, distractor_kind=cond, distractor_side=rng.choice([-1.0, 1.0]), distractor_layout='platform')
            if scene != 'empty':
                prop = t1.PROP[st]
                ox, oy = platform_side_offset(st, -w['distractor_side'], 0.10)
                w['prop_offsets'][prop][:2] = [round(ox + rng.uniform(-.04, .04), 3), round(oy + rng.uniform(-.04, .04), 3)]
        w['views'] = {}
        for station, (sx, sy) in sorted(STATIONS.items()):
            keep_out = [hazard_xy(station, *w['hazard_geom'][:2])] if w.get('hazard_at') == station else []
            views = []
            while len(views) < 5:
                dist = rng.uniform(0.9, 1.8)
                bearing = math.atan2(-sy, -sx) + rng.uniform(-0.6, 0.6)
                x, y = sx + dist * math.cos(bearing), sy + dist * math.sin(bearing)
                if any(math.hypot(x - kx, y - ky) < 0.55 for kx, ky in keep_out):
                    continue
                yaw = math.atan2(sy - y, sx - x) + rng.uniform(-0.12, 0.12)
                views.append([round(x, 3), round(y, 3), round(yaw, 3), round(dist, 3)])
            w['views'][station] = views
        out.append(w)
    return out


SETS = {
    'dh': dict(out='experiments/vlm_devset_hazard', spec=lambda: dh_spec('DH-2026'), role='development'),
    'dh2': dict(out='experiments/vlm_devset_hazard2', spec=lambda: dh2_spec('DH2-2026'), role='development'),
    't2': dict(out='experiments/vlm_testset_t2', role='held-out test',
               spec=lambda: [dict(w, id=w['id'].replace('t1_', 't2_')) for w in t1.make_spec('T2-2026')]),
}


def set_pose(x, y, yaw):
    t1.set_pose(x, y, yaw)


def render(spec: list[dict], out: Path, masks: bool):
    import numpy as np
    import rclpy
    from PIL import Image as PImage
    from sensor_msgs.msg import Image
    from rescuemind.ros_qos import image_qos
    img_dir = out / ('fire_masks' if masks else 'images')
    img_dir.mkdir(parents=True, exist_ok=True)
    wdir = ROOT / 'worlds' / out.name
    wdir.mkdir(parents=True, exist_ok=True)
    rows = []
    rclpy.init()
    node = rclpy.create_node('rescuemind_image_set')
    latest = {'msg': None}
    node.create_subscription(Image, '/camera', lambda m: latest.__setitem__('msg', m), image_qos())
    todo = [w for w in spec if w.get('hazard_at')] if masks else spec
    for wi, w in enumerate(todo):
        world = wdir / f"rescuemind_{w['id']}{'_mask' if masks else ''}.sdf"
        kw = {k: w[k] for k in ('lighting_params', 'prop_offsets', 'hazard_at', 'distractor_at', 'distractor_kind',
                                'distractor_side', 'distractor_layout') if k in w}
        if 'hazard_geom' in w:
            kw['hazard_geom'] = tuple(w['hazard_geom'])
        if masks:
            kw['hazard_mask'] = True
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
                    name = f"{w['id']}_{station}_{k}"
                    if masks:
                        PImage.fromarray(arr).save(img_dir / f'{name}.png')
                        continue
                    PImage.fromarray(arr).save(img_dir / f'{name}.jpg', quality=90)
                    rows.append({'image': f'images/{name}.jpg', 'world_id': w['id'], 'station': station, 'scene': w['scene'],
                                 'hazard_at': w.get('hazard_at'), 'distractor_at': w.get('distractor_at'),
                                 'distractor_kind': w.get('distractor_kind'),
                                 # geometric pre-label only (replaced by the mask label); size scale is not geometry
                                 **t1.labels_for(dict(w, hazard_geom=w['hazard_geom'][:2]) if 'hazard_geom' in w else w,
                                                 station, view),
                                 'pose': view[:3], 'distance_m': view[3]})
            print(f'[{wi + 1}/{len(todo)}] {w["id"]} {w["scene"]}{" mask" if masks else ""}', flush=True)
        finally:
            for p in procs:
                for sig in (signal.SIGINT, signal.SIGKILL):
                    try:
                        os.killpg(p.pid, sig); p.wait(timeout=6); break
                    except Exception:
                        continue
            time.sleep(2)
    node.destroy_node(); rclpy.shutdown()
    if not masks:
        (out / 'labels.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))


def relabel(out: Path):
    rows = [json.loads(x) for x in (out / 'labels.jsonl').read_text().splitlines()]
    for r in rows:
        r.setdefault('hazard_visibility_geometric', r['hazard_visibility'])
        mask = out / 'fire_masks' / Path(r['image']).name.replace('.jpg', '.png')
        if r.get('hazard_at') and not mask.is_file():
            raise SystemExit(f'missing fire mask for {r["image"]}')
        px = t1.fire_pixels(mask) if mask.is_file() else 0
        r['fire_pixels'] = px
        r['hazard_visibility'] = t1.mask_label(px)
        r['truth_hazard_visible'] = r['hazard_visibility'] == 'visible'
        ok = r['truth_supply'] == r['station']
        r['expected'] = ('ambiguous' if ok and r['hazard_visibility'] == 'ambiguous' else
                         'allow' if ok and r['hazard_visibility'] == 'hidden' else 'deny')
    (out / 'labels.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    from collections import Counter
    print('expected', dict(Counter(r['expected'] for r in rows)), 'fire', dict(Counter(r['hazard_visibility'] for r in rows)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--set', choices=sorted(SETS), required=True)
    ap.add_argument('--spec-only', action='store_true')
    a = ap.parse_args()
    cfg = SETS[a.set]
    out = ROOT / cfg['out']
    out.mkdir(parents=True, exist_ok=True)
    spec = cfg['spec']()
    sp = out / 'spec.json'
    if sp.is_file() and json.loads(sp.read_text()) != json.loads(json.dumps(spec)):
        sys.exit('spec.json differs from the generator output; refusing to overwrite a registered spec')
    sp.write_text(json.dumps(spec, indent=1) + '\n')
    print(a.set, cfg['role'], 'worlds', len(spec), 'images', sum(len(v) for w in spec for v in w['views'].values()))
    if a.spec_only:
        return
    render(spec, out, masks=False)
    render(spec, out, masks=True)
    relabel(out)


if __name__ == '__main__':
    main()
