"""Strict ROS/Gazebo *simulation-time* consistency probe, independent of wall-clock safety timeouts.

A camera/scan/odom Header stamp is simulation time, NOT a Unix timestamp.
The watchdogs still use time.monotonic() for real-world timeout accounting.
This read-only contract rejects missing/non-advancing /clock and obviously
mixed (wall vs simulation) or reversed sensor acquisition stamps.
"""
from __future__ import annotations
from bisect import bisect_left
from dataclasses import dataclass, field

class ClockContractError(ValueError):
    pass

def stamp_ns(sec: int, nanosec: int) -> int:
    if type(sec) is not int or type(nanosec) is not int:
        raise ClockContractError('stamp requires integer sec/nanosec (not bool)')
    if sec < 0 or not 0 <= nanosec < 1_000_000_000:
        raise ClockContractError('invalid ROS time stamp')
    return sec * 1_000_000_000 + nanosec

@dataclass
class SimClockContract:
    max_skew_s: float = 2.0
    min_clock_advances: int = 3
    min_sensor_samples: int = 2
    clocks: list[int] = field(default_factory=list)
    sensors: dict[str, list[int]] = field(default_factory=lambda: {'camera':[], 'scan':[], 'odom':[]})
    issues: list[str] = field(default_factory=list)

    def __post_init__(self):
        if (not isinstance(self.max_skew_s,(int,float)) or isinstance(self.max_skew_s,bool)
                or not 0.1 <= self.max_skew_s <= 30 or not 2 <= self.min_clock_advances <= 100
                or not 1 <= self.min_sensor_samples <= 100):
            raise ClockContractError('invalid contract configuration')

    def clock(self, sec: int, nanosec: int) -> None:
        v = stamp_ns(sec,nanosec)
        if self.clocks and v < self.clocks[-1]:
            self.issues.append('simulation_clock_rewound')
        if not self.clocks or v > self.clocks[-1]:
            self.clocks.append(v)
        # Repeated /clock during pause is permitted; it cannot satisfy advances.

    def sensor(self, name: str, sec: int, nanosec: int) -> None:
        if name not in self.sensors:
            raise ClockContractError('unsupported sensor')
        v = stamp_ns(sec,nanosec)
        if v == 0:
            self.issues.append(name+'_zero_stamp')
        arr=self.sensors[name]
        if arr and v <= arr[-1]:
            self.issues.append(name+'_stamp_not_advancing')
        arr.append(v)

    def report(self) -> dict:
        issues=list(dict.fromkeys(self.issues))
        if len(self.clocks)<self.min_clock_advances:
            issues.append('clock_did_not_advance')
        if self.clocks:
            max_skew_ns=round(self.max_skew_s*1e9)
            for name,arr in self.sensors.items():
                if len(arr)<self.min_sensor_samples:
                    issues.append(name+'_insufficient_samples')
                for value in arr:
                    i=bisect_left(self.clocks,value)
                    nearest=min((abs(value-self.clocks[j]) for j in (i-1,i) if 0<=j<len(self.clocks)),default=10**30)
                    if nearest > max_skew_ns:
                        issues.append(name+'_not_in_simulation_time_domain')
                        break
        else:
            for name,arr in self.sensors.items():
                if len(arr)<self.min_sensor_samples:
                    issues.append(name+'_insufficient_samples')
        return {'ok':not issues,'issues':list(dict.fromkeys(issues)),
                'time_basis':'ROS_simulation_clock; watchdogs use host monotonic clock',
                'clock_advances':max(0,len(self.clocks)-1),
                'sensor_counts':{k:len(v) for k,v in self.sensors.items()},
                'max_skew_s':float(self.max_skew_s)}
