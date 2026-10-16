#!/usr/bin/env bash
# OPTIONAL manual ROS 2 bag capture of physical simulation traffic.
# Use in a separate terminal after the Gazebo/ROS bridge starts; Ctrl+C to flush.
# The bag captures topics, NOT model API secrets or proof of Gazebo provenance.
set -Eeuo pipefail
if [ "$#" -ne 1 ]; then echo 'Usage: bash scripts/v19_rosbag_capture.sh /absolute/output/run-directory' >&2; exit 2; fi
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set +u; source /opt/ros/jazzy/setup.bash; set -u
RUN_DIR="$1"
if [[ "$RUN_DIR" != /* ]]; then echo 'Require absolute output directory' >&2; exit 2; fi
if [[ "$RUN_DIR" != "$ROOT"/outputs/runs/* ]]; then
 echo 'For privacy, only store a bag below this project outputs/runs/' >&2; exit 2
fi
if [[ -e "$RUN_DIR/rosbag2" ]]; then echo 'Refusing to overwrite bag' >&2; exit 2; fi
mkdir -p "$RUN_DIR"
command -v ros2 >/dev/null
ros2 bag record -o "$RUN_DIR/rosbag2" --topics /odom /cmd_vel /rescuemind/cmd_vel_request /camera /scan /rescuemind/guard_ready
