#!/usr/bin/env bash
# Manual capture after v20 YAML bridge and /clock probe pass.
set -Eeuo pipefail
if [ "$#" -ne 1 ]; then echo 'Usage: bash scripts/v20_rosbag_capture.sh /absolute/project/outputs/runs/<run_id>' >&2; exit 2; fi
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set +u; source /opt/ros/jazzy/setup.bash; set -u
RUN_DIR="$1"
if [[ "$RUN_DIR" != "$ROOT"/outputs/runs/* ]] || [[ "$RUN_DIR" != /* ]]; then
  echo 'Run directory must be inside this project outputs/runs/' >&2; exit 2
fi
if [[ -e "$RUN_DIR/rosbag2" ]]; then echo 'Refusing to overwrite rosbag2' >&2; exit 2; fi
mkdir -p "$RUN_DIR"
# rosbag2 will NOT start writing messages before it receives /clock.
exec ros2 bag record --use-sim-time -o "$RUN_DIR/rosbag2" --topics \
 /clock /odom /cmd_vel /rescuemind/cmd_vel_request /camera /scan /rescuemind/guard_ready
