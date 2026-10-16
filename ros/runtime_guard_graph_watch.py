#!/usr/bin/env python3
"""Independent ROS publisher identity watch during the entire Gazebo mission.

Polls the live DDS graph every 200ms. If /cmd_vel (or guard_ready) acquires an
unauthorized publisher, publish ESTOP on /rescuemind/estop and exit nonzero,
triggering Supervisor stack shutdown. NOT cryptographic authentication; a
rogue ROS participant can bypass this monitor. SIMULATION ONLY.
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.runtime_guard_graph import RuntimeGuardGraph, GraphMonitorFault


def run(args) -> int:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import Bool
    rclpy.init()
    node=Node('rescuemind_guard_graph_watch')
    estop=node.create_publisher(Bool,'/rescuemind/estop',10)
    model=RuntimeGuardGraph(time.monotonic(),startup_grace_s=args.startup_grace)
    path=Path(args.out)
    path.parent.mkdir(parents=True,exist_ok=True)
    last_report=None
    last_logged=-args.log_period
    try:
        with path.open('a',encoding='utf8') as output:
            while rclpy.ok():
                rclpy.spin_once(node,timeout_sec=args.interval)
                now=time.monotonic()
                cmd=node.get_publishers_info_by_topic('/cmd_vel')
                ready=node.get_publishers_info_by_topic('/rescuemind/guard_ready')
                try:
                    state=model.observe(now,cmd,ready)
                except GraphMonitorFault as fault:
                    state='FAILED_LATCHED'
                    output.write(json.dumps({'elapsed_s':round(now-model.started_at,3),'state':state,
                         'reason':str(fault),'cmd_publishers':len(cmd),'guard_ready_publishers':len(ready)},ensure_ascii=False)+'\n')
                    output.flush()
                    # Do not assume that a graph fault can override rogue /cmd_vel
                    # publishers; this is best-effort and NOT safety certified.
                    for _ in range(12):
                        estop.publish(Bool(data=True))
                        rclpy.spin_once(node,timeout_sec=.045)
                    node.get_logger().error('Guard publisher topology fault: '+str(fault))
                    return 9
                if state != last_report or now-model.started_at-last_logged >= args.log_period:
                    output.write(json.dumps({'elapsed_s':round(now-model.started_at,3),'state':state,
                                              'cmd_publishers':len(cmd),'guard_ready_publishers':len(ready)},ensure_ascii=False)+'\n')
                    output.flush()
                    last_logged=now-model.started_at
                    last_report=state
        return 0
    finally:
        node.destroy_node()
        rclpy.shutdown()


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',required=True)
    p.add_argument('--interval',type=float,default=.20)
    p.add_argument('--startup-grace',type=float,default=8.0)
    p.add_argument('--log-period',type=float,default=2.0)
    args=p.parse_args(argv)
    if not .05 <= args.interval <= 1. or not 2 <= args.startup_grace <= 60 or not .25 <= args.log_period <= 60:
        p.error('invalid watch timing')
    try:
        return run(args)
    except (OSError,RuntimeError) as exc:
        print(type(exc).__name__+': '+str(exc),file=sys.stderr)
        return 9

if __name__=='__main__':
    raise SystemExit(main())
