#!/usr/bin/env bash
# Runs as the host UID; give ROS/Gazebo a writable HOME and source the stack.
set -e
export HOME="${HOME:-/tmp/rescuemind-home}"
[[ -w "$HOME" ]] || export HOME=/tmp/rescuemind-home
mkdir -p "$HOME"
source /opt/ros/jazzy/setup.bash
source "${RESCUEMIND_VENV:-/opt/rescuemind-venv}/bin/activate"
exec "$@"
