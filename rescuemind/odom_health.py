"""Strict odometry payload and acquisition-stamp checks for the simulator speed guard.

Guard validation is independent of ROS imports for deterministic tests.  All
validation below happens at runtime, not just once in a startup probe.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
from .frame_freshness import frame_stamp_ns

@dataclass
class OdomHealth:
    last_stamp_ns: int | None = None
    last_position: tuple[float, float, float] | None = None
    odom_frame: str = 'odom'          # I-26: the suffix header.frame_id must end with (default: unchanged)
    base_frame: str = 'base_link'     # I-26: the suffix child_frame_id must end with (default: unchanged)

    def observe(self, msg) -> str | None:
        try:
            p=msg.pose.pose.position
            q=msg.pose.pose.orientation
            pos=(p.x,p.y,p.z)
            quat=(q.x,q.y,q.z,q.w)
            if any(type(v) not in (float,int) or not math.isfinite(v) for v in pos+quat):
                return "invalid_odom_numeric"
            norm=sum(v*v for v in quat)
            if not (0.9 < norm < 1.1):
                return "invalid_odom_quaternion"
            if not (str(msg.header.frame_id).endswith(self.odom_frame) and str(msg.child_frame_id).endswith(self.base_frame)):
                return "invalid_odom_frames"
            stamp=frame_stamp_ns(msg)
            if stamp is None:
                return "invalid_odom_timestamp"
            if self.last_stamp_ns is not None and stamp < self.last_stamp_ns:
                return "regressed_odom_timestamp"
            # Repeated simulator time may be produced when the simulation is paused;
            # a repeated stamp must not refresh the heartbeat indefinitely.
            if self.last_stamp_ns == stamp:
                return "repeated_odom_timestamp"
            self.last_stamp_ns=stamp
            self.last_position=tuple(float(x) for x in pos)
            return None
        except (AttributeError,TypeError,ValueError,OverflowError):
            return "malformed_odom"
