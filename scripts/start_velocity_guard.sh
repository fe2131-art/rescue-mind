#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
: "${ROS_DISTRO:=jazzy}"
set +u; source "/opt/ros/${ROS_DISTRO}/setup.bash"; set -u
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
echo 'Ensure NO other publisher targets /cmd_vel. Guard sends ZERO until sensors ready.'
exec python3 "$ROOT/ros/guarded_cmd_relay.py"
