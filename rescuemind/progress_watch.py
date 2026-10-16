"""Detect a simulated mobile base failing to translate under sustained forward commands.

Safety-related experimental software ONLY. Does not replace physical E-stop or
Nav2 costmap/avoidance. Turn-in-place and commanded stop do not count as stall.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import hypot, isfinite
from .waypoint import Pose2

@dataclass
class ProgressWatch:
    min_forward_mps: float = .06
    min_translation_m: float = .045
    max_stall_s: float = 9.0
    anchor_xy: tuple[float, float] | None = None
    anchor_at: float | None = None
    latched_reason: str | None = None

    def update(self, pose: Pose2, forward: float, now: float) -> str | None:
        if self.latched_reason:
            return self.latched_reason
        if not all(isfinite(v) for v in (forward, now)):
            self.latched_reason = 'invalid_drive_progress_input'
            return self.latched_reason
        if self.anchor_at is not None and now < self.anchor_at:
            self.latched_reason = 'clock_regression'
            return self.latched_reason
        if forward < self.min_forward_mps:
            self.anchor_at = None
            self.anchor_xy = None
            return None
        if self.anchor_at is None:
            self.anchor_at = now
            self.anchor_xy = (pose.x, pose.y)
            return None
        if hypot(pose.x-self.anchor_xy[0],pose.y-self.anchor_xy[1]) >= self.min_translation_m:
            self.anchor_at = now
            self.anchor_xy = (pose.x,pose.y)
            return None
        if now-self.anchor_at > self.max_stall_s:
            self.latched_reason = 'drive_commanded_but_no_translation'
        return self.latched_reason
