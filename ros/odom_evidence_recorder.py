#!/usr/bin/env python3
"""Independent, append-only observation of /odom and /cmd_vel into JSONL.

Run as a separate subprocess under the stack supervisor.  Data can be spoofed
on an unsecured ROS graph and therefore does not authenticate Gazebo provenance.
No movement commands are published by this process.
"""
from __future__ import annotations
import argparse,json,sys,time
from pathlib import Path

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',required=True)
    p.add_argument('--run-id',required=True)
    a=p.parse_args(argv)
    if len(a.run_id)!=16 or any(c not in '0123456789abcdef' for c in a.run_id):
        p.error('run-id must be 16 lowercase hex digits')
    out=Path(a.out)
    out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists():
        p.error('refuse to overwrite existing independent evidence file')
    import rclpy
    from rclpy.qos import qos_profile_sensor_data
    from rclpy.node import Node
    from nav_msgs.msg import Odometry
    from geometry_msgs.msg import Twist
    with out.open('x',encoding='utf8',buffering=1) as handle:
        def write(record):
            handle.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+'\n')
        write({'kind':'meta','schema':'rescuemind_ros_observation_v1',
               'run_id':a.run_id,'start_unix_ns':time.time_ns(),
               'provenance':'ROS_topic_subscription_not_cryptographically_authenticated'})
        rclpy.init()
        class Recorder(Node):
            def __init__(self):
                super().__init__('rescuemind_independent_odom_recorder')
                self.odom=self.create_subscription(Odometry,'/odom',self.on_odom,qos_profile_sensor_data)
                self.vel=self.create_subscription(Twist,'/cmd_vel',self.on_vel,10)
                # Simulator ground truth (Gazebo OdometryPublisher on the true model pose):
                # independent of wheel odometry, which the controller itself consumes.
                self.truth=self.create_subscription(Odometry,'/ground_truth/odom',self.on_truth,qos_profile_sensor_data)
            def on_odom(self,m):
                s=m.header.stamp
                q=m.pose.pose.position
                write({'kind':'odom','ros_stamp_ns':int(s.sec)*1000000000+int(s.nanosec),
                       'wall_unix_ns':time.time_ns(),'x':float(q.x),'y':float(q.y),
                       'frame_id':m.header.frame_id,'child_frame_id':m.child_frame_id})
            def on_truth(self,m):
                s=m.header.stamp
                q=m.pose.pose.position
                o=m.pose.pose.orientation
                write({'kind':'ground_truth','ros_stamp_ns':int(s.sec)*1000000000+int(s.nanosec),
                       'wall_unix_ns':time.time_ns(),'x':float(q.x),'y':float(q.y),'z':float(q.z),
                       'qx':float(o.x),'qy':float(o.y),'qz':float(o.z),'qw':float(o.w)})
            def on_vel(self,m):
                write({'kind':'cmd_vel','wall_unix_ns':time.time_ns(),
                       'linear':float(m.linear.x),'angular':float(m.angular.z)})
        node=Recorder()
        try:rclpy.spin(node)
        finally:
            node.destroy_node();rclpy.shutdown()

if __name__=='__main__':main()
