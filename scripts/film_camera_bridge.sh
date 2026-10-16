#!/usr/bin/env bash
# Demo-video only: spawn the static overview camera into the running world, then
# bridge its frames to ROS. The VLM checkpoint never subscribes to this topic.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set +u; source /opt/ros/jazzy/setup.bash; set -u
SDF="$ROOT/worlds/film/film_camera_overview.sdf"
for attempt in $(seq 1 60); do
  if gz service -s /world/rescuemind_arena/create --reqtype gz.msgs.EntityFactory \
       --reptype gz.msgs.Boolean --timeout 3000 \
       --req "sdf_filename: \"$SDF\" name: \"film_camera_overview\"" 2>/dev/null | grep -q 'data: true'; then
    echo "film camera spawned (attempt $attempt)"; break
  fi
  sleep 1
done
exec nice -n 15 ros2 run ros_gz_bridge parameter_bridge \
  '/film_camera_overview@sensor_msgs/msg/Image[gz.msgs.Image' \
  --ros-args -r __node:=rescuemind_film_bridge
