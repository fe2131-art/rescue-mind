#!/usr/bin/env python3
"""I-01: where does wheel-odometry drift come from?  Open-loop motion patterns,
wheel odometry (/odom) vs Gazebo ground truth (/ground_truth/odom).

  python3 scripts/odometry_drift_study.py --variant baseline [--world-patch name]

Patterns (each from a fresh world): straight 2 m, one in-place turn, and the
'medicine route' command profile (turn, drive, turn, drive) at the controller's
real speeds (0.19 m/s, 0.75 rad/s).  Reports final position / yaw error.
"""
from __future__ import annotations
import argparse
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAUSE = 0.6
TRACE = False
V, W = 0.19, 0.75
PATTERNS = {
    'straight_2m': [(V, 0.0, 2.0 / V)],
    'turn_360': [(0.0, W, 2 * math.pi / W)],
    'turn_cw_360': [(0.0, -W, 2 * math.pi / W)],
    'turn90_then_straight': [(0.0, W, math.radians(90) / W), (V, 0.0, 2.0 / V)],
    'straight_then_turn90_straight': [(V, 0.0, 1.0 / V), (0.0, W, math.radians(90) / W), (V, 0.0, 1.0 / V)],
    'medicine_route': [(0.0, W, math.radians(137) / W), (V, 0.0, 1.6 / V),
                       (0.0, -W, math.radians(176) / W), (V, 0.0, 4.0 / V)],
}


def yaw(q):
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


