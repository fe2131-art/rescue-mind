#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set +u; source /opt/ros/jazzy/setup.bash; set -u
ros2 pkg prefix ros_gz_bridge >/dev/null || { echo 'Install ros-jazzy-ros-gz-bridge' >&2; exit 2; }
# Map fully qualified Gazebo world clock to /clock, and each sensor explicitly.
exec ros2 launch ros_gz_bridge ros_gz_bridge.launch.py \
  bridge_name:=rescuemind_ros_gz_bridge \
  config_file:="$ROOT/configs/ros_gz_bridge_v20.yaml"
