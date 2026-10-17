#!/usr/bin/env python3
"""Study W-a image set: 3 views (front, left, right) of every world in experiments/campaign_w_protocol.json.

  python3 scripts/build_testset_w.py --images        # colour images of all fire worlds and twins (no other stack running)
  python3 scripts/build_testset_w.py --fire-masks    # flat-magenta fire masks of the fire worlds, same poses
  python3 scripts/build_testset_w.py --labels        # labels.jsonl from the masks (no Gazebo needed)
  python3 scripts/build_testset_w.py --check         # counts only, no rendering

Run inside the rm-next container via scripts/w_render.sh.  Rendering is resumable: a world whose three files exist is skipped.
Labels (same rule as T1 amendment 2): fire pixels >= 614 -> visible, <= 20 -> hidden, otherwise ambiguous.  A fire world is
*perceivable* if any of its three views is visible; it is *front-perceivable* if the front view is.  Labels come from the
generator and the renders, never from a model.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import scripts.build_testset_t1 as t1  # noqa: E402

PROTOCOL = ROOT / 'experiments/campaign_w_protocol.json'
OUT = ROOT / 'experiments/vlm_testset_w'
VIEWS = ('F', 'L', 'R')
VIEWS_EXTRA = ('L2', 'R2', 'N')     # Amendment 1 (I-20): rendered too, used only by the secondary adaptive analysis
MIN_FIRE_PX = 614


def all_views(w: dict) -> tuple:
    return VIEWS + tuple(v for v in VIEWS_EXTRA if v in w['views'])


def load_protocol(path: Path = PROTOCOL) -> dict:
    return json.loads(path.read_text())


def view_label(px: int) -> str:
    """hidden <= 20 px, visible >= 614 px (the threshold of the G/H/V design masks), otherwise ambiguous.  (t1.mask_label
    needs >= 614.4, i.e. 615 px; the two differ for exactly 614 px, so the W rule is written out here.)"""
    if px <= t1.MASK_HIDDEN_PX:
        return 'hidden'
    return 'visible' if px >= MIN_FIRE_PX else 'ambiguous'


def world_labels(px_by_view: dict) -> dict:
    """World-level label from the three mask pixel counts."""
    vis = {v: view_label(px_by_view[v]) for v in VIEWS}
    vis.update({v: view_label(px_by_view[v]) for v in VIEWS_EXTRA if v in px_by_view})
    return {'perceivable': any(px_by_view[v] >= MIN_FIRE_PX for v in VIEWS),
            'perceivable_any_view': any(p >= MIN_FIRE_PX for p in px_by_view.values()),
            'front_perceivable': px_by_view['F'] >= MIN_FIRE_PX,
            'side_only': px_by_view['F'] < MIN_FIRE_PX and any(px_by_view[v] >= MIN_FIRE_PX for v in ('L', 'R')),
            'view_visibility': vis, 'max_fire_pixels': max(px_by_view[v] for v in VIEWS)}


def image_name(world_id: str, view: str, ext: str = 'jpg') -> str:
    return f'{world_id}_{view}.{ext}'


def _world_kwargs(w: dict, mask: bool) -> dict:
    kw = dict(w['world_spec'])
    if 'hazard_geom' in kw:
        kw['hazard_geom'] = tuple(kw['hazard_geom'])
    if mask:
        kw['hazard_mask'] = True
    return kw


def render(worlds: list, masks: bool):
    import os
    import signal
    import subprocess
    import time
    import numpy as np
    import rclpy
    from PIL import Image as PImage
    from sensor_msgs.msg import Image
    from rescuemind.robust_scenes import build_variant
    from rescuemind.ros_qos import image_qos
    img_dir = OUT / ('fire_masks' if masks else 'images')
    img_dir.mkdir(parents=True, exist_ok=True)
    wdir = ROOT / 'worlds/testset_w'
    wdir.mkdir(parents=True, exist_ok=True)
    rclpy.init()
    node = rclpy.create_node('rescuemind_testset_w')
    latest = {'msg': None}
    node.create_subscription(Image, '/camera', lambda m: latest.__setitem__('msg', m), image_qos())
    ext = 'png' if masks else 'jpg'
    todo = [w for w in worlds if (w['kind'] == 'fire' or not masks)
            and not all((img_dir / image_name(w['id'], v, ext)).is_file() for v in all_views(w))]
    print(f'{len(todo)} of {len(worlds)} worlds to render ({"masks" if masks else "images"})', flush=True)
    for wi, w in enumerate(todo):
        world = wdir / f"rescuemind_{w['id']}{'_mask' if masks else ''}.sdf"
        world.write_bytes(build_variant(ROOT / f"worlds/scenarios/rescuemind_{w['scene']}.sdf", **_world_kwargs(w, masks)))
        procs = [subprocess.Popen(['gz', 'sim', '-s', '-r', '--headless-rendering', '-v', '1', str(world)],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True),
                 subprocess.Popen(['bash', str(ROOT / 'scripts/bridge_direct_gazebo.sh')],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)]
        try:
            time.sleep(9)
            for v in all_views(w):
                t1.set_pose(*w['views'][v])
                latest['msg'] = None
                t0 = time.monotonic()
                while time.monotonic() - t0 < 1.6 or (latest['msg'] is None and time.monotonic() - t0 < 10):
                    rclpy.spin_once(node, timeout_sec=0.05)
                m = latest['msg']
                if m is None:
                    raise RuntimeError(f"no camera frame for {w['id']} {v}")
                arr = np.frombuffer(bytes(m.data), np.uint8).reshape(m.height, m.width, 3)
                path = img_dir / image_name(w['id'], v, ext)
                if masks:
                    PImage.fromarray(arr).save(path)
                else:
                    PImage.fromarray(arr).save(path, quality=90)
            print(f'[{wi + 1}/{len(todo)}] {w["id"]}', flush=True)
        finally:
            for p in procs:
                for sig in (signal.SIGINT, signal.SIGKILL):
                    try:
                        os.killpg(p.pid, sig); p.wait(timeout=6); break
                    except Exception:
                        continue
            time.sleep(2)
    node.destroy_node(); rclpy.shutdown()


def build_labels(proto: dict, out_dir: Path = OUT, pixels=None) -> list:
    """One row per image (same fields as the T1/T2 label files where they apply, so vlm_devset_eval.py can score it)."""
    rows = []
    for w in proto['worlds']:
        px = None
        if w['kind'] == 'fire':
            px = {}
            for v in all_views(w):
                if pixels is not None:
                    px[v] = pixels[(w['id'], v)]
                else:
                    f = out_dir / 'fire_masks' / image_name(w['id'], v, 'png')
                    if not f.is_file():
                        raise SystemExit(f'missing fire mask {f}')
                    px[v] = t1.fire_pixels(f)
            wl = world_labels(px)
        else:
            wl = {'perceivable': False, 'perceivable_any_view': False, 'front_perceivable': False, 'side_only': False,
                  'view_visibility': {v: 'hidden' for v in all_views(w)}, 'max_fire_pixels': 0}
        for v in all_views(w):
            rows.append({'image': f'images/{image_name(w["id"], v)}', 'world_id': w['id'], 'world_kind': w['kind'],
                         'twin_of': w['twin_of'], 'view': v, 'station': w['item'], 'scene': 'nominal',
                         'truth_supply': w['item'], 'hazard_at': w['world_spec'].get('hazard_at'),
                         'fire_pixels': 0 if px is None else px[v],
                         'hazard_visibility': wl['view_visibility'][v], 'truth_hazard_visible': wl['view_visibility'][v] == 'visible',
                         'world_perceivable': wl['perceivable'], 'world_front_perceivable': wl['front_perceivable'],
                         'world_side_only': wl['side_only'], 'world_perceivable_any_view': wl['perceivable_any_view'],
                         'extra_view': v in VIEWS_EXTRA, 'pose': w['views'][v]})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--images', action='store_true')
    ap.add_argument('--fire-masks', action='store_true')
    ap.add_argument('--labels', action='store_true')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    proto = load_protocol()
    from scripts.make_protocol_w import build
    if json.loads(json.dumps(build())) != proto:
        sys.exit('campaign_w_protocol.json differs from the generator output')
    OUT.mkdir(parents=True, exist_ok=True)
    if a.check:
        print(len(proto['worlds']), 'worlds', proto['planned_images'], 'images'); return
    if a.images:
        render(proto['worlds'], masks=False)
    if a.fire_masks:
        render(proto['worlds'], masks=True)
    if a.labels:
        rows = build_labels(proto)
        (OUT / 'labels.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
        fire = [w for w in {r['world_id']: r for r in rows}.values() if w['world_kind'] == 'fire']
        print('rows', len(rows), 'fire worlds', len(fire), 'perceivable', sum(w['world_perceivable'] for w in fire),
              'front-perceivable', sum(w['world_front_perceivable'] for w in fire), 'side-only', sum(w['world_side_only'] for w in fire))


if __name__ == '__main__':
    main()
