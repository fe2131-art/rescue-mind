#!/usr/bin/env python3
"""Read-only ROS clock + camera/scan/odom domain test on user's Ubuntu machine.

Does not send motor commands. Use after Gazebo and bridge are running.
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.sim_clock_contract import SimClockContract,ClockContractError
from rescuemind.ros_qos import image_qos

def probe(seconds: float, max_skew_s: float=2.0) -> dict:
    import rclpy
    from rclpy.qos import qos_profile_sensor_data
    from rclpy.node import Node
    from rosgraph_msgs.msg import Clock
    from nav_msgs.msg import Odometry
    from sensor_msgs.msg import LaserScan, Image
    contract=SimClockContract(max_skew_s=max_skew_s)
    rclpy.init()
    node=Node('rescuemind_v20_clock_probe')
    def callback(name):
        def cb(msg):
            s=msg.clock if name=='clock' else msg.header.stamp
            try:
                if name=='clock': contract.clock(int(s.sec),int(s.nanosec))
                else: contract.sensor(name,int(s.sec),int(s.nanosec))
            except ClockContractError as exc:
                contract.issues.append(name+'_invalid_stamp:'+str(exc))
        return cb
    subs=[node.create_subscription(Clock,'/clock',callback('clock'),10),
          node.create_subscription(Image,'/camera',callback('camera'),image_qos()),
          node.create_subscription(LaserScan,'/scan',callback('scan'),qos_profile_sensor_data),
          node.create_subscription(Odometry,'/odom',callback('odom'),qos_profile_sensor_data)]
    deadline=time.monotonic()+seconds
    try:
        while time.monotonic()<deadline:
            rclpy.spin_once(node,timeout_sec=0.1)
            if contract.report()['ok'] or contract.issues: break
    finally:
        _=subs; node.destroy_node(); rclpy.shutdown()
    return contract.report()

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seconds',type=float,default=16.)
    p.add_argument('--max-skew-s',type=float,default=2.)
    p.add_argument('--output',default=str(ROOT/'outputs/local_runtime_diagnostics/v20_clock.json'))
    a=p.parse_args(argv)
    if not 2<=a.seconds<=120: p.error('seconds must be in [2,120]')
    try: result=probe(a.seconds,a.max_skew_s)
    except (ImportError,RuntimeError,ClockContractError) as e:
        result={'ok':False,'issues':[str(e)],'scope':'runtime ROS clock probe unavailable or failed'}
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['ok'] else 4

if __name__=='__main__':raise SystemExit(main())
