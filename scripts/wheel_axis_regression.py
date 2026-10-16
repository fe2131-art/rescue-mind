#!/usr/bin/env python3
"""Reproduce the v3.2 wheel-axis defect against the v3.3 fix with Gazebo ground truth.

Two worlds that differ ONLY in the wheel joint axis declaration:
  handoff_v32 : <xyz>0 1 0</xyz>                       (expressed in the rolled wheel frame)
  fixed_v33   : <xyz expressed_in="__model__">0 1 0</xyz>
Same open-loop command for both: 0.3 m/s forward for 4 s, then 0.6 rad/s for 3 s.
Records wheel odometry (/odom) and simulator truth (/ground_truth/odom).
Run inside docker/run.sh with no other stack running.
"""
from __future__ import annotations
import json
import math
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXED = '<xyz expressed_in="__model__">0 1 0</xyz>'
HANDOFF = '<xyz>0 1 0</xyz>'


def run_world(sdf_text: str) -> dict:
    import rclpy
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry
    from rclpy.qos import qos_profile_sensor_data
    with tempfile.TemporaryDirectory() as td:
        world = Path(td) / 'world.sdf'
        world.write_text(sdf_text)
        gz = subprocess.Popen(['gz', 'sim', '-s', '-r', '--headless-rendering', '-v', '1', str(world)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        br = subprocess.Popen(['bash', str(ROOT / 'scripts/bridge_direct_gazebo.sh')],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            time.sleep(10)
            rclpy.init()
            node = rclpy.create_node('rescuemind_wheel_axis_regression')
            odom, truth = [], []
            node.create_subscription(Odometry, '/odom', lambda m: odom.append(
                (time.monotonic(), m.pose.pose.position.x, m.pose.pose.position.y)), qos_profile_sensor_data)
            def on_truth(m):
                q = m.pose.pose.orientation
                tilt = math.degrees(math.acos(max(-1., min(1., 1 - 2 * (q.x * q.x + q.y * q.y)))))
                truth.append((time.monotonic(), m.pose.pose.position.x, m.pose.pose.position.y, tilt))
            node.create_subscription(Odometry, '/ground_truth/odom', on_truth, qos_profile_sensor_data)
            pub = node.create_publisher(Twist, '/cmd_vel', 10)
            def drive(v, w, seconds):
                end = time.monotonic() + seconds
                while time.monotonic() < end:
                    t = Twist(); t.linear.x = v; t.angular.z = w
                    pub.publish(t)
                    rclpy.spin_once(node, timeout_sec=0.05)
            drive(0., 0., 1.0)
            odom.clear(); truth.clear()
            drive(0.3, 0., 4.0)
            drive(0., 0.6, 3.0)
            drive(0., 0., 1.0)
            node.destroy_node(); rclpy.shutdown()
        finally:
            for p in (br, gz):
                try:
                    import os, signal
                    os.killpg(p.pid, signal.SIGINT); p.wait(timeout=8)
                except Exception:
                    import os, signal
                    os.killpg(p.pid, signal.SIGKILL)
    import bisect
    ot = [o[0] for o in odom]
    gap = 0.0
    for t, tx, ty, _ in truth:
        k = min(max(bisect.bisect_left(ot, t), 0), len(odom) - 1)
        gap = max(gap, math.hypot(odom[k][1] - tx, odom[k][2] - ty))
    return {'odom': [[round(x, 3), round(y, 3)] for _, x, y in odom[::5]],
            'truth': [[round(x, 3), round(y, 3)] for _, x, y, _ in truth[::2]],
            'final_odom': [round(odom[-1][1], 3), round(odom[-1][2], 3)],
            'final_truth': [round(truth[-1][1], 3), round(truth[-1][2], 3)],
            'max_tilt_deg': round(max(r[3] for r in truth), 1),
            'max_gap_m': round(gap, 3)}


def main():
    fixed = (ROOT / 'worlds/scenarios/rescuemind_nominal.sdf').read_text()
    if fixed.count(FIXED) != 2:
        sys.exit('unexpected world: fixed axis declaration not found twice')
    out = {'command': '0.3 m/s x 4 s, then 0.6 rad/s x 3 s (open loop)',
           'handoff_v32': run_world(fixed.replace(FIXED, HANDOFF)),
           'fixed_v33': run_world(fixed)}
    dest = ROOT / 'experiments/results/wheel_axis_regression.json'
    dest.write_text(json.dumps(out, indent=1) + '\n')
    for k in ('handoff_v32', 'fixed_v33'):
        r = out[k]
        print(k, 'final odom', r['final_odom'], 'final truth', r['final_truth'],
              'max gap', r['max_gap_m'], 'max tilt', r['max_tilt_deg'])


if __name__ == '__main__':
    main()
