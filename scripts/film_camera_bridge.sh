#!/usr/bin/env bash
# Demo-video only: spawn the static overview camera into the running world, then
# bridge its frames to ROS. The VLM checkpoint never subscribes to this topic.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set +u; source /opt/ros/jazzy/setup.bash; set -u
# FILM_CAMERA_SDF (relative to the repository root, or absolute): another static camera pose, e.g. the depot's (scripts/film_depot.sh);
# the model name and the topic stay the same, so the recorder and the bridge below are unchanged.
SDF="${FILM_CAMERA_SDF:-worlds/film/film_camera_overview.sdf}"
case "$SDF" in /*) ;; *) SDF="$ROOT/$SDF";; esac
[ -f "$SDF" ] || { echo "film camera SDF not found: $SDF" >&2; exit 1; }
for attempt in $(seq 1 60); do
  if gz service -s /world/rescuemind_arena/create --reqtype gz.msgs.EntityFactory \
       --reptype gz.msgs.Boolean --timeout 3000 \
       --req "sdf_filename: \"$SDF\" name: \"film_camera_overview\"" 2>/dev/null | grep -q 'data: true'; then
    echo "film camera spawned (attempt $attempt)"; break
  fi
  sleep 1
done
renice -n 15 -p $$ >/dev/null   # lower priority without exec'ing the capability-carrying nice
exec ros2 run ros_gz_bridge parameter_bridge \
  '/film_camera_overview@sensor_msgs/msg/Image[gz.msgs.Image' \
  --ros-args -r __node:=rescuemind_film_bridge
