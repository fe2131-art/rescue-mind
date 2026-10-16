#!/usr/bin/env python3
"""Count visible fire pixels at given camera poses by rendering the flat-magenta fire mask (occlusion-aware).

  python3 scripts/fire_mask_at_pose.py --protocol experiments/campaign_f_protocol.json --design     # planned checkpoint pose
  python3 scripts/fire_mask_at_pose.py --protocol experiments/campaign_f_protocol.json \
      --ledger experiments/results/campaign_F_ledger.jsonl                                           # logged GT pose

--design uses the nominal checkpoint pose of each station (the median ground-truth pose of campaign D) to check
that the "mostly hidden" fires are partly visible at all.  With --ledger, the pose is the robot's Gazebo
ground-truth pose at the checkpoint frame of the station where the fire is, so the label is what the camera saw.
Labels follow T1 amendment 2: >= 614 px visible, <= 20 px hidden, otherwise ambiguous.
"""
from __future__ import annotations
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import scripts.build_testset_t1 as t1  # noqa: E402
from rescuemind.robust_scenes import build_variant  # noqa: E402

DESIGN_POSE = {'water': (1.03, 0.99, 0.769), 'medicine': (-1.03, 0.97, 2.388)}


def logged_pose(run_id: str, fire_at: str):
    from scripts.fire_visibility_check import pose_at
    run = ROOT / 'outputs/runs' / run_id
    m = json.loads((run / 'mission.json').read_text())
    stage = 'checkpoint_frame' if m.get('checkpoint_station') == fire_at else 'recovery_checkpoint_frame'
    ev = next((e for e in m['events'] if e.get('stage') == stage), None)
    if ev is None:
        return None
    (x, y, yaw), _ = pose_at(run, m['mission_start_unix_ns'] + int(ev['t_wall_s'] * 1e9))
    return x, y, yaw


def render(jobs):
    import numpy as np
    import rclpy
    from sensor_msgs.msg import Image
    from rescuemind.ros_qos import image_qos
    wdir = ROOT / 'worlds/fire_masks'
    wdir.mkdir(parents=True, exist_ok=True)
    rclpy.init()
    node = rclpy.create_node('rescuemind_fire_mask')
    latest = {'msg': None}
    node.create_subscription(Image, '/camera', lambda m: latest.__setitem__('msg', m), image_qos())
    results = []
    for job in jobs:
        world = wdir / f"rescuemind_{job['key']}_mask.sdf"
        kw = dict(job['world_spec']); kw['hazard_geom'] = tuple(kw['hazard_geom']); kw['hazard_mask'] = True
        world.write_bytes(build_variant(ROOT / f"worlds/scenarios/rescuemind_{job['scene']}.sdf", **kw))
        procs = [subprocess.Popen(['gz', 'sim', '-s', '-r', '--headless-rendering', '-v', '1', str(world)],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True),
                 subprocess.Popen(['bash', str(ROOT / 'scripts/bridge_direct_gazebo.sh')],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)]
        try:
            time.sleep(9)
            t1.set_pose(*job['pose'])
            latest['msg'] = None
            t0 = time.monotonic()
            while time.monotonic() - t0 < 1.6 or (latest['msg'] is None and time.monotonic() - t0 < 10):
                rclpy.spin_once(node, timeout_sec=0.05)
            m = latest['msg']
            a = np.frombuffer(bytes(m.data), np.uint8).reshape(m.height, m.width, 3).astype(int)
            px = int(((a[..., 0] > 150) & (a[..., 2] > 150) & (a[..., 1] < 100)).sum())
            results.append({**{k: job[k] for k in ('key', 'pose')}, 'fire_pixels': px, 'visibility': t1.mask_label(px)})
            print(json.dumps(results[-1]), flush=True)
        finally:
            for p in procs:
                for sig in (signal.SIGINT, signal.SIGKILL):
                    try:
                        os.killpg(p.pid, sig); p.wait(timeout=6); break
                    except Exception:
                        continue
            time.sleep(2)
    node.destroy_node(); rclpy.shutdown()
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--protocol', required=True)
    ap.add_argument('--ledger')
    ap.add_argument('--design', action='store_true')
    ap.add_argument('--design-sides', type=float, default=0.0,
                    help='with --design: also render at the two side poses this far (m) left/right of the checkpoint')
    a = ap.parse_args()
    proto = json.loads(Path(a.protocol).read_text())
    jobs = []
    if a.design:
        seen = set()
        for t in proto['trials']:
            spec = t['world_spec']
            if 'hazard_at' in spec and t['world'] not in seen:
                seen.add(t['world'])
                jobs.append({'key': t['world'], 'scene': t['scene'], 'world_spec': spec,
                             'pose': DESIGN_POSE[spec['hazard_at']]})
                if a.design_sides:
                    import math
                    x, y, _ = DESIGN_POSE[spec['hazard_at']]
                    sx, sy = (2.0, 2.0) if spec['hazard_at'] == 'water' else (-2.0, 2.0)
                    n = math.hypot(sx - x, sy - y); vx, vy = -(sy - y) / n, (sx - x) / n
                    for side, k in (('L', -1), ('R', 1)):
                        px, py = x + k * a.design_sides * vx, y + k * a.design_sides * vy
                        jobs.append({'key': t['world'] + side, 'scene': t['scene'], 'world_spec': spec,
                                     'pose': (round(px, 3), round(py, 3), round(math.atan2(sy - py, sx - px), 3))})
        dest = Path(a.protocol).with_name(Path(a.protocol).stem + '_design_fire_masks.json')
    else:
        trials = {t['id']: t for t in proto['trials']}
        for line in Path(a.ledger).read_text().splitlines():
            r = json.loads(line)
            t = trials.get(r['trial_id'])
            if not r.get('final', True) or not t or 'hazard_at' not in t['world_spec'] or not r.get('run_id'):
                continue
            pose = logged_pose(r['run_id'], t['world_spec']['hazard_at'])
            if pose:
                jobs.append({'key': r['trial_id'], 'scene': t['scene'], 'world_spec': t['world_spec'], 'pose': pose})
        dest = Path(a.ledger).with_name(Path(a.ledger).stem + '_fire_masks.json')
    res = render(jobs)
    dest.write_text(json.dumps(res, indent=1) + '\n')
    print('saved', dest)


if __name__ == '__main__':
    main()
