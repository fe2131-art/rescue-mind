#!/usr/bin/env python3
"""Study JI image set (fork of build_testset_xd.py): the views of every world in experiments/campaign_ji_protocol.json (DRAFT, nothing rendered yet).

  python3 scripts/build_testset_ji.py --check          # counts only, no rendering
  python3 scripts/build_testset_ji.py --smoke          # one world per class, front view, colour + mask, contact sheet (no labels)
  python3 scripts/build_testset_ji.py --images         # colour images of all main and ablation worlds
  python3 scripts/build_testset_ji.py --fire-masks     # flat-magenta masks of the hazard worlds, same poses
  python3 scripts/build_testset_ji.py --labels         # labels.jsonl from the masks (no Gazebo needed)

Run inside the rm-next container via scripts/ji_run.sh (depot assets fetched, nothing else on Gazebo / the GPU).  Rendering
is resumable: a world whose files exist is skipped.  Labels (study W rule): fire or smoke pixels >= 614 -> visible, <= 20 ->
hidden, otherwise ambiguous.  A hazard world is *perceivable* if any of F, L, R is visible, *front-perceivable* if F is, and
*side-only* if only a side view is.  Particle smoke (visual only) is never in a mask: the labels count the static flame / smoke
geometry.  An ablation world that differs from its base only in lighting or in the particle plume re-uses the base world's masks.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import scripts.build_testset_t1 as t1  # noqa: E402

PROTOCOL = ROOT / 'experiments/campaign_ji_protocol.json'
OUT = ROOT / 'experiments/vlm_testset_ji'
VIEWS = ('F', 'L', 'R')
VIEWS_EXTRA = ('L2', 'R2', 'N')
MIN_FIRE_PX = 614
SAME_MASK_AS_BASE = ('default_light', 'no_particle_smoke')      # variants whose label geometry equals the base world's


def load_protocol(path: Path = PROTOCOL) -> dict:
    return json.loads(path.read_text())


def all_worlds(proto: dict) -> list:
    return list(proto['worlds']) + list(proto.get('ablation_worlds', []))


def all_views(w: dict) -> tuple:
    return VIEWS + tuple(v for v in VIEWS_EXTRA if v in w['views'])


def view_label(px: int) -> str:
    """hidden <= 20 px, visible >= 614 px (the threshold of the G/H/V/W design masks), otherwise ambiguous."""
    if px <= t1.MASK_HIDDEN_PX:
        return 'hidden'
    return 'visible' if px >= MIN_FIRE_PX else 'ambiguous'


def world_labels(px_by_view: dict) -> dict:
    vis = {v: view_label(p) for v, p in px_by_view.items()}
    return {'perceivable': any(px_by_view[v] >= MIN_FIRE_PX for v in VIEWS),
            'perceivable_any_view': any(p >= MIN_FIRE_PX for p in px_by_view.values()),
            'front_perceivable': px_by_view['F'] >= MIN_FIRE_PX,
            'side_only': px_by_view['F'] < MIN_FIRE_PX and any(px_by_view[v] >= MIN_FIRE_PX for v in ('L', 'R')),
            'view_visibility': vis, 'max_fire_pixels': max(px_by_view[v] for v in VIEWS)}


def image_name(world_id: str, view: str, ext: str = 'jpg') -> str:
    return f'{world_id}_{view}.{ext}'


def has_mask(w: dict) -> bool:
    return 'hazard_at' in w['world_spec']


def mask_world_id(w: dict) -> str:
    """The world whose mask files label `w`'s views (itself, or its base when the label geometry is identical)."""
    return w['ablation_base'] if w.get('variant') in SAME_MASK_AS_BASE else w['id']


def _world_kwargs(w: dict, mask: bool) -> dict:
    kw = json.loads(json.dumps(w['world_spec']))
    if 'hazard_geom' in kw:
        kw['hazard_geom'] = tuple(kw['hazard_geom'])
    if mask:
        kw['hazard_mask'] = True
    return kw


