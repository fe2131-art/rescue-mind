"""Run as INDEPENDENT ROS 2 node before the mission; publishes /cmd_vel at 10 Hz.

WARNING: Designed for Gazebo simulation only, not safety-certified hardware.
The relay must be the ONLY /cmd_vel publisher. Avoid ros2 topic pub /cmd_vel.
Stop all robot processes and pause Gazebo before restarting after a fault.
"""
from __future__ import annotations
import argparse
import time
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.velocity_relay import VelocityRelay, planar_request_components
from rescuemind.ros_qos import image_qos


def run(args):
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from geometry_msgs.msg import Twist
    from std_msgs.msg import Bool
    from nav_msgs.msg import Odometry
    from sensor_msgs.msg import Image,LaserScan

    class Guard(Node):
        def __init__(self):
            super().__init__('rescuemind_velocity_guard')
            self.policy=VelocityRelay(started_at=time.monotonic(),latch_stale_zero=args.legacy_latch_zero)
            self.command_pub=self.create_publisher(Twist,'/cmd_vel',10)
            from rescuemind.ros_qos import control_qos
            self.status_pub=self.create_publisher(Bool,'/rescuemind/guard_ready',control_qos(args.control_qos))
            self.create_subscription(Twist,'/rescuemind/cmd_vel_request',self.on_request,control_qos(args.control_qos))
            self.create_subscription(Odometry,'/odom',self.on_odom,qos_profile_sensor_data)
            self.create_subscription(Image,'/camera',self.on_camera,image_qos())
            self.create_subscription(LaserScan,'/scan',self.on_lidar,qos_profile_sensor_data)
            self.create_subscription(Bool,'/rescuemind/estop',self.on_estop,10)
            self.gate=None
            if getattr(args,'delivery_interlock',False):
                # I-22: during the 'deliver' phase non-zero velocity needs a valid permit for the latest approval record.
                # Imports only the tiny permit module; knows nothing about the mission node or the decision rule.
                from std_msgs.msg import String
                from rescuemind import delivery_permit as dp
                key=dp.load_key(args.permit_key_file) if getattr(args,'permit_key_file',None) else None
                self.gate=dp.PermitGate(key=key)
                q=control_qos('reliable')
                self.create_subscription(String,dp.TOPIC_RECORD,lambda m:self.gate.on_record(m.data),q)
                self.create_subscription(String,dp.TOPIC_PERMIT,lambda m:self.gate.on_permit(m.data),q)
                self.create_subscription(String,dp.TOPIC_PHASE,lambda m:self.gate.on_phase(m.data,time.time()),q)
                self.get_logger().info('delivery interlock ON, hmac='+str(key is not None))
            self.last_gate=None
            self.timer=self.create_timer(.10,self.on_tick)
            self.last_reason=None
            self.last_tick=None
            self.max_tick_gap=0.0
        def on_request(self,msg):
            try:
                linear,angular=planar_request_components(msg)
            except ValueError as exc:
                self.policy.latched=str(exc)
                return
            self.policy.request(linear,angular,time.monotonic())
        def on_odom(self,msg):
            self.policy.odometry(time.monotonic(),msg)
        def on_camera(self,msg):
            self.policy.camera_frame(msg,time.monotonic())
        def on_lidar(self,msg):
            self.policy.laser_scan(msg,time.monotonic())
        def on_estop(self,msg):
            self.policy.emergency_stop(bool(msg.data))
        def on_tick(self):
            now=time.monotonic()
            # I-09: diagnose stale-request latches (guard starvation vs. a silent mission)
            tick_gap=None if self.last_tick is None else now-self.last_tick
            self.last_tick=now
            outcome=self.policy.decide(now)
            if outcome.reason=='stale_velocity_command' and self.last_reason!='stale_velocity_command':
                since=None if self.policy.last_cmd_at is None else now-self.policy.last_cmd_at
                self.get_logger().error(f'stale request latch: since_last_request={since} tick_gap={tick_gap} '
                                        f'max_tick_gap={self.max_tick_gap:.3f}')
            if tick_gap is not None:
                self.max_tick_gap=max(self.max_tick_gap,tick_gap)
            velocity=Twist()
            velocity.linear.x=outcome.linear
            velocity.angular.z=outcome.angular
            if self.gate is not None:
                lin,ang,why=self.gate.filter(outcome.linear,outcome.angular,time.time())
                velocity.linear.x=lin
                velocity.angular.z=ang
                if why!=self.last_gate:
                    self.get_logger().info('delivery gate: '+(why or 'pass'))
                    self.last_gate=why
            self.command_pub.publish(velocity)
            self.status_pub.publish(Bool(data=outcome.ready))
            if outcome.reason != self.last_reason:
                self.get_logger().info('relay state: '+outcome.reason)
                self.last_reason=outcome.reason

    rclpy.init()
    node=Guard()
    try:rclpy.spin(node)
    finally:
        for _ in range(10):
            stop=Twist()
            node.command_pub.publish(stop)
            time.sleep(.03)
        node.destroy_node()
        rclpy.shutdown()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--control-qos',choices=['reliable','best_effort'],default='reliable',
                        help='I-12: QoS of the request / heartbeat topics (must match the mission)')
    parser.add_argument('--legacy-latch-zero',action='store_true',
                        help='pre-v3.4: latch even when the stale request was zero (A/B experiments only)')
    parser.add_argument('--delivery-interlock',action='store_true',
                        help='I-22 (default off): in the mission phase \'deliver\' forward non-zero velocity only with a valid permit')
    parser.add_argument('--permit-key-file',default=None,help='I-22: HMAC key shared with the interlock node (omit: unsigned permits)')
    run(parser.parse_args())