def run(world_text: str, steps) -> dict:
    import rclpy
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry
    from rclpy.qos import qos_profile_sensor_data
    with tempfile.TemporaryDirectory() as td:
        world = Path(td) / 'w.sdf'
        world.write_text(world_text)
        procs = [subprocess.Popen(['gz', 'sim', '-s', '-r', '--headless-rendering', '-v', '1', str(world)],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True),
                 subprocess.Popen(['bash', str(ROOT / 'scripts/bridge_direct_gazebo.sh')],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)]
        try:
            time.sleep(9)
            rclpy.init()
            n = rclpy.create_node('rescuemind_drift_study')
            last = {}
            n.create_subscription(Odometry, '/odom', lambda m: last.__setitem__('odom', m), qos_profile_sensor_data)
            n.create_subscription(Odometry, '/ground_truth/odom', lambda m: last.__setitem__('gt', m), qos_profile_sensor_data)
            pub = n.create_publisher(Twist, '/cmd_vel', 10)

            trace = []
            def drive(v, w, sec):
                end = time.monotonic() + sec
                while time.monotonic() < end:
                    t = Twist(); t.linear.x = float(v); t.angular.z = float(w); pub.publish(t)
                    rclpy.spin_once(n, timeout_sec=0.02)
                    if TRACE and 'odom' in last and 'gt' in last and (not trace or time.monotonic() - trace[-1][0] > 0.1):
                        o, g = last['odom'].pose.pose, last['gt'].pose.pose
                        trace.append((time.monotonic(), v, w, round(math.degrees(yaw(o.orientation)), 2),
                                      round(math.degrees(yaw(g.orientation)), 2), round(o.position.x, 3), round(o.position.y, 3),
                                      round(g.position.x, 3), round(g.position.y, 3)))
            drive(0, 0, 1.0)
            for v, w, sec in steps:
                drive(v, w, sec)
                drive(0, 0, PAUSE)
            drive(0, 0, 1.0)
            o, g = last['odom'].pose.pose, last['gt'].pose.pose
            out = {'odom_xy': [round(o.position.x, 3), round(o.position.y, 3)],
                   'truth_xy': [round(g.position.x, 3), round(g.position.y, 3)],
                   'pos_error_m': round(math.hypot(o.position.x - g.position.x, o.position.y - g.position.y), 3),
                   'yaw_error_deg': round(math.degrees(math.atan2(math.sin(yaw(o.orientation) - yaw(g.orientation)),
                                                                  math.cos(yaw(o.orientation) - yaw(g.orientation)))), 2)}
            if TRACE:
                t0 = trace[0][0]
                out['trace'] = [[round(r[0] - t0, 2), *r[1:]] for r in trace]
            n.destroy_node(); rclpy.shutdown()
            return out
        finally:
            for p in procs:
                for sig in (signal.SIGINT, signal.SIGKILL):
                    try:
                        os.killpg(p.pid, sig); p.wait(timeout=6); break
                    except Exception:
                        continue


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--variant', required=True)
    ap.add_argument('--world', default=str(ROOT / 'worlds/scenarios/rescuemind_empty.sdf'))
    ap.add_argument('--repeats', type=int, default=2)
    ap.add_argument('--turn-rate', type=float, default=None, help='override in-place turn rate (rad/s)')
    ap.add_argument('--caster-mu', type=float, default=None, help='override caster friction coefficient')
    ap.add_argument('--only', nargs='*', default=None)
    ap.add_argument('--front-caster', action='store_true', help='add a frictionless front caster')
    ap.add_argument('--pause', type=float, default=0.6, help='stop between segments (s)')
    ap.add_argument('--trace', action='store_true')
    ap.add_argument('--sphere-wheels', action='store_true', help='spherical wheel collisions (visuals unchanged)')
    ap.add_argument('--accel', type=float, nargs=2, metavar=('LIN', 'ANG'),
                    help='inject DiffDrive acceleration limits (m/s^2, rad/s^2) into the world')
    a = ap.parse_args()
    text = Path(a.world).read_text()
    if a.accel:
        lin, ang = a.accel
        tag = '<child_frame_id>base_link</child_frame_id>'
        assert text.count(tag) == 1
        text = text.replace(tag, tag + (f'<max_linear_acceleration>{lin}</max_linear_acceleration>'
                                        f'<min_linear_acceleration>-{lin}</min_linear_acceleration>'
                                        f'<max_angular_acceleration>{ang}</max_angular_acceleration>'
                                        f'<min_angular_acceleration>-{ang}</min_angular_acceleration>'))
    if a.caster_mu is not None:
        import re
        i = text.index('<collision name="caster">'); j = text.index('</collision>', i)
        block = re.sub(r'<mu>0</mu>', f'<mu>{a.caster_mu}</mu>', text[i:j])
        block = re.sub(r'<mu2>0</mu2>', f'<mu2>{a.caster_mu}</mu2>', block)
        assert block != text[i:j]
        text = text[:i] + block + text[j:]
    if a.front_caster:
        i = text.index('<collision name="caster">'); j = text.index('</collision>', i) + len('</collision>')
        front = text[i:j].replace('name="caster"', 'name="front_caster"').replace('-.18 0 -.09', '.18 0 -.09')
        assert front != text[i:j]
        text = text[:j] + front + text[j:]
    if a.sphere_wheels:
        import re
        for wheel in ('left_wheel', 'right_wheel'):
            i = text.index(f'<link name="{wheel}">'); j = text.index('</collision>', i)
            block = re.sub(r'<cylinder>\s*<radius>.115</radius>\s*<length>.05</length>\s*</cylinder>',
                           '<sphere><radius>.115</radius></sphere>', text[i:j])
            assert block != text[i:j], wheel
            text = text[:i] + block + text[j:]
    global PAUSE, TRACE
    PAUSE = a.pause
    TRACE = a.trace
    patterns = PATTERNS
    if a.turn_rate:
        k = a.turn_rate / W
        patterns = {n: [(v, w * k, sec / k) if w else (v, w, sec) for v, w, sec in st] for n, st in PATTERNS.items()}
    res = {'variant': a.variant, 'world': Path(a.world).name, 'args': vars(a), 'patterns': {}}
    for name, steps in patterns.items():
        if a.only and name not in a.only:
            continue
        res['patterns'][name] = [run(text, steps) for _ in range(a.repeats)]
        print(name, res['patterns'][name], flush=True)
    dest = ROOT / 'experiments/results/i01_drift' / f'{a.variant}.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(res, indent=1) + '\n')


if __name__ == '__main__':
    sys.exit(main())
