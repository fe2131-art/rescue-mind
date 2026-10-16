#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bash "$ROOT/scripts/v15_live_readiness.sh"
set +u; source /opt/ros/jazzy/setup.bash; set -u
VENV="${RESCUEMIND_VENV:-$ROOT/.venv}"
if [[ -f "$VENV/bin/activate" ]]; then source "$VENV/bin/activate"; fi
python3 "$ROOT/scripts/v20_clock_probe.py" --seconds 16
