"""Simulation-only ROS LiDAR / operator E-stop fail-closed watchdog logic.

Not certified safety equipment. Designed for offline property tests and
Nav2 cancellation on close obstacle or loss of scan heartbeat.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite, isinf

@dataclass
class Watchdog:
    min_front_m: float = 0.30
    max_scan_age_s: float = 2.0
    startup_grace_s: float = 4.0
    started_at: float = 0.0
    last_scan_at: float | None = None
    last_front_m: float | None = None
    latched_reason: str | None = None

    def update_scan(self, ranges, angle_min: float, angle_increment: float,
                    range_min: float, range_max: float, now: float, half_angle: float = 0.52):
        if self.latched_reason:
            return
        if not (isfinite(angle_min) and isfinite(angle_increment) and angle_increment > 0):
            self.latched_reason = 'invalid_scan_geometry'
            return
        if not (isfinite(range_min) and isfinite(range_max) and 0 <= range_min < range_max):
            self.latched_reason = 'invalid_scan_range'
            return
        valid = []
        # ROS LaserScan: +inf is a legitimate no-return beyond max range; NaN
        # and -inf are NOT evidence of free space. A scan with only +inf is
        # still observable when valid geometry, heartbeat and a front arc exist.
        front_beams = 0
        for i, r in enumerate(ranges):
            if abs(angle_min + i * angle_increment) > half_angle:
                continue
            front_beams += 1
            # A measurement below range_min is conservatively treated as too close.
            if isinstance(r, (int, float)) and isfinite(r):
                if r < range_min:
                    self.latched_reason = 'front_range_below_sensor_min'
                    return
                if r <= range_max:
                    valid.append(float(r))
            elif isinstance(r, (int, float)) and isinf(r) and r > 0:
                valid.append(float(range_max))
        self.last_scan_at = now
        if not front_beams or not valid:
            self.latched_reason = 'front_scan_unobservable'
            return
        self.last_front_m = min(valid)
        if self.last_front_m < self.min_front_m:
            self.latched_reason = 'front_obstacle_too_close'

    def emergency_stop(self, pressed: bool):
        if pressed:
            self.latched_reason = 'operator_emergency_stop'

    def check(self, now: float) -> str | None:
        if self.latched_reason:
            return self.latched_reason
        if self.last_scan_at is None:
            if now - self.started_at > self.startup_grace_s:
                self.latched_reason = 'no_lidar_scan'
        elif now - self.last_scan_at > self.max_scan_age_s or now < self.last_scan_at:
            self.latched_reason = 'stale_lidar_scan'
        return self.latched_reason
