"""Cross-file Gazebo/ROS/static contract audit. NOT a Gazebo execution."""
from __future__ import annotations
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def check(root: Path) -> dict:
    root=Path(root)
    issues=[]
    try:
        xml=ET.parse(root/'worlds/rescuemind_test_arena.sdf').getroot()
        models={m.get('name'):m for m in xml.findall('./world/model')}
        bot=models['rescue_diffbot']
        diff=next(p for p in bot.findall('plugin') if p.get('name')=='gz::sim::systems::DiffDrive')
        joints={x.get('name') for x in bot.findall('joint')}
        for tag in ('left_joint','right_joint'):
            if diff.findtext(tag) not in joints:issues.append('missing_'+tag)
        if diff.findtext('topic')!='/cmd_vel':issues.append('diffdrive_cmd_topic_mismatch')
        if diff.findtext('odom_topic')!='/odom':issues.append('diffdrive_odom_topic_mismatch')
        senses={s.findtext('topic'):s for s in bot.findall('.//sensor')}
        if '/camera' not in senses:issues.append('missing_camera_topic')
        if '/scan' not in senses:issues.append('missing_scan_topic')
        if '/camera' in senses and senses['/camera'].get('type')!='camera':issues.append('not_camera')
        if '/scan' in senses and senses['/scan'].get('type') not in ('gpu_lidar','lidar'):issues.append('not_lidar')
        # v2.0 uses a declarative Gazebo<->ROS YAML bridge. Validate its
        # semantics rather than searching old command-line bridge literals.
        yaml_bridge=root/'configs/ros_gz_bridge_v20.yaml'
        if yaml_bridge.exists():
            try:
                from .bridge_contract import audit
                audit(root/'worlds/rescuemind_test_arena.sdf', yaml_bridge)
            except (ValueError,OSError,KeyError) as exc:
                issues.append('bridge_contract_missing:/cmd_vel')
            bridge_sh=(root/'scripts/bridge_direct_gazebo.sh').read_text()
            if 'ros_gz_bridge_v20.yaml' not in bridge_sh:
                issues.append('bridge_script_ignores_yaml')
        else:
            bridge=(root/'scripts/bridge_direct_gazebo.sh').read_text()
            for literal in ('/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist',
                            '/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry',
                            '/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan',
                            '/camera@sensor_msgs/msg/Image[gz.msgs.Image'):
                if literal not in bridge:issues.append('bridge_contract_missing:'+literal.split('@')[0])
        launcher=(root/'scripts/v16_orchestrate.py').read_text()
        if 'start_velocity_guard.sh' not in launcher:issues.append('launcher_bypasses_guard')
        readiness=(root/'scripts/v15_live_readiness.sh').read_text()
        if 'check_guard_topology.sh' not in readiness or 'v15_sensor_probe.sh' not in readiness:
            issues.append('readiness_skips_guard_or_sensors')
        cfg=json.loads((root/'configs/gazebo_waypoints.json').read_text())
        for waypoint,modelname in [('water','aid_station_water'),('medicine','aid_station_medicine'),('B','shelter_B')]:
            coords=cfg[waypoint]
            if len(coords)!=2 or not all(math.isfinite(v) for v in coords):
                issues.append('invalid_waypoint:'+waypoint);continue
            station=models[modelname]
            tokens=(station.findtext('pose') or '').split()
            x,y=map(float,tokens[:2]);sep=math.hypot(coords[0]-x,coords[1]-y)
            if not 0.35 < sep < 1.8:issues.append(f'waypoint_not_an_approach_{waypoint}')
    except (OSError,KeyError,ET.ParseError,TypeError,ValueError,StopIteration) as e:
        issues.append('contract_parse_error:'+type(e).__name__+':'+str(e))
    return {'kind':'STATIC_CONTRACT_ONLY_NOT_GAZEBO','ok':not issues,'issues':issues,
            'checked':['diffdrive/joints','Gazebo sensor topics','ROS bridge message types/directions',
                       'launch guard/readiness ordering','waypoint-to-object geometry']}
