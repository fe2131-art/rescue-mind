#!/usr/bin/env bash
set -u
printf '== RescueMind environment diagnostic ==\n'
if [[ -f /etc/os-release ]]; then
  . /etc/os-release
  printf 'OS: %s\n' "${PRETTY_NAME:-unknown}"
  if [[ "${VERSION_ID:-}" != "24.04" ]]; then
    echo 'WARNING: This project targets Ubuntu 24.04 (Jazzy/Harmonic).'
  fi
fi
printf 'GPU: '
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
else
  echo 'nvidia-smi not found (GPU optional for basic TF-IDF).'
fi
printf 'ROS: '
if [[ -f /opt/ros/jazzy/setup.bash ]]; then
  echo '/opt/ros/jazzy/setup.bash exists'
else
  echo 'Jazzy not found; install it first.'
fi
for cmd in ros2 gz ffmpeg python3; do
  if command -v "$cmd" >/dev/null 2>&1; then
    printf '%s: %s\n' "$cmd" "$(command -v "$cmd")"
  else
    printf '%s: MISSING\n' "$cmd"
  fi
done
if command -v ros2 >/dev/null 2>&1; then
  ros2 pkg prefix nav2_bringup || true
  ros2 pkg prefix nav2_simple_commander || true
fi
