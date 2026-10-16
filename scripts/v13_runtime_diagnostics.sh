#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
: "${ROS_DISTRO:=jazzy}"
set +u; source "/opt/ros/${ROS_DISTRO}/setup.bash"; set -u
# A venv containing system ROS packages may be activated after source.
[[ -r "$ROOT/.venv/bin/activate" ]] && source "$ROOT/.venv/bin/activate"
command -v ros2 >/dev/null && command -v gz >/dev/null
mkdir -p "$ROOT/outputs/local_runtime_diagnostics"
gz topic -l > "$ROOT/outputs/local_runtime_diagnostics/v13_gz_topics.txt"
ros2 topic list -t > "$ROOT/outputs/local_runtime_diagnostics/v13_ros_topics.txt"
bash "$ROOT/scripts/v12_live_readiness.sh"
python3 "$ROOT/scripts/v13_ros_graph_diagnostic.py"
python3 -c 'import rclpy, rescuemind; print("ROS Python imports PASS")'
echo 'LIVE GRAPH READINESS PASS; not evidence of Gazebo movement, AI calls or certified safety.'
