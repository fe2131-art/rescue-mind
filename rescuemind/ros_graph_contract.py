"""Fail-closed *diagnostic* validation of ROS 2 publisher identity.

Works with `ros2 topic info TOPIC -v` text from Jazzy CLI. A DDS graph report
cannot authenticate publishers; this only catches common misconfiguration.
"""
from __future__ import annotations
import re


def publisher_names(topic_info: str) -> list[str]:
    match = re.search(r"(?m)^\s*Publisher count:\s*(\d+)\s*$", topic_info)
    if not match:
        raise ValueError("missing publisher count")
    count = int(match.group(1))
    names = []
    blocks = re.split(r"(?m)^\s*Node name:\s*", topic_info)[1:]
    for block in blocks:
        name = block.splitlines()[0].strip()
        endpoint_type = re.search(r"(?m)^\s*Endpoint type:\s*(\w+)\s*$", block)
        if endpoint_type and endpoint_type.group(1).upper() == "PUBLISHER":
            names.append(name)
    if len(names) != count:
        raise ValueError(f"publisher name/count inconsistency: {len(names)} vs {count}")
    return names


def assert_guard_topology(cmd_info: str, ready_info: str) -> None:
    expected = ["rescuemind_velocity_guard"]
    if publisher_names(cmd_info) != expected or publisher_names(ready_info) != expected:
        raise RuntimeError("/cmd_vel and guard_ready must ONLY be published by the guard")
