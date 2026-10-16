#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
bash "$ROOT/scripts/live_readiness.sh"
bash "$ROOT/scripts/check_guard_topology.sh"
echo 'NOTE: publication and camera quality still require a real Gazebo test.'
