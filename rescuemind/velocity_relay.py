"""Fail-closed simulation velocity relay; deterministic core without ROS.

The controller publishes requested velocity to /rescuemind/cmd_vel_request.
Only the independent relay is intended to publish /cmd_vel (Gazebo bridge).
It sends ZERO on every 100ms timer tick unless all sensors/command are fresh.
A fault latches until process restart. This is NOT a physical safety device.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import math
from .watchdog import Watchdog
from .camera_watch import CameraWatch
from .odom_health import OdomHealth


@dataclass(frozen=True)
class RelayDecision:
    ready: bool
    linear: float
    angular: float
    reason: str


@dataclass
class VelocityRelay:
    started_at: float
    cmd_max_age_s: float = 0.45
    odom_max_age_s: float = 1.0
    camera_max_age_s: float = 2.0
    scan_max_age_s: float = 1.0
    max_linear: float = 0.30
    max_angular: float = 1.30
    min_front_m: float = 0.26
    latch_stale_zero: bool = False   # True = pre-v3.4 behaviour (for A/B tests)
    last_odom_at: float | None = None
    last_cmd_at: float | None = None
    last_cmd: tuple[float, float] = (0., 0.)
    latched: str | None = None
    camera: CameraWatch = field(init=False)
    scan: Watchdog = field(init=False)
    odom_health: OdomHealth = field(default_factory=OdomHealth)

    def __post_init__(self):
        parameters=(self.started_at,self.cmd_max_age_s,self.odom_max_age_s,
                    self.camera_max_age_s,self.scan_max_age_s,self.max_linear,
                    self.max_angular,self.min_front_m)
        if not all(math.isfinite(v) for v in parameters):
            raise ValueError('non-finite velocity relay parameter')
        if not (0 < self.cmd_max_age_s <= 2 and 0 < self.odom_max_age_s <= 5 and
                0 < self.camera_max_age_s <= 5 and 0 < self.scan_max_age_s <= 5 and
                0 < self.max_linear <= 2 and 0 < self.max_angular <= 5 and self.min_front_m > 0):
            raise ValueError('invalid relay timing or speed limit')
        self.camera=CameraWatch(self.started_at,self.camera_max_age_s, startup_grace_s=0)
        self.scan=Watchdog(started_at=self.started_at,min_front_m=self.min_front_m,
                           max_scan_age_s=self.scan_max_age_s,startup_grace_s=0)

    def _validate_clock(self, now):
        if not math.isfinite(now) or now < self.started_at:
            self.latched='invalid_monotonic_time'
            return False
        return True

    def odometry(self, now: float, msg=None):
        if not self._validate_clock(now): return
        if msg is not None:
            failure=self.odom_health.observe(msg)
            if failure:
                self.latched=failure
                return
        if self.last_odom_at is not None and now < self.last_odom_at:
            self.latched='regressed_odom_receive_time'
        else:
            self.last_odom_at=now

    def camera_frame(self, frame, now: float):
        if not self._validate_clock(now): return
        self.camera.observe(frame,now)
        if self.camera.latched_reason:
            self.latched='camera_'+self.camera.latched_reason

    def laser_scan(self, msg, now: float):
        if not self._validate_clock(now): return
        self.scan.update_scan(msg.ranges,msg.angle_min,msg.angle_increment,
                              msg.range_min,msg.range_max,now)
        if self.scan.latched_reason:
            self.latched='scan_'+self.scan.latched_reason

    def emergency_stop(self, pressed: bool):
        if pressed: self.latched='operator_estop'

    def request(self, linear: float, angular: float, now: float):
        if not self._validate_clock(now): return
        if not all(type(x) in (int,float) and math.isfinite(x) for x in (linear,angular)):
            self.latched='invalid_velocity_request'; return
        # LiDAR safety zone covers the forward-facing corridor only.  A negative
        # linear command would drive into unobserved space behind the robot.
        if linear < 0:
            self.latched='reverse_motion_unmonitored'; return
        if linear>self.max_linear or abs(angular)>self.max_angular:
            self.latched='request_exceeds_speed_limit'; return
        self.last_cmd=(float(linear),float(angular))
        self.last_cmd_at=now

    def _sensors_ready(self, now: float) -> tuple[bool,str]:
        if self.latched:return False,self.latched
        if not self._validate_clock(now):return False,self.latched or 'invalid_clock'
        if self.scan.last_scan_at is None:return False,'scan_not_received'
        if self.camera.last_advanced_at is None:return False,'camera_not_received'
        if self.last_odom_at is None:return False,'odom_not_received'
        if self.scan.check(now):
            self.latched='scan_'+self.scan.latched_reason
        elif self.camera.check(now):
            self.latched='camera_'+self.camera.latched_reason
        elif now<self.last_odom_at or now-self.last_odom_at>self.odom_max_age_s:
            self.latched='stale_odometry'
        if self.latched:return False,self.latched
        return True,'ready'

    def ready(self, now: float)->bool:
        return self._sensors_ready(now)[0]

    def decide(self, now: float)->RelayDecision:
        ok,why=self._sensors_ready(now)
        if not ok:return RelayDecision(False,0.,0.,why)
        if self.last_cmd_at is None:
            return RelayDecision(True,0.,0.,'awaiting_command')
        if now<self.last_cmd_at or now-self.last_cmd_at>self.cmd_max_age_s+1e-9:
            # I-09: a stale ZERO request is not a hazard (the output is zero either way);
            # hold zero without latching so a brief planner stall while stationary does
            # not abort the mission.  A stale MOTION request still latches immediately.
            if self.latch_stale_zero or now<self.last_cmd_at or self.last_cmd!=(0.,0.):
                self.latched='stale_velocity_command'
                return RelayDecision(False,0.,0.,self.latched)
            return RelayDecision(True,0.,0.,'stale_zero_request_hold')
        return RelayDecision(True,*self.last_cmd,'command_fresh')


def planar_request_components(msg) -> tuple[float, float]:
    """Reject off-axis Twist fields even when forward/yaw components are valid."""
    values = (msg.linear.x, msg.linear.y, msg.linear.z,
              msg.angular.x, msg.angular.y, msg.angular.z)
    if not all(type(x) in (int,float) and math.isfinite(x) for x in values):
        raise ValueError('invalid_nonfinite_twist')
    if any(abs(x) > 1e-9 for x in (msg.linear.y,msg.linear.z,msg.angular.x,msg.angular.y)):
        raise ValueError('nonplanar_twist_request')
    return float(msg.linear.x),float(msg.angular.z)
