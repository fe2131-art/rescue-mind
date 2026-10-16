#!/usr/bin/env python3
"""I-05: capture the domain-randomised VLM development set (dev v2).

16 worlds (3 lightings x 3 scenes, 4 distractor worlds, 3 hazard worlds) x 2 stations
x 4 randomised viewpoints (seed 11, wider jitter than dev v1).  Images + labels go to
experiments/vlm_devset_v2/.  Development data only; the closed-loop evaluation is separate.
Run inside docker/run.sh with no other stack running.
"""
from __future__ import annotations
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
from rescuemind.robust_scenes import STATIONS, hazard_visible, truth_for, write_variant  # noqa: E402
from rescuemind.ros_qos import image_qos  # noqa: E402

VARIANTS = ([dict(scene=s, lighting=l) for l in ('default', 'dim_evening', 'harsh_noon')
             for s in ('nominal', 'swapped', 'empty')] +
            [dict(scene='empty', lighting='default', distractor_at='water'),
             dict(scene='empty', lighting='default', distractor_at='medicine'),
             dict(scene='nominal', lighting='default', distractor_at='water'),
             dict(scene='nominal', lighting='default', distractor_at='medicine'),
             dict(scene='nominal', lighting='default', hazard_at='water'),
             dict(scene='nominal', lighting='default', hazard_at='medicine'),
             dict(scene='swapped', lighting='dim_evening', hazard_at='water')])


def set_pose(x, y, yaw):
    req = (f'name: "rescue_diffbot" position {{x: {x:.4f} y: {y:.4f} z: 0.16}} '
           f'orientation {{z: {math.sin(yaw / 2):.6f} w: {math.cos(yaw / 2):.6f}}}')
    subprocess.run(['gz', 'service', '-s', '/world/rescuemind_arena/set_pose', '--reqtype', 'gz.msgs.Pose',
                    '--reptype', 'gz.msgs.Boolean', '--timeout', '3000', '--req', req], check=True, capture_output=True)


def main():
    import numpy as np
    import rclpy
    from PIL import Image as PImage
    from sensor_msgs.msg import Image
    out = ROOT / 'experiments/vlm_devset_v2'
    (out / 'images').mkdir(parents=True, exist_ok=True)
    worlds = ROOT / 'worlds/robustness'
    rows = []
    rclpy.init()
    node = rclpy.create_node('rescuemind_devset_v2')
    latest = {'msg': None}
    node.create_subscription(Image, '/camera', lambda m: latest.__setitem__('msg', m), image_qos())
    for vi, var in enumerate(VARIANTS):
        world = write_variant(ROOT / 'worlds/scenarios', worlds, **var)
        procs = [subprocess.Popen(['gz', 'sim', '-s', '-r', '--headless-rendering', '-v', '1', str(world)],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True),
                 subprocess.Popen(['bash', str(ROOT / 'scripts/bridge_direct_gazebo.sh')],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)]
        try:
            time.sleep(9)
            rng = random.Random(f'11-{world.stem}')
            for station, (sx, sy) in STATIONS.items():
                for k in range(4):
                    dist = rng.uniform(0.9, 1.7)
                    bearing = math.atan2(-sy, -sx) + rng.uniform(-0.6, 0.6)
                    x, y = sx + dist * math.cos(bearing), sy + dist * math.sin(bearing)
                    yaw = math.atan2(sy - y, sx - x) + rng.uniform(-0.12, 0.12)
                    set_pose(x, y, yaw)
                    latest['msg'] = None
                    t0 = time.monotonic()
                    while time.monotonic() - t0 < 1.6:
                        rclpy.spin_once(node, timeout_sec=0.05)
                    m = latest['msg']
                    arr = np.frombuffer(bytes(m.data), np.uint8).reshape(m.height, m.width, 3)
                    name = f'{world.stem.replace("rescuemind_", "")}_{station}_{k}.jpg'
                    PImage.fromarray(arr).save(out / 'images' / name, quality=90)
                    rows.append({'image': f'images/{name}', 'station': station, 'world': world.name,
                                 **var, **truth_for(var['scene'], station, hazard_at=var.get('hazard_at')),
                                 'truth_hazard_visible': hazard_visible(station, var.get('hazard_at'), (x, y), yaw),
                                 'pose': [round(x, 3), round(y, 3), round(yaw, 3)], 'distance_m': round(dist, 3)})
            print(f'[{vi + 1}/{len(VARIANTS)}] {world.name}', flush=True)
        finally:
            for p in procs:
                for sig in (signal.SIGINT, signal.SIGKILL):
                    try:
                        os.killpg(p.pid, sig); p.wait(timeout=6); break
                    except Exception:
                        continue
            time.sleep(2)
    (out / 'labels.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    print('images', len(rows))
    node.destroy_node(); rclpy.shutdown()


if __name__ == '__main__':
    main()
