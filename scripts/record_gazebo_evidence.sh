#!/usr/bin/env bash
# Capture the ACTUAL Ubuntu desktop. Never synthesize a claim of Gazebo success.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if ! command -v ffmpeg >/dev/null; then echo 'Install ffmpeg first' >&2; exit 2; fi
if [[ -z "${DISPLAY:-}" ]]; then echo 'DISPLAY not set: x11grab requires a visible X11 desktop. Use OBS for Wayland.' >&2; exit 2; fi
: "${RECORD_SECONDS:=120}"
: "${SCREEN_SIZE:=1920x1080}"
: "${SCREEN_ORIGIN:=0,0}"
case "$RECORD_SECONDS" in ''|*[!0-9]*) echo 'RECORD_SECONDS must be integer 60-180' >&2; exit 2;; esac
if (( RECORD_SECONDS < 60 || RECORD_SECONDS > 180 )); then echo 'Video must be 1-3 minutes' >&2; exit 2; fi
mkdir -p "$ROOT/outputs/local_runtime_diagnostics"
out="$ROOT/outputs/local_runtime_diagnostics/actual_gazebo_raw.mp4"
echo "Recording real desktop ${DISPLAY}+${SCREEN_ORIGIN} for ${RECORD_SECONDS}s -> $out"
ffmpeg -hide_banner -loglevel warning -y -f x11grab -framerate 20 -video_size "$SCREEN_SIZE" -i "${DISPLAY}+${SCREEN_ORIGIN}" -t "$RECORD_SECONDS" -an -c:v libx264 -crf 23 -pix_fmt yuv420p "$out"
echo "Saved raw screen recording; inspect personally for identifiable information and accurate provenance."
