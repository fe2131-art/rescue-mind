#!/usr/bin/env bash
# ROS graph checks; inspect all publishers manually if this rejects your custom stack.
set -Eeuo pipefail
: "${ROS_DISTRO:=jazzy}"
set +u; source "/opt/ros/${ROS_DISTRO}/setup.bash"; set -u
for topic in /cmd_vel /rescuemind/guard_ready; do
  echo "--- $topic ---"
  info="$(timeout 8 ros2 topic info "$topic" -v)"
  echo "$info"
  if ! grep -Eq 'Publisher count: 1([[:space:]]|$)' <<<"$info"; then
    echo "STOP: $topic does not have exactly one publisher" >&2; exit 4
  fi
done
for topic in /odom /scan /camera; do
  timeout 8 ros2 topic info "$topic" -v >/dev/null || { echo "STOP: no $topic" >&2; exit 4; }
done
python3 "$(cd "$(dirname "$0")/.." && pwd)/scripts/v13_ros_graph_diagnostic.py"
echo 'Graph identity diagnostic PASS (not publisher authentication or proof of safety).'
