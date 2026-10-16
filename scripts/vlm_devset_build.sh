#!/usr/bin/env bash
# Build the VLM development set for all three scenes (run inside docker/run.sh).
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$ROOT/experiments/vlm_devset}"
rm -rf "$OUT"; mkdir -p "$OUT"
for scene in nominal swapped empty; do
  gz sim -s -r --headless-rendering -v 1 "$ROOT/worlds/scenarios/rescuemind_$scene.sdf" > "$OUT/gz_$scene.log" 2>&1 &
  GZ=$!
  bash "$ROOT/scripts/bridge_direct_gazebo.sh" > "$OUT/bridge_$scene.log" 2>&1 &
  BR=$!
  sleep 9
  python3 "$ROOT/scripts/vlm_devset_capture.py" --scene "$scene" --out "$OUT"
  kill "$BR" 2>/dev/null || true; pkill -f ros_gz_bridge || true
  kill -9 "$GZ" 2>/dev/null || true; wait "$GZ" 2>/dev/null || true
  sleep 2
done
rm -f "$OUT"/gz_*.log "$OUT"/bridge_*.log
