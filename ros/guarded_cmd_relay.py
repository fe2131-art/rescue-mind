"""Run as INDEPENDENT ROS 2 node before the mission; publishes /cmd_vel at 10 Hz.

WARNING: Designed for Gazebo simulation only, not safety-certified hardware.
The relay must be the ONLY /cmd_vel publisher. Avoid ros2 topic pub /cmd_vel.
Stop all robot processes and pause Gazebo before restarting after a fault.
"""
from __future__ import annotations
import argparse
import math
import time
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.velocity_relay import VelocityRelay, planar_request_components
from rescuemind.ros_qos import image_qos
from rescuemind import real_profile as rp


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
            # I-26 (default off): camera QoS and odometry frame suffixes for a real robot; without the flags the objects are
            # exactly the ones used so far
            cam_rel,odom_fr,base_fr=rp.guard_settings(args)
            relay_kw={}
            if odom_fr is not None or base_fr is not None:
                from rescuemind.odom_health import OdomHealth
                relay_kw['odom_health']=OdomHealth(odom_frame=odom_fr or 'odom',base_frame=base_fr or 'base_link')
            self.policy=VelocityRelay(started_at=time.monotonic(),latch_stale_zero=args.legacy_latch_zero,**relay_kw)
            self.command_pub=self.create_publisher(Twist,'/cmd_vel',10)
            from rescuemind.ros_qos import control_qos
            self.status_pub=self.create_publisher(Bool,'/rescuemind/guard_ready',control_qos(args.control_qos))
            self.create_subscription(Twist,'/rescuemind/cmd_vel_request',self.on_request,control_qos(args.control_qos))
            self.create_subscription(Odometry,'/odom',self.on_odom,qos_profile_sensor_data)
            self.create_subscription(Image,'/camera',self.on_camera,
                                     image_qos() if cam_rel=='reliable' else image_qos(reliability=cam_rel))
            self.create_subscription(LaserScan,'/scan',self.on_lidar,qos_profile_sensor_data)
            self.create_subscription(Bool,'/rescuemind/estop',self.on_estop,10)
            self.gate=None
            if getattr(args,'delivery_interlock',False):
                # I-22: during the 'deliver' phase non-zero velocity needs a valid permit for the latest approval record.
                # Imports only the tiny permit module; knows nothing about the mission node or the decision rule.
                from std_msgs.msg import String
                from rescuemind import delivery_permit as dp
                key=dp.load_key(args.permit_key_file) if getattr(args,'permit_key_file',None) else None
                fence=None
                if getattr(args,'geofence_config',None):
                    # shelter geofence from the per-run waypoints file given to the guard (not from the mission); a missing
                    # or malformed file raises here, so the guard does not start (fail closed)
                    fence=dp.ShelterGeofence.from_waypoints_file(args.geofence_config,getattr(args,'geofence_radius',None) or dp.GEOFENCE_RADIUS_M)
                    self.get_logger().info(f'shelter geofence ON: centre={fence.centre} radius={fence.radius}')
                else:
                    self.get_logger().warning('delivery interlock without --geofence-config: the mission-reported phase is trusted')
                self.gate=dp.PermitGate(key=key,fence=fence)
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
            if self.gate is not None:
                try:
                    p,q=msg.pose.pose.position,msg.pose.pose.orientation
                    yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
                    self.gate.on_odom(float(p.x),float(p.y),yaw,time.time())
                except (AttributeError,TypeError,ValueError):
                    pass                         # unusable odometry is never stored: the fence then fails closed
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
    parser.add_argument('--geofence-config',default=None,
                        help='I-22: per-run waypoints.json whose B is the centre of the shelter geofence (non-zero velocity into it needs a permit whatever phase is claimed)')
    parser.add_argument('--geofence-radius',type=float,default=None,help='I-22: geofence radius in metres (default 0.5)')
    parser.add_argument('--permit-key-file',default=None,help='I-22: HMAC key shared with the interlock node (omit: unsigned permits)')
    parser.add_argument('--real-profile',action='store_true',
                        help='I-26 (default off): the real-robot profile; required for --camera-qos best_effort')
    parser.add_argument('--camera-qos',choices=['reliable','best_effort'],default='reliable',
                        help='I-26: /camera subscription QoS (must be compatible with the driver; best_effort needs --real-profile)')
    parser.add_argument('--odom-frame',default=None,help="I-26: /odom header.frame_id must end with this (default 'odom')")
    parser.add_argument('--base-frame',default=None,help="I-26: /odom child_frame_id must end with this (default 'base_link')")
    parser.add_argument('--site-config',default=None,help='I-26: site.json; supplies --odom-frame / --base-frame when they are not given')
    ns=parser.parse_args()
    try:
        rp.guard_settings(ns)                    # validate before any ROS node exists
    except rp.SiteConfigError as e:
        parser.error(str(e))
    run(ns)
