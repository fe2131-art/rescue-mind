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
            self.policy=VelocityRelay(started_at=time.monotonic())
            self.command_pub=self.create_publisher(Twist,'/cmd_vel',10)
            self.status_pub=self.create_publisher(Bool,'/rescuemind/guard_ready',10)
            self.create_subscription(Twist,'/rescuemind/cmd_vel_request',self.on_request,10)
            self.create_subscription(Odometry,'/odom',self.on_odom,qos_profile_sensor_data)
            self.create_subscription(Image,'/camera',self.on_camera,image_qos())
            self.create_subscription(LaserScan,'/scan',self.on_lidar,qos_profile_sensor_data)
            self.create_subscription(Bool,'/rescuemind/estop',self.on_estop,10)
            self.timer=self.create_timer(.10,self.on_tick)
            self.last_reason=None
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
            outcome=self.policy.decide(time.monotonic())
            velocity=Twist()
            velocity.linear.x=outcome.linear
            velocity.angular.z=outcome.angular
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
    run(parser.parse_args())
