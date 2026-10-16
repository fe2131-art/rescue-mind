"""Independent, fail-closed incoming ROS message validation for Gazebo demos.

Validates a *sequence* rather than just `ros2 topic echo --once`. This is an
interface sanity check, not proof of physical safety or camera semantics.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import math
from collections import defaultdict
from .frame_freshness import frame_stamp_ns


@dataclass
class StreamAudit:
    minimum_messages: int = 3
    counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    last_stamps: dict[str, int] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    first_stamps: dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.minimum_messages, int) or self.minimum_messages < 2:
            raise ValueError('need at least two messages per topic to prove stamp advancement')

    def _mark(self, kind: str, msg) -> None:
        stamp = frame_stamp_ns(msg)
        if stamp is None:
            raise ValueError(f'{kind}: invalid or zero acquisition timestamp')
        prev = self.last_stamps.get(kind)
        if prev is not None and stamp < prev:
            raise ValueError(f'{kind}: timestamp regression')
        if prev is not None and stamp == prev:
            # A duplicate sample does not count as another observation.
            return
        self.first_stamps.setdefault(kind, stamp)
        self.last_stamps[kind] = stamp
        self.counts[kind] += 1

    def add_image(self, msg):
        width, height, step = int(msg.width), int(msg.height), int(msg.step)
        channels = {'rgb8': 3, 'bgr8': 3, 'rgba8': 4, 'bgra8': 4, 'mono8': 1}
        if msg.encoding not in channels or not 320 <= width <= 4096 or not 240 <= height <= 4096:
            raise ValueError('camera: unsupported encoding/dimensions')
        if step < width * channels[msg.encoding] or step > width * channels[msg.encoding] + 4096:
            raise ValueError('camera: invalid row stride')
        if len(msg.data) != step * height:
            raise ValueError('camera: truncated or inconsistent bytes')
        if getattr(msg, 'is_bigendian', 0) not in (0, 1):
            raise ValueError('camera: invalid endian flag')
        self._mark('camera', msg)

    def add_scan(self, msg):
        if len(msg.ranges) < 90 or len(msg.ranges) > 10000:
            raise ValueError('scan: implausible beam count')
        finite_meta = (msg.angle_min, msg.angle_max, msg.angle_increment, msg.range_min, msg.range_max)
        if not all(isinstance(x, (float, int)) and math.isfinite(x) for x in finite_meta):
            raise ValueError('scan: invalid metadata')
        if not (msg.angle_increment > 0 and msg.angle_max > msg.angle_min and
                0 < msg.range_min < msg.range_max and msg.range_max < 1000):
            raise ValueError('scan: invalid geometry or range')
        if any(isinstance(x, bool) or not isinstance(x,(float,int)) or
               math.isnan(x) or x < 0 or x == float('-inf') for x in msg.ranges):
            raise ValueError('scan: invalid range readings')
        # +inf means 'no return' for many simulation lidars; it is allowed.
        self._mark('scan', msg)

    def add_odom(self, msg):
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        values = (p.x, p.y, p.z, q.x, q.y, q.z, q.w)
        if any(type(x) not in (float, int) or not math.isfinite(x) for x in values):
            raise ValueError('odom: non-finite pose')
        if not .90 < sum(x*x for x in (q.x,q.y,q.z,q.w)) < 1.10:
            raise ValueError('odom: invalid quaternion')
        if not (str(msg.header.frame_id).endswith('odom') and
                str(msg.child_frame_id).endswith('base_link')):
            raise ValueError('odom: unexpected frame identifiers')
        self._mark('odom', msg)

    def report(self):
        required = ('camera', 'scan', 'odom')
        missing = {k: max(0, self.minimum_messages - self.counts[k]) for k in required}
        passed = not any(missing.values()) and not self.problems
        return {'ok': passed,
                'category': 'ROS_GAZEBO_SENSOR_SANITY_NOT_REAL_SIMULATION_PROOF',
                'distinct_timestamps': {k:self.counts[k] for k in required},
                'missing': missing,
                'first_stamp_ns': dict(self.first_stamps),
                'last_stamp_ns': dict(self.last_stamps),
                'issues': list(self.problems)}