def world_sdf(w: dict, mask: bool = False) -> bytes:
    from rescuemind.robust_scenes import build_variant
    return build_variant(ROOT / f"worlds/scenarios/rescuemind_{w['scene']}.sdf", **_world_kwargs(w, mask))


def render(worlds: list, masks: bool, out_dir: Path, views=None, sheet_views=None):
    import os
    import signal
    import subprocess
    import time
    import numpy as np
    import rclpy
    from PIL import Image as PImage
    from sensor_msgs.msg import Image
    from rescuemind.ros_qos import image_qos
    img_dir = out_dir / ('fire_masks' if masks else 'images')
    img_dir.mkdir(parents=True, exist_ok=True)
    wdir = ROOT / 'worlds/testset_ji'
    wdir.mkdir(parents=True, exist_ok=True)
    rclpy.init()
    node = rclpy.create_node('rescuemind_testset_ji')
    latest = {'msg': None}
    node.create_subscription(Image, '/camera', lambda m: latest.__setitem__('msg', m), image_qos())
    ext = 'png' if masks else 'jpg'
    vs = lambda w: tuple(views) if views else all_views(w)
    todo = [w for w in worlds if (has_mask(w) or not masks) and (not masks or mask_world_id(w) == w['id'])
            and not all((img_dir / image_name(w['id'], v, ext)).is_file() for v in vs(w))]
    print(f'{len(todo)} of {len(worlds)} worlds to render ({"masks" if masks else "images"})', flush=True)
    for wi, w in enumerate(todo):
        world = wdir / f"rescuemind_{w['id']}{'_mask' if masks else ''}.sdf"
        world.write_bytes(world_sdf(w, masks))
        procs = [subprocess.Popen(['gz', 'sim', '-s', '-r', '--headless-rendering', '-v', '1', str(world)],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True),
                 subprocess.Popen(['bash', str(ROOT / 'scripts/bridge_direct_gazebo.sh')],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)]
        try:
            time.sleep(12)                                  # the depot world is larger than the arena (9 s there)
            for v in vs(w):
                t1.set_pose(*w['views'][v])
                latest['msg'] = None
                t0 = time.monotonic()
                while time.monotonic() - t0 < 2.0 or (latest['msg'] is None and time.monotonic() - t0 < 12):
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


def smoke_worlds(proto: dict) -> list:
    """One world per class (first of its class) plus one ablation world per variant: what the first look must cover."""
    seen, out = set(), []
    for w in proto['worlds']:
        if w['cls'] not in seen:
            seen.add(w['cls']); out.append(w)
    for w in proto.get('ablation_worlds', []):
        if w['variant'] not in seen and w['kind'] == 'hazard':
            seen.add(w['variant']); out.append(w)
    return out


