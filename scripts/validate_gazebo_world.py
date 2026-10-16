"""Static Gazebo world/ROS bridge interface and viewpoint checks, NOT a runtime test."""
from __future__ import annotations
import json
from math import atan2, hypot, pi
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.waypoint import simulate_route, wrap
from rescuemind.arena_geometry import check_route


def inspect_world(sdf_path=ROOT/'worlds/rescuemind_test_arena.sdf',
                  config_path=ROOT/'configs/gazebo_waypoints.json'):
    root=ET.parse(sdf_path).getroot()
    world=root.find('world')
    assert world is not None and world.attrib.get('name')=='rescuemind_arena'
    robot=world.find("model[@name='rescue_diffbot']")
    assert robot is not None
    plugin=robot.find("plugin[@name='gz::sim::systems::DiffDrive']")
    assert plugin is not None
    for tag,val in [('left_joint','left_wheel_joint'),('right_joint','right_wheel_joint'),
                    ('topic','/cmd_vel'),('odom_topic','/odom')]:
        assert plugin.findtext(tag)==val, f'DiffDrive {tag} mismatch'
    link=robot.find("link[@name='base_link']")
    sensors={s.get('type'):s for s in link.findall('sensor')}
    assert sensors['camera'].findtext('topic')=='/camera'
    assert sensors['gpu_lidar'].findtext('topic')=='/scan'
    assert all(s.findtext('update_rate') and float(s.findtext('update_rate'))>=5 for s in sensors.values())
    from rescuemind.bridge_contract import audit
    assert audit(sdf_path, ROOT/'configs/ros_gz_bridge_v20.yaml')['ok']
    assert 'ros_gz_bridge_v20.yaml' in (ROOT/'scripts/bridge_direct_gazebo.sh').read_text()
    positions=json.loads(Path(config_path).read_text())
    results={}
    for supply,station in [('water',(2.,2.)),('medicine',(-2.,2.))]:
        goal=positions[supply]
        sim=simulate_route([goal])
        x,y,yaw=sim['final']
        bearing=atan2(station[1]-y,station[0]-x)
        relative=abs(wrap(bearing-yaw))
        distance=hypot(station[0]-x,station[1]-y)
        # Horizontal FOV = 1.05 rad, camera front offset .22 m.
        assert relative < .525, f'{supply} supply outside camera horizontal FOV under ideal kinematics'
        assert distance > .65, f'{supply} robot too close to shelf in ideal kinematics'
        route_clearance=check_route([positions[supply],positions['B']])
        # We expose measured margins, don't treat ideal geometry as proof of real Gazebo contact safety.
        results[supply]={'last_pose':[x,y,yaw], 'supply_range_m':round(distance,3),
                         'camera_relative_yaw_deg':round(relative*180/pi,2),
                         'horizontal_fov_check':True,'straight_segment_clearance':route_clearance}
    return {'status':'PASS','kind':'STATIC_SCENE_CONTRACT_NOT_SIMULATOR_EXECUTION',
            'world':str(Path(sdf_path).name),'topics':['/cmd_vel','/odom','/scan','/camera'],
            'viewpoint_checks':results}

if __name__=='__main__':
    obj=inspect_world()
    target=ROOT/'outputs/release/v09_static_scene_contract.json'
    target.parent.mkdir(exist_ok=True,parents=True)
    target.write_text(json.dumps(obj,ensure_ascii=False,indent=2))
    print(json.dumps(obj,ensure_ascii=False,indent=2))
