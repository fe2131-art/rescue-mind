#!/usr/bin/env bash
# Apply docker/Dockerfile.security to the project images (old images are kept as <tag>-presec).  Running containers keep their old image until they are recreated.
set -e
cd "$(dirname "$0")/.."
IMAGES=${IMAGES:-"rescuemind:jazzy rescuemind:jazzy-next rescuemind:latex voicevox/voicevox_engine:cpu-latest"}      # IMAGES="python:3.12-slim ubuntu:24.04 ..." for other images on the host
for img in $IMAGES; do
  user=$(docker inspect -f '{{.Config.User}}' "$img"); user=${user:-root}
  docker tag "$img" "${img}-presec"
  docker build -q --build-arg BASE="${img}-presec" --build-arg ORIG_USER="$user" -f docker/Dockerfile.security -t "$img" docker
  echo "rebuilt $img (user $user)"
done
