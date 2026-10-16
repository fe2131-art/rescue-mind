"""Motion-gated on-site image acquisition; pure Python, no ROS dependency.

Measures actual odometry twist plus position/yaw stability, rather than treating
zero requested velocity as zero physical velocity. Fail closed on malformed or
stale samples. The reported speed is an estimate, not a certified stop sensor.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
from .waypoint import Pose2, wrap

class MotionUnstable(ValueError):
    pass


def odom_planar_twist(msg) -> tuple[float,float]:
    try:
        velocity=msg.twist.twist
        linear=(float(velocity.linear.x),float(velocity.linear.y),float(velocity.linear.z))
        angular=(float(velocity.angular.x),float(velocity.angular.y),float(velocity.angular.z))
        if not all(math.isfinite(v) for v in linear+angular):
            raise MotionUnstable('nonfinite_odom_twist')
        if math.hypot(*linear)>3. or math.hypot(*angular)>6.:
            raise MotionUnstable('implausible_odom_twist')
        return math.hypot(*linear), math.hypot(*angular)
    except (AttributeError,TypeError,ValueError,OverflowError) as exc:
        if isinstance(exc,MotionUnstable):
            raise
        raise MotionUnstable('missing_or_malformed_odom_twist') from exc

@dataclass
class StationaryGate:
    stable_s:float=0.65
    max_linear_mps:float=0.025
    max_angular_rps:float=0.055
    max_drift_m:float=0.020
    max_yaw_drift_rad:float=0.04
    minimum_samples:int=4
    origin:Pose2 | None=None
    anchor_time:float | None=None
    last_time:float | None=None
    samples:int=0
    resets:int=0
    locked:bool=False

    def __post_init__(self):
        numbers=(self.stable_s,self.max_linear_mps,self.max_angular_rps,
                 self.max_drift_m,self.max_yaw_drift_rad)
        if not all(type(x) in (float,int) and math.isfinite(x) and x>0 for x in numbers):
            raise ValueError('bad stationarity thresholds')
        if type(self.minimum_samples)!=int or self.minimum_samples<3:
            raise ValueError('minimum 3 distinct odometry samples')

    def _within(self, pose:Pose2, linear:float, angular:float) -> bool:
        return (self.origin is not None and
                math.hypot(pose.x-self.origin.x,pose.y-self.origin.y)<=self.max_drift_m and
                abs(wrap(pose.yaw-self.origin.yaw))<=self.max_yaw_drift_rad and
                0<=linear<=self.max_linear_mps and 0<=angular<=self.max_angular_rps)

    def observe(self, pose:Pose2, linear:float, angular:float, now:float) -> bool:
        if not isinstance(pose,Pose2) or not all(type(x) in (float,int) and math.isfinite(x)
               for x in (linear,angular,now)) or linear<0 or angular<0:
            raise MotionUnstable('invalid_stationary_sample')
        if self.last_time is not None and now<=self.last_time:
            raise MotionUnstable('nonadvancing_stationary_sample_time')
        self.last_time=now
        if self.locked:
            if not self._within(pose,linear,angular):
                raise MotionUnstable('physical_motion_after_stationary_lock')
            self.samples+=1
            return True
        if self.origin is None or not self._within(pose,linear,angular):
            self.resets+=int(self.origin is not None)
            self.origin=pose
            self.anchor_time=now
            self.samples=1 if linear<=self.max_linear_mps and angular<=self.max_angular_rps else 0
            return False
        self.samples+=1
        if self.samples>=self.minimum_samples and now-self.anchor_time>=self.stable_s:
            self.locked=True
        return self.locked

    def report(self) -> dict:
        if not self.locked or self.origin is None:
            raise MotionUnstable('stationary_gate_not_satisfied')
        return {'stable_elapsed_s':round(self.last_time-self.anchor_time,4),
                'sample_count':self.samples,'reset_count':self.resets,
                'max_linear_mps':self.max_linear_mps,
                'max_angular_rps':self.max_angular_rps,
                'max_drift_m':self.max_drift_m,
                'max_yaw_drift_rad':self.max_yaw_drift_rad}
