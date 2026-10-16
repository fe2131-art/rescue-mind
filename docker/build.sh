#!/usr/bin/env bash
# Build the RescueMind runtime image (no sudo; requires membership in the docker group).
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
exec docker build -t "${RESCUEMIND_IMAGE:-rescuemind:jazzy}" .
