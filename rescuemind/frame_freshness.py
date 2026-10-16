"""Gazebo/ROS camera acquisition-time freshness, independent of callback time.

Receiving an old ROS Image after a waypoint does not mean the image was shot
there. Require a positive simulator-time header stamp strictly newer than the
last pre-arrival observation AND a callback after the stationary dwell.
"""
from __future__ import annotations
from dataclasses import dataclass


def frame_stamp_ns(msg) -> int | None:
    """Return a valid ROS header stamp in nanoseconds, otherwise None."""
    try:
        stamp=msg.header.stamp
        sec,nsec=int(stamp.sec),int(stamp.nanosec)
        if sec < 0 or not 0 <= nsec < 1_000_000_000:
            return None
        result=sec*1_000_000_000+nsec
        return result if result>0 else None
    except (AttributeError,TypeError,ValueError,OverflowError):
        return None


@dataclass
class FrameSequence:
    last_stamp_ns: int | None = None
    invalid_or_regressed: bool = False

    def observe(self, msg) -> int | None:
        stamp=frame_stamp_ns(msg)
        if stamp is None or (self.last_stamp_ns is not None and stamp < self.last_stamp_ns):
            self.invalid_or_regressed=True
        elif not self.invalid_or_regressed:
            self.last_stamp_ns=stamp
        return stamp

    def eligible(self, arrival_stamp_ns: int | None, received_wall: float | None,
                 minimum_wall: float) -> bool:
        return (not self.invalid_or_regressed and
                arrival_stamp_ns is not None and
                self.last_stamp_ns is not None and
                self.last_stamp_ns > arrival_stamp_ns and
                received_wall is not None and received_wall > minimum_wall)