def contact_sheet(out_dir: Path, worlds: list):
    from PIL import Image as PImage, ImageDraw
    cells = []
    for w in worlds:
        for sub, ext in (('images', 'jpg'), ('fire_masks', 'png')):
            f = out_dir / sub / image_name(w['id'], 'F', ext)
            if f.is_file():
                im = PImage.open(f).convert('RGB').resize((320, 240))
                ImageDraw.Draw(im).text((4, 4), f"{w.get('variant') or w['cls']} {sub[:3]}", fill=(255, 255, 0))
                cells.append(im)
    if cells:
        cols = 4
        sheet = PImage.new('RGB', (320 * cols, 240 * ((len(cells) + cols - 1) // cols)), 'white')
        for k, im in enumerate(cells):
            sheet.paste(im, ((k % cols) * 320, (k // cols) * 240))
        sheet.save(out_dir / 'smoke_sheet.jpg', quality=88)
    return len(cells)


def build_labels(proto: dict, out_dir: Path = OUT, pixels=None) -> list:
    """One row per image (the fields of the T1/T2/W label files that vlm_devset_eval.py needs, plus the depot factors).
    `pixels[(world_id, view)]` (tests) or the mask files give the fire/smoke pixel counts of hazard worlds."""
    rows = []
    for w in all_worlds(proto):
        px = None
        if has_mask(w):
            px = {}
            for v in all_views(w):
                mid = mask_world_id(w)
                if pixels is not None:
                    px[v] = pixels[(mid, v)]
                else:
                    f = out_dir / 'fire_masks' / image_name(mid, v, 'png')
                    if not f.is_file():
                        raise SystemExit(f'missing fire mask {f}')
                    px[v] = t1.fire_pixels(f)
            wl = world_labels(px)
        else:
            wl = {'perceivable': False, 'perceivable_any_view': False, 'front_perceivable': False, 'side_only': False,
                  'view_visibility': {v: 'hidden' for v in all_views(w)}, 'max_fire_pixels': 0}
        spec = w['world_spec']
        dep = spec['depot']
        for v in all_views(w):
            rows.append({'image': f'images/{image_name(w["id"], v)}', 'world_id': w['id'], 'world_kind': w['kind'], 'cls': w['cls'],
                         'size_class': w.get('size_class'), 'twin_of': w.get('twin_of'), 'split': w['split'], 'view': v,
                         'station': w['item'], 'depot_station': w['depot_station'], 'scene': 'nominal',
                         'truth_supply': w['truth_supply'], 'hazard_at': spec.get('hazard_at'),
                         'hazard_style': dep.get('hazard_style') or ('tongues' if 'hazard_at' in spec else None),
                         'particle_smoke': bool(dep.get('particle_smoke')), 'obstacle': bool(dep.get('obstacle')),
                         'distractor_kind': spec.get('distractor_kind'),
                         'ablation_base': w.get('ablation_base'), 'variant': w.get('variant'),
                         'fire_pixels': 0 if px is None else px[v],
                         'hazard_visibility': wl['view_visibility'][v], 'truth_hazard_visible': wl['view_visibility'][v] == 'visible',
                         'world_perceivable': wl['perceivable'], 'world_front_perceivable': wl['front_perceivable'],
                         'world_side_only': wl['side_only'], 'world_perceivable_any_view': wl['perceivable_any_view'],
                         'extra_view': v in VIEWS_EXTRA, 'pose': w['views'][v]})
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for flag in ('--images', '--fire-masks', '--labels', '--check', '--smoke'):
        ap.add_argument(flag, action='store_true')
    a = ap.parse_args(argv)
    proto = load_protocol()
    from scripts.make_protocol_ji import build
    if json.loads(json.dumps(build())) != proto:
        sys.exit('campaign_ji_protocol.json differs from the generator output')
    OUT.mkdir(parents=True, exist_ok=True)
    if a.check:
        print(len(proto['worlds']), 'main worlds', proto['planned_images'], 'images', proto['planned_extra_images'], 'extra',
              len(proto['ablation_worlds']), 'ablation worlds', proto['planned_ablation_images'], 'images')
        return
    if a.smoke:
        sw = smoke_worlds(proto)
        sm = OUT / 'smoke'
        render(sw, masks=False, out_dir=sm, views=('F',))
        render([w for w in sw if has_mask(w)], masks=True, out_dir=sm, views=('F',))
        print('sheet cells:', contact_sheet(sm, sw))
        return
    worlds = all_worlds(proto)
    if a.images:
        render(worlds, masks=False, out_dir=OUT)
    if a.fire_masks:
        render(worlds, masks=True, out_dir=OUT)
    if a.labels:
        rows = build_labels(proto)
        (OUT / 'labels.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
        haz = {r['world_id']: r for r in rows if r['world_kind'] == 'hazard'}
        print('rows', len(rows), 'hazard worlds', len(haz), 'perceivable', sum(r['world_perceivable'] for r in haz.values()),
              'front-perceivable', sum(r['world_front_perceivable'] for r in haz.values()),
              'side-only', sum(r['world_side_only'] for r in haz.values()))


if __name__ == '__main__':
    main()
