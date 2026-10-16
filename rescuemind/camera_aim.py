"""Fail-closed camera bearing alignment for a fixed Gazebo showcase world.

The aiming targets are SDF station centers, never vision ground-truth labels.
This feature does NOT detect/verify that a target is visible: ROS rendered
images and real VLM inference must still be checked on the user's Ubuntu PC.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import atan2, isfinite, hypot
from .waypoint import Pose2, wrap

@dataclass(frozen=True)
class AimCommand:
    angular: float
    aligned: bool
    bearing_error_rad: float


def aim_at_station(pose:Pose2, station:tuple[float,float],
                   *, tolerance_rad:float=0.10, gain:float=2.0,
                   max_angular:float=0.65)->AimCommand:
    """Rotation only; robot translates zero. Narrow FOV requires heading alignment."""
    if not (isinstance(station, (tuple,list)) and len(station)==2
            and all(type(v) in (float,int) and isfinite(v) for v in station)):
        raise ValueError('invalid station coordinate')
    if not (0<tolerance_rad<0.30 and 0<gain<=5 and 0<max_angular<=1):
        raise ValueError('invalid aiming limits')
    dx=station[0]-pose.x;dy=station[1]-pose.y
    if hypot(dx,dy)<0.45:
        raise ValueError('station too close to estimate safe bearing')
    error=wrap(atan2(dy,dx)-pose.yaw)
    if abs(error)<=tolerance_rad:
        return AimCommand(0.0,True,error)
    return AimCommand(max(-max_angular,min(max_angular,gain*error)),False,error)


def station_centers(config:dict)->dict:
    expected={'water':(2.0,2.0),'medicine':(-2.0,2.0)}
    if not isinstance(config,dict) or set(config)!=set(expected):
        raise ValueError('station centers schema mismatch')
    for key, xy in expected.items():
        if type(config[key])!=list or len(config[key])!=2 or tuple(config[key])!=xy:
            raise ValueError('station centers must match locked SDF geometry')
    return expected
