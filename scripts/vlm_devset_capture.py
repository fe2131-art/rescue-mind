#!/usr/bin/env python3
"""Capture a VLM *development* image set from Gazebo (separate from the locked test).

For each controlled scene the robot is teleported (gz set_pose) to randomized
viewpoints around each supply station: distance, bearing and residual camera yaw
are jittered with a fixed seed that differs from the locked 30-trial protocol.
Prompt / threshold design is tuned ONLY on this set; the pre-registered
closed-loop missions (scripts/run_campaign.py) are the held-out test.

Run inside the ROS/Gazebo container with Gazebo + bridge already running for
--scene, e.g. via scripts/vlm_devset_build.sh.
"""
from __future__ import annotations
import argparse
import json
import math
import random
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind.ros_qos import image_qos  # noqa: E402

STATIONS = {'water': (2.0, 2.0), 'medicine': (-2.0, 2.0)}
TRUTH = {'nominal': {'water': 'water', 'medicine': 'medicine'},
         'swapped': {'water': 'medicine', 'medicine': 'water'},
         'empty': {'water': 'other', 'medicine': 'other'}}


def set_pose(x, y, yaw):
    req = (f'name: "rescue_diffbot" position {{x: {x:.4f} y: {y:.4f} z: 0.16}} '
           f'orientation {{z: {math.sin(yaw / 2):.6f} w: {math.cos(yaw / 2):.6f}}}')
    subprocess.run(['gz', 'service', '-s', '/world/rescuemind_arena/set_pose', '--reqtype', 'gz.msgs.Pose',
                    '--reptype', 'gz.msgs.Boolean', '--timeout', '3000', '--req', req],
                   check=True, capture_output=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--scene', choices=sorted(TRUTH), required=True)
    ap.add_argument('--out', default=str(ROOT / 'experiments/vlm_devset'))
    ap.add_argument('--per-station', type=int, default=8)
    ap.add_argument('--seed', type=int, default=7)
    a = ap.parse_args(argv)
    import numpy as np
    import rclpy
    from PIL import Image as PImage
    from sensor_msgs.msg import Image
    out = Path(a.out)
    (out / 'images').mkdir(parents=True, exist_ok=True)
    rng = random.Random(f'{a.seed}-{a.scene}')
    rclpy.init()
    node = rclpy.create_node('rescuemind_devset_capture')
    latest = {'msg': None}
    node.create_subscription(Image, '/camera', lambda m: latest.__setitem__('msg', m), image_qos())
    rows = []
    for station, (sx, sy) in STATIONS.items():
        # Viewpoints scatter around the approach side facing the arena origin.
        for k in range(a.per_station):
            dist = rng.uniform(0.95, 1.55)
            bearing = math.atan2(0 - sy, 0 - sx) + rng.uniform(-0.45, 0.45)
            x, y = sx + dist * math.cos(bearing), sy + dist * math.sin(bearing)
            yaw = math.atan2(sy - y, sx - x) + rng.uniform(-0.09, 0.09)
            set_pose(x, y, yaw)
            latest['msg'] = None
            t0 = time.monotonic()
            while time.monotonic() - t0 < 1.6:
                rclpy.spin_once(node, timeout_sec=0.05)
            m = latest['msg']
            if m is None:
                raise SystemExit('no camera frame received')
            arr = np.frombuffer(bytes(m.data), np.uint8).reshape(m.height, m.width, 3)
            name = f'{a.scene}_{station}_{k:02d}.jpg'
            PImage.fromarray(arr).save(out / 'images' / name, quality=90)
            rows.append({'image': f'images/{name}', 'scene': a.scene, 'station': station,
                         'truth_supply': TRUTH[a.scene][station], 'distance_m': round(dist, 3),
                         'bearing_rad': round(bearing, 3), 'yaw_rad': round(yaw, 3)})
    with (out / 'labels.jsonl').open('a', encoding='utf8') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    print(f'captured {len(rows)} images for {a.scene}')
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
