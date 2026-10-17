#!/usr/bin/env python3
"""I-21 preview: render the depot worlds from the checkpoint views (inside rm-next, nothing else on Gazebo).
   python3 scripts/depot_preview.py   -> docs/figures/depot_preview_*.jpg  (and a contact sheet)"""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image as PImage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import scripts.build_testset_t1 as t1  # noqa: E402
from rescuemind.robust_scenes import build_variant  # noqa: E402
from rescuemind.ros_qos import image_qos  # noqa: E402

OUT = ROOT / 'docs/figures'
CASES = [('nominal', {'depot': {'seed': 1}}),
         ('fire_smoke', {'depot': {'seed': 2, 'particle_smoke': True}, 'hazard_at': 'water', 'hazard_geom': (0.6, 0.0, 0.6)}),
         ('obstacle_dim', {'depot': {'seed': 3, 'obstacle': True}, 'lighting': 'dim_evening'})]
VIEWS = {'front_water': (1.03, 0.99, 0.769), 'front_medicine': (-1.03, 0.97, 2.388), 'start': (0.0, -0.3, 1.5708)}


def main():
    import rclpy
    from sensor_msgs.msg import Image
    rclpy.init()
    node = rclpy.create_node('rescuemind_depot_preview')
    latest = {'msg': None}
    node.create_subscription(Image, '/camera', lambda m: latest.__setitem__('msg', m), image_qos())
    wdir = Path('/tmp/depot_preview'); wdir.mkdir(exist_ok=True)
    shots = []
    for name, kw in CASES:
        world = wdir / f'depot_{name}.sdf'
        world.write_bytes(build_variant(ROOT / 'worlds/scenarios/rescuemind_nominal.sdf', **kw))
        procs = [subprocess.Popen(['gz', 'sim', '-s', '-r', '--headless-rendering', '-v', '1', str(world)],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True),
                 subprocess.Popen(['bash', str(ROOT / 'scripts/bridge_direct_gazebo.sh')],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)]
        try:
            time.sleep(14)
            for v, pose in VIEWS.items():
                t1.set_pose(*pose)
                latest['msg'] = None
                t0 = time.monotonic()
                while time.monotonic() - t0 < 2.5 or (latest['msg'] is None and time.monotonic() - t0 < 15):
                    rclpy.spin_once(node, timeout_sec=0.05)
                m = latest['msg']
                if m is None:
                    print('no frame', name, v, flush=True); continue
                arr = np.frombuffer(bytes(m.data), np.uint8).reshape(m.height, m.width, 3)
                p = OUT / f'depot_preview_{name}_{v}.jpg'
                PImage.fromarray(arr).save(p, quality=88)
                shots.append(p); print('wrote', p, flush=True)
        finally:
            for pr in procs:
                for sig in (signal.SIGINT, signal.SIGKILL):
                    try:
                        os.killpg(pr.pid, sig); pr.wait(timeout=6); break
                    except Exception:
                        continue
            time.sleep(2)
    if shots:
        ims = [PImage.open(p).resize((320, 240)) for p in shots]
        cols = 3
        sheet = PImage.new('RGB', (320 * cols, 240 * ((len(ims) + cols - 1) // cols)), 'white')
        for k, im in enumerate(ims):
            sheet.paste(im, ((k % cols) * 320, (k // cols) * 240))
        sheet.save(OUT / 'depot_preview_sheet.jpg', quality=88)
    node.destroy_node(); rclpy.shutdown()
    print(json.dumps({'shots': [str(s) for s in shots]}))


if __name__ == '__main__':
    main()
