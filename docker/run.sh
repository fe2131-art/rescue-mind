#!/usr/bin/env bash
# Run a command inside the RescueMind ROS 2 Jazzy / Gazebo Harmonic / CUDA container.
#   bash docker/run.sh python3 scripts/v32_orchestrate.py --run --scenario live --scene nominal
# The repository is mounted at the SAME absolute path so evidence paths stay valid,
# the host Hugging Face cache is shared read-mostly, and files are owned by the caller.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${RESCUEMIND_IMAGE:-rescuemind:jazzy}"
HF_CACHE="${HF_HOME:-$HOME/.cache/huggingface}"
mkdir -p "$HF_CACHE"
RUN_FLAGS=(--rm)
[[ -t 0 && -t 1 ]] && RUN_FLAGS+=(-it)
# RESCUEMIND_CONTAINER=name keeps a detached container for `docker exec` sessions.
if [[ -n "${RESCUEMIND_CONTAINER:-}" ]]; then RUN_FLAGS=(-d --name "$RESCUEMIND_CONTAINER"); fi
exec docker run "${RUN_FLAGS[@]}" \
  --init --gpus all --network host --ipc host \
  --user "$(id -u):$(id -g)" \
  -e HOME=/tmp/rescuemind-home \
  -e HF_HOME=/hf -e HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}" \
  -e ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-73}" \
  -e ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST \
  -e GZ_PARTITION="${GZ_PARTITION:-rescuemind_$(id -u)}" \
  -e GZ_IP=127.0.0.1 \
  -e DISPLAY="${DISPLAY:-}" \
  -v "$ROOT:$ROOT" -w "$ROOT" \
  -v "$HF_CACHE:/hf" \
  ${RESCUEMIND_DOCKER_EXTRA:-} \
  "$IMAGE" "$@"
