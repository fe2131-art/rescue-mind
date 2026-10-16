#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if ! command -v gz >/dev/null 2>&1; then
 echo 'Gazebo not installed (no real runtime test possible here)' >&2; exit 2
fi
# This verifies parsing and a running Gazebo instance's topics, not full mission success.
echo 'Gazebo installed:'; gz sim --versions 2>/dev/null || true
if command -v timeout >/dev/null; then
 timeout 18s gz sim -s -r -v 4 "$ROOT/worlds/rescuemind_test_arena.sdf" \
   >"$ROOT/outputs/gazebo_smoke.log" 2>&1 &
 PID=$!
 sleep 7
 echo 'Simulator topics:'
 gz topic -l | grep -E '(^/cmd_vel|^/odom|^/scan|^/camera)' || true
 kill "$PID" 2>/dev/null || true
 wait "$PID" 2>/dev/null || true
 echo 'Look at outputs/gazebo_smoke.log for startup warnings; this script alone does not certify movement.'
else
 echo 'timeout missing'; exit 2
fi
