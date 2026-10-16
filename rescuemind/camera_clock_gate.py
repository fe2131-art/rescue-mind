"""Validate ROS camera image acquisition stamps against *current Gazebo sim time*.

ROS Image.header.stamp alone increasing does NOT prove it is close to the
current simulation instant: a delayed bridge/queue can deliver old but
monotonically stamped frames.  Use `/clock` as a second independent ROS topic.

This is a fail-closed freshness heuristic, not a time-synchronization proof:
ROS graph publishers may be spoofed, and thresholds need calibration on the
user's real Gazebo machine. Host monotonic time is used only for stall timeouts.
"""
from dataclasses import dataclass
import math
from .frame_freshness import frame_stamp_ns
from .sim_clock_contract import stamp_ns, ClockContractError

class CameraClockRejected(ValueError):
    pass

@dataclass
class CameraClockGate:
    max_camera_lag_s: float = 1.2
    max_camera_lead_s: float = 0.25
    max_clock_idle_s: float = 0.9
    last_clock_ns: int | None = None
    last_clock_wall: float | None = None
    last_advance_wall: float | None = None
    clock_advances: int = 0
    rejected_count: int = 0

    def __post_init__(self):
        values = (self.max_camera_lag_s,self.max_camera_lead_s,self.max_clock_idle_s)
        if not all(type(v) in (float,int) and math.isfinite(v) and 0 < v <= 30 for v in values):
            raise CameraClockRejected('invalid_camera_clock_parameters')

    def clock(self, sec: int, nanosec: int, wall_s: float) -> None:
        if not isinstance(wall_s,(int,float)) or isinstance(wall_s,bool) or not math.isfinite(wall_s):
            raise CameraClockRejected('invalid_clock_wall_time')
        try: n = stamp_ns(sec,nanosec)
        except ClockContractError as exc: raise CameraClockRejected('invalid_ros_clock_stamp') from exc
        if self.last_clock_wall is not None and wall_s <= self.last_clock_wall:
            raise CameraClockRejected('clock_callback_time_nonadvancing')
        if self.last_clock_ns is not None and n < self.last_clock_ns:
            raise CameraClockRejected('gazebo_clock_rewound')
        if self.last_clock_ns is not None and n > self.last_clock_ns:
            self.clock_advances += 1
            self.last_advance_wall = wall_s
        # Repeated sim time is not an advance. Updating last callback time is
        # okay: a separate sim-time forward-progress condition is required.
        self.last_clock_ns = n
        self.last_clock_wall = wall_s

    def check_frame(self,msg,wall_s:float) -> dict:
        def reject(reason):
            self.rejected_count += 1
            raise CameraClockRejected(reason)
        if not isinstance(wall_s,(int,float)) or isinstance(wall_s,bool) or not math.isfinite(wall_s):
            reject('invalid_frame_receive_time')
        if self.last_clock_ns is None or self.last_clock_wall is None:
            reject('no_gazebo_clock')
        if self.clock_advances < 2:
            reject('gazebo_clock_not_advancing')
        age_wall=wall_s-self.last_clock_wall
        progress_idle=(wall_s-self.last_advance_wall) if self.last_advance_wall is not None else math.inf
        if age_wall < 0 or progress_idle < 0 or progress_idle > self.max_clock_idle_s:
            reject('gazebo_clock_stalled_or_wall_regressed')
        frame_ns=frame_stamp_ns(msg)
        if frame_ns is None:
            reject('invalid_camera_ros_stamp')
        delta_s=(self.last_clock_ns-frame_ns)/1e9
        if delta_s > self.max_camera_lag_s:
            reject('camera_acquisition_too_old_for_sim_clock')
        if delta_s < -self.max_camera_lead_s:
            reject('camera_acquisition_ahead_of_sim_clock')
        return {'basis':'Gazebo_clock_vs_camera_ROS_stamp',
                'camera_lag_to_sim_clock_s':round(delta_s,4),
                'sim_clock_ns':self.last_clock_ns,
                'camera_ros_stamp_ns':frame_ns,
                'clock_callback_idle_s':round(age_wall,4),
                'clock_progress_idle_s':round(progress_idle,4),
                'clock_advances':self.clock_advances,
                'limits_s':{'max_lag':self.max_camera_lag_s,
                            'max_lead':self.max_camera_lead_s,
                            'max_clock_idle':self.max_clock_idle_s}}
