"""Offline configuration checks: explicit topic directions + world clock source.

Static validation only. Does NOT assert Gazebo plugins actually publish messages.
"""
from pathlib import Path
import xml.etree.ElementTree as ET
import yaml

EXPECTED = {
    '/clock':('/world/rescuemind_arena/clock','rosgraph_msgs/msg/Clock','gz.msgs.Clock','GZ_TO_ROS'),
    '/cmd_vel':('/cmd_vel','geometry_msgs/msg/Twist','gz.msgs.Twist','ROS_TO_GZ'),
    '/odom':('/odom','nav_msgs/msg/Odometry','gz.msgs.Odometry','GZ_TO_ROS'),
    '/scan':('/scan','sensor_msgs/msg/LaserScan','gz.msgs.LaserScan','GZ_TO_ROS'),
    '/camera':('/camera','sensor_msgs/msg/Image','gz.msgs.Image','GZ_TO_ROS'),
    '/ground_truth/odom':('/ground_truth/odom','nav_msgs/msg/Odometry','gz.msgs.Odometry','GZ_TO_ROS'),
}

def audit(world_path, bridge_yaml):
    root=ET.parse(world_path).getroot()
    world=root.find('world')
    if world is None or world.get('name')!='rescuemind_arena':
        raise ValueError('world name does not match clock mapping')
    raw=yaml.safe_load(Path(bridge_yaml).read_text(encoding='utf8'))
    if not isinstance(raw,list) or len(raw)!=len(EXPECTED):
        raise ValueError('missing or extra bridge topic entries')
    rows={}
    for entry in raw:
        if not isinstance(entry,dict):raise ValueError('invalid mapping row')
        name=entry.get('ros_topic_name')
        if not isinstance(name,str) or name in rows:
            raise ValueError('duplicate/invalid ROS topic mapping')
        rows[name]=entry
    for name,exp in EXPECTED.items():
        row=rows.get(name)
        if row is None or tuple(row.get(key) for key in ('gz_topic_name','ros_type_name','gz_type_name','direction'))!=exp:
            raise ValueError('incorrect ROS/Gazebo mapping for '+name)
    topics={elem.text for elem in root.findall('.//topic')} | {elem.text for elem in root.findall('.//odom_topic')}
    if not {'/cmd_vel','/odom','/scan','/camera'}.issubset(topics):
        raise ValueError('SDF does not declare expected Gazebo topics')
    return {'ok':True,'scope':'STATIC_CONFIG_NOT_LIVE_GAZEBO',
            'world':world.get('name'),'topic_mappings':len(rows),
            'simulation_clock_ros_topic':'/clock',
            'gazebo_clock_source':'/world/rescuemind_arena/clock'}
