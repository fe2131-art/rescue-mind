#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Check that the guard is the sole commanded-velocity publisher.
bash "$ROOT/scripts/check_guard_topology.sh"
# Three distinct, valid ROS acquisition stamps and credible payloads per stream.
bash "$ROOT/scripts/v15_sensor_probe.sh" --seconds 20 --minimum-messages 3
printf 'PASS: guarded ROS sensor contract. Does not prove vehicle movement.\n'
