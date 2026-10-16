#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
set +u; source /opt/ros/jazzy/setup.bash; set -u
if [[ -f "$ROOT/.venv/bin/activate" ]]; then source "$ROOT/.venv/bin/activate"; fi
cd "$ROOT"
python3 scripts/v15_ros_sensor_probe.py "$@"
