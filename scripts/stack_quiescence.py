#!/usr/bin/env python3
"""Exit 0 only if no RescueMind stack is already running on this ROS domain / Gazebo partition.

v3.3 live finding: an orphaned stack (left by a SIGKILLed supervisor) kept a second
velocity guard publishing /cmd_vel into the next trial.  The orchestrator now refuses
to start while any /cmd_vel publisher, guard, or rescuemind Gazebo world is visible.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import time


def gazebo_world_running() -> bool:
    try:
        out = subprocess.run(['gz', 'topic', '-l'], capture_output=True, text=True, timeout=8).stdout
    except (OSError, subprocess.TimeoutExpired):
        return False
    return any(line.startswith('/world/rescuemind_arena/') for line in out.splitlines())


def ros_publishers(seconds: float = 2.0) -> dict:
    import rclpy
    rclpy.init()
    node = rclpy.create_node('rescuemind_quiescence_probe')
    try:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=0.1)
        return {t: [i.node_name for i in node.get_publishers_info_by_topic(t)]
                for t in ('/cmd_vel', '/rescuemind/guard_ready', '/clock')}
    finally:
        node.destroy_node()
        rclpy.shutdown()


def check() -> dict:
    pubs = ros_publishers()
    gz = gazebo_world_running()
    busy = gz or any(pubs.values())
    return {'quiet': not busy, 'gazebo_world_running': gz, 'publishers': pubs}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--wait', type=float, default=0.0, help='keep polling up to this many seconds')
    a = ap.parse_args(argv)
    end = time.monotonic() + a.wait
    while True:
        r = check()
        if r['quiet'] or time.monotonic() >= end:
            print(json.dumps(r))
            return 0 if r['quiet'] else 3
        time.sleep(3)


if __name__ == '__main__':
    sys.exit(main())
