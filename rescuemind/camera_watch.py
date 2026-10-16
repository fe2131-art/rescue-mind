"""Monitor ROS Image acquisition timestamps *and* wall-clock freshness.

A valid timestamp alone cannot show the camera is still producing frames.
Only strictly increasing acquisition stamps refresh the heartbeat, so a replayed
frame cannot keep a mission alive. This is simulation-only fail-stop monitoring;
it is not a safety-certified physical interlock.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from .frame_freshness import frame_stamp_ns


@dataclass
class CameraWatch:
    started_at: float
    max_age_s: float = 3.0
    startup_grace_s: float = 4.0
    last_stamp_ns: int | None = None
    last_advanced_at: float | None = None
    latched_reason: str | None = None

    def __post_init__(self):
        if not (isfinite(self.started_at) and isfinite(self.max_age_s) and self.max_age_s > 0
                and isfinite(self.startup_grace_s) and self.startup_grace_s >= 0):
            raise ValueError('invalid camera watchdog configuration')

    def observe(self, msg, now: float):
        if self.latched_reason:
            return
        stamp = frame_stamp_ns(msg)
        if not isfinite(now) or now < self.started_at:
            self.latched_reason = 'invalid_camera_clock'
        elif stamp is None:
            self.latched_reason = 'invalid_camera_stamp'
        elif self.last_stamp_ns is not None and stamp < self.last_stamp_ns:
            self.latched_reason = 'regressed_camera_stamp'
        elif self.last_stamp_ns is None or stamp > self.last_stamp_ns:
            self.last_stamp_ns = stamp
            self.last_advanced_at = now
        # Identical image timestamps are duplicates and DO NOT refresh activity.

    def check(self, now: float) -> str | None:
        if self.latched_reason:
            return self.latched_reason
        if not isfinite(now) or now < self.started_at:
            self.latched_reason = 'invalid_camera_clock'
        elif self.last_advanced_at is None:
            if now-self.started_at > self.startup_grace_s:
                self.latched_reason = 'no_camera_frames'
        elif now < self.last_advanced_at or now-self.last_advanced_at > self.max_age_s:
            self.latched_reason = 'stale_camera_frames'
        return self.latched_reason
