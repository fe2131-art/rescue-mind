#!/usr/bin/env python3
"""Record Gazebo-rendered frames for the demo video (not part of mission logic).

Subscribes to the spawned overview camera and the robot's own /camera and writes
JPEG frames named by host Unix receipt time, so the video compositor can align
them with mission.json events (mission_start_unix_ns + t_wall_s).  The VLM never
sees the overview camera; this node only observes.
"""
from __future__ import annotations
import argparse
import json
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind.ros_qos import image_qos  # noqa: E402


def to_bgr(msg):
    import numpy as np
    channels = {'rgb8': 3, 'bgr8': 3, 'rgba8': 4, 'bgra8': 4}.get(msg.encoding)
    if channels is None:
        raise ValueError('unsupported encoding ' + msg.encoding)
    arr = np.frombuffer(bytes(msg.data), dtype=np.uint8)
    arr = arr.reshape((msg.height, msg.step))[:, :msg.width * channels].reshape((msg.height, msg.width, channels))
    if msg.encoding.startswith('rgb'):
        arr = arr[:, :, [2, 1, 0]]
    return np.ascontiguousarray(arr[:, :, :3])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', required=True)
    p.add_argument('--film-topic', default='/film_camera_overview')
    p.add_argument('--robot-topic', default='/camera')
    p.add_argument('--quality', type=int, default=88)
    a = p.parse_args(argv)
    import cv2
    import rclpy
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import Image
    from nav_msgs.msg import Odometry
    out = Path(a.out)
    (out / 'film').mkdir(parents=True, exist_ok=True)
    (out / 'robot').mkdir(parents=True, exist_ok=True)
    odom_log = (out / 'odom.jsonl').open('a', encoding='utf-8')
    rclpy.init()
    node = rclpy.create_node('rescuemind_film_recorder')
    counts = {'film': 0, 'robot': 0}

    def writer(kind):
        def callback(msg):
            try:
                frame = to_bgr(msg)
            except ValueError as exc:
                node.get_logger().warning(str(exc))
                return
            stamp = msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec
            name = f'{time.time_ns()}_{stamp}.jpg'
            cv2.imwrite(str(out / kind / name), frame, [cv2.IMWRITE_JPEG_QUALITY, a.quality])
            counts[kind] += 1
        return callback

    def on_odom(msg):
        pose = msg.pose.pose
        odom_log.write(json.dumps({'unix_ns': time.time_ns(), 'x': pose.position.x, 'y': pose.position.y,
                                   'qz': pose.orientation.z, 'qw': pose.orientation.w,
                                   'v': msg.twist.twist.linear.x, 'w': msg.twist.twist.angular.z}) + '\n')

    subs = [node.create_subscription(Image, a.film_topic, writer('film'), image_qos()),
            node.create_subscription(Image, a.robot_topic, writer('robot'), image_qos()),
            node.create_subscription(Odometry, '/odom', on_odom, qos_profile_sensor_data)]
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, Exception):
        pass
    finally:
        _ = subs
        odom_log.close()
        (out / 'counts.json').write_text(json.dumps(counts) + '\n')
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
