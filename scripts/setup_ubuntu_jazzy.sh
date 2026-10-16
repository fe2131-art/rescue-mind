#!/usr/bin/env bash
# Run on Ubuntu 24.04 with ROS 2 Jazzy already installed via apt.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ "$(. /etc/os-release && echo "$VERSION_ID")" != '24.04' ]]; then
  echo 'STOP: this reproducible bootstrap targets Ubuntu 24.04' >&2; exit 2
fi
if [[ ! -r /opt/ros/jazzy/setup.bash ]]; then
  echo 'STOP: install ROS 2 Jazzy and ros_gz before this bootstrap' >&2; exit 2
fi
set +u; source /opt/ros/jazzy/setup.bash; set -u
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"
"$PYTHON_BIN" -c 'import rclpy; print("ROS Python import PASS")'
cd "$ROOT"
# Ubuntu apt ROS Python packages live in system dist-packages; avoid isolated venv.
"$PYTHON_BIN" -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install -e .
python -c 'import rclpy, rescuemind; print("rclpy + rescuemind import PASS")'
python -m unittest discover -s tests -q
printf '\nReady. In EACH terminal: source /opt/ros/jazzy/setup.bash && source .venv/bin/activate\n'
