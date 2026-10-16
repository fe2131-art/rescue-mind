#!/usr/bin/env python3
"""Read-only runtime contract test on Ubuntu Jazzy after Gazebo/bridge start.

No velocity command is published. Exits nonzero for missing/invalid sensor data.
Usage: python3 scripts/v15_ros_sensor_probe.py --seconds 20 --output outputs/diagnostics/sensors.json
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.sensor_contract import StreamAudit
from rescuemind.ros_qos import image_qos


def live(seconds, target):
    try:
        import rclpy
        from rclpy.qos import qos_profile_sensor_data
        from sensor_msgs.msg import Image, LaserScan
        from nav_msgs.msg import Odometry
    except ImportError as e:
        raise RuntimeError('ROS 2 Jazzy Python modules unavailable; source ROS and use .venv from setup_ubuntu_jazzy.sh') from e
    audit = StreamAudit(minimum_messages=target)
    rclpy.init()
    node=rclpy.create_node('rescuemind_v15_sensor_probe')
    def wrap(method):
        def cb(msg):
            try: method(msg)
            except (ValueError,AttributeError,TypeError,OverflowError) as err:
                reason = str(err)
                if reason not in audit.problems: audit.problems.append(reason)
        return cb
    subscriptions=[
        node.create_subscription(Image,'/camera',wrap(audit.add_image),image_qos()),
        node.create_subscription(LaserScan,'/scan',wrap(audit.add_scan),qos_profile_sensor_data),
        node.create_subscription(Odometry,'/odom',wrap(audit.add_odom),qos_profile_sensor_data),
    ]
    end=time.monotonic()+seconds
    try:
        while time.monotonic()<end and not audit.report()['ok'] and not audit.problems:
            rclpy.spin_once(node,timeout_sec=0.1)
    finally:
        _=subscriptions
        node.destroy_node()
        rclpy.shutdown()
    return audit.report()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seconds',type=float,default=20)
    p.add_argument('--minimum-messages',type=int,default=3)
    p.add_argument('--output',default=str(ROOT/'outputs/local_runtime_diagnostics/v15_sensor_probe.json'))
    a=p.parse_args(argv)
    if not 2 <= a.seconds <= 120 or not 2 <= a.minimum_messages <= 20:
        p.error('seconds must be [2,120] and minimum-messages [2,20]')
    try:
        result=live(a.seconds,a.minimum_messages)
    except (RuntimeError,OSError) as e:
        result={'ok':False,'issues':[str(e)],'scope':'runtime ROS probe failed'}
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['ok'] else 4

if __name__=='__main__': raise SystemExit(main())
