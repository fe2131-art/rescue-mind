"""Read-only cross-check of Gazebo Transport, SDF and ROS-GZ bridge.

This module does NOT validate the content of ROS sensor messages, physics motion,
or safety of actual hardware. It is a prerequisite for the existing ROS checks.
"""
from __future__ import annotations
from pathlib import Path
import xml.etree.ElementTree as ET
import yaml

EXPECTED = {
    '/world/rescuemind_arena/clock': ('/clock', 'rosgraph_msgs/msg/Clock', 'gz.msgs.Clock', 'GZ_TO_ROS'),
    '/odom': ('/odom', 'nav_msgs/msg/Odometry', 'gz.msgs.Odometry', 'GZ_TO_ROS'),
    '/scan': ('/scan', 'sensor_msgs/msg/LaserScan', 'gz.msgs.LaserScan', 'GZ_TO_ROS'),
    '/camera': ('/camera', 'sensor_msgs/msg/Image', 'gz.msgs.Image', 'GZ_TO_ROS'),
    '/cmd_vel': ('/cmd_vel', 'geometry_msgs/msg/Twist', 'gz.msgs.Twist', 'ROS_TO_GZ'),
    '/ground_truth/odom': ('/ground_truth/odom', 'nav_msgs/msg/Odometry', 'gz.msgs.Odometry', 'GZ_TO_ROS'),
}
PUBLISHED = frozenset(EXPECTED) - {'/cmd_vel'}  # cmd_vel is subscriber-only until bridge is live

class GazeboContractError(ValueError):
    pass


def validate_static(world_path: str | Path, bridge_path: str | Path) -> dict:
    """Check exact names, SDF plugin systems and bridge type/direction."""
    try:
        world = ET.parse(world_path).getroot().find('world')
        if world is None or world.get('name') != 'rescuemind_arena':
            raise GazeboContractError('unexpected world name')
        mappings = yaml.safe_load(Path(bridge_path).read_text(encoding='utf-8'))
        if not isinstance(mappings, list) or len(mappings) != len(EXPECTED):
            raise GazeboContractError('bridge mappings count mismatch')
        by_gz = {}
        for entry in mappings:
            if not isinstance(entry, dict):
                raise GazeboContractError('invalid YAML bridge entry')
            key = entry.get('gz_topic_name')
            if key in by_gz:
                raise GazeboContractError('duplicated Gazebo bridge topic')
            by_gz[key] = entry
        for topic, expected in EXPECTED.items():
            entry = by_gz.get(topic)
            if entry is None or tuple(entry.get(k) for k in ('ros_topic_name', 'ros_type_name', 'gz_type_name', 'direction')) != expected:
                raise GazeboContractError('bridge mismatch: '+topic)
        plugin_names = [p.get('name') for p in world.iter('plugin')]
        for name in ('gz::sim::systems::Physics', 'gz::sim::systems::Sensors', 'gz::sim::systems::DiffDrive'):
            if name not in plugin_names:
                raise GazeboContractError('missing SDF system: '+name)
        robot = next((m for m in world.findall('model') if m.get('name') == 'rescue_diffbot'), None)
        if robot is None:
            raise GazeboContractError('missing rescue_diffbot model')
        for sensor_kind, topic in (('camera','/camera'),('gpu_lidar','/scan')):
            found = [s for s in robot.iter('sensor') if s.get('type') == sensor_kind and (s.findtext('topic') or '').strip() == topic]
            if len(found) != 1:
                raise GazeboContractError('missing/duplicate sensor: '+sensor_kind+' '+topic)
        drives = [p for p in robot.iter('plugin') if p.get('name') == 'gz::sim::systems::DiffDrive']
        if len(drives) != 1 or drives[0].findtext('topic') != '/cmd_vel' or drives[0].findtext('odom_topic') != '/odom':
            raise GazeboContractError('DiffDrive odom/cmd topic mismatch')
    except (ET.ParseError, OSError, yaml.YAMLError, TypeError) as e:
        raise GazeboContractError('cannot inspect SDF/YAML contract: '+str(e)) from e
    return {'ok': True, 'scope': 'STATIC_WORLD_BRIDGE_WIRING_ONLY', 'world': world.get('name'), 'mappings':len(by_gz)}


def parse_topic_list(text: str) -> set[str]:
    """`gz topic -l` normally emits a single absolute topic per line."""
    if not isinstance(text, str):
        raise GazeboContractError('non-text Gazebo topic output')
    topics = set()
    for line in text.splitlines():
        value = line.strip()
        if not value:
            continue
        if not value.startswith('/') or any(c.isspace() for c in value):
            raise GazeboContractError('unexpected `gz topic -l` output line: '+value[:100])
        topics.add(value)
    if not topics:
        raise GazeboContractError('empty Gazebo topic list')
    return topics


def audit_runtime_topics(text: str, *, expected: frozenset[str] = PUBLISHED) -> dict:
    topics = parse_topic_list(text)
    missing = sorted(expected - topics)
    return {'ok':not missing, 'scope':'GAZEBO_TRANSPORT_TOPIC_NAMES_NOT_SENSOR_DATA_OR_PHYSICS',
            'observed_count':len(topics), 'observed_required': sorted(topics & expected),
            'missing':missing}
