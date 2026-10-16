#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# 1. Gazebo Transport must expose scene clock/odom/camera/scan.
python3 "$ROOT/scripts/v21_gz_transport_probe.py" --attempts 3 --interval 1
# 2. ROS bridge, safety relay, message contents and stamp domain must be valid.
bash "$ROOT/scripts/v20_live_readiness.sh"
