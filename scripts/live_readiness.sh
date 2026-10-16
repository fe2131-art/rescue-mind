#!/usr/bin/env bash
# Run AFTER starting gz sim and ros_gz_bridge. This is a LIVE topic smoke test;
# it makes no inference, no wheel commands, and must be run on Ubuntu ROS host.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
: "${ROS_DISTRO:=jazzy}"
if [[ ! -f "/opt/ros/$ROS_DISTRO/setup.bash" ]]; then
  echo "ROS 2 $ROS_DISTRO missing. See docs/V09_UBUNTU_FIRST_RUN.md" >&2; exit 2
fi
set +u; source "/opt/ros/$ROS_DISTRO/setup.bash"; set -u
for tool in ros2 gz timeout; do command -v "$tool" >/dev/null || { echo "missing $tool" >&2; exit 2; }; done
out="$ROOT/outputs/local_runtime_diagnostics"
mkdir -p "$out"
printf 'ros_distro=%s\n' "$ROS_DISTRO" | tee "$out/environment.txt"
(ros2 topic list -t || true) > "$out/ros_topic_types.txt"
(gz topic -l || true) > "$out/gz_topic_list.txt"
for topic in /odom /scan /camera; do
  echo "Verifying $topic (may take 12 s) ..."
  if timeout 12 ros2 topic echo "$topic" --once --field header --qos-reliability best_effort > "$out/$(basename "$topic").txt" 2>"$out/$(basename "$topic").err"; then
    echo "PASS: $topic message received"
  else
    echo "FAIL: $topic no ROS messages; inspect $out and bridge config" >&2; exit 3
  fi
done
printf 'PASS: /odom /scan /camera sample received. Check content/frames and physical wheel motion separately.\n'
