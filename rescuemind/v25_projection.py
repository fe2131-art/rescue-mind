"""Geometry-only screening of object center in ideal pinhole camera FOV.

Not an image-visibility or occlusion check. Does not claim VLM accuracy.
Coordinates are based on locked SDF visual centers and camera mount pose.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
from .camera_aim import station_centers

PROPS={'water':('sealed_water_bottles',.71), 'medicine':('first_aid_case',.68)}

def estimate_projection(root:Path, scene:str='nominal')->dict:
    if scene not in ('nominal','swapped','empty'):raise ValueError('unknown scene')
    sdf=Path(root)/'worlds/scenarios'/f'rescuemind_{scene}.sdf'
    world=ET.parse(sdf).getroot().find('world')
    if world is None:raise ValueError('world not found')
    rover=[m for m in world.findall('model') if m.get('name')=='rescue_bot']
    if len(rover)!=1:
        # tolerate actual SDF model naming; caller records it
        rover=[m for m in world.findall('model') if m.find('.//sensor[@name="front_camera"]') is not None]
    if len(rover)!=1:raise ValueError('robot model not uniquely found')
    robot=rover[0]
    sensor=robot.find('.//sensor[@name="front_camera"]')
    if sensor is None:raise ValueError('camera not found')
    cam_p=list(map(float,sensor.findtext('pose').split()))
    base_p=list(map(float,robot.findtext('pose').split()))
    h_fov=float(sensor.findtext('./camera/horizontal_fov'))
    width=float(sensor.findtext('./camera/image/width'))
    height=float(sensor.findtext('./camera/image/height'))
    v_fov=2*math.atan(math.tan(h_fov/2)*height/width)
    poses=json.loads((Path(root)/'configs/gazebo_waypoints.json').read_text())
    centers=station_centers(json.loads((Path(root)/'configs/gazebo_station_centers.json').read_text()))
    outputs={}
    for item in ('water','medicine'):
        contents=({'water':'water','medicine':'medicine'} if scene=='nominal' else
                  {'water':'medicine','medicine':'water'} if scene=='swapped' else {})
        if item not in contents:
            outputs[item]={'present':False,'condition':scene}
            continue
        actual_item=contents[item]
        name,z=PROPS[actual_item]
        station=centers[item]
        sx,sy=poses[item]
        yaw=math.atan2(station[1]-sy,station[0]-sx)
        cx=sx+cam_p[0]*math.cos(yaw)-cam_p[1]*math.sin(yaw)
        cy=sy+cam_p[0]*math.sin(yaw)+cam_p[1]*math.cos(yaw)
        cz=base_p[2]+cam_p[2]
        actual=next((m for m in world.findall('model') if m.get('name')==name),None)
        if actual is None:
            outputs[item]={'present':False,'condition':scene}
            continue
        xy=list(map(float,actual.findtext('pose').split()[:2]))
        dx=xy[0]-cx;dy=xy[1]-cy
        h_offset=math.atan2(dy,dx)-yaw
        h_offset=math.atan2(math.sin(h_offset),math.cos(h_offset))
        elev=math.atan2(z-cz,math.hypot(dx,dy)) + cam_p[4]  # negative camera pitch is upward
        outputs[item]={'present':True,'object_in_view':actual_item,'bearing_offset_rad':round(h_offset,4),
                       'elevation_rad':round(elev,4),
                       'center_inside_fov_with_margin':abs(h_offset)<h_fov/2-.08 and abs(elev)<v_fov/2-.06}
    return {'kind':'IDEAL_PINHOLE_STATIC_NOT_RENDERED_IMAGE','scenario':scene,
            'horizontal_fov_rad':h_fov,'vertical_fov_rad':round(v_fov,4),
            'assumes_robot_aims_at_station':True, 'objects':outputs}
