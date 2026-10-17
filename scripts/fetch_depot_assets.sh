#!/usr/bin/env bash
# I-21: fetch the AWS RoboMaker small-warehouse models (MIT-0) into worlds/assets/aws-wh (git-ignored).
set -euo pipefail
cd "$(dirname "$0")/.."
D=worlds/assets/aws-wh
[ -f $D/models/aws_robomaker_warehouse_WallB_01/model.sdf ] && { echo "already present: $D"; exit 0; }
mkdir -p worlds/assets
git clone -q --depth 1 -b ros2 https://github.com/aws-robotics/aws-robomaker-small-warehouse-world.git $D
git -C $D rev-parse HEAD > $D/COMMIT
echo "fetched $(cat $D/COMMIT) into $D (licence: $D/LICENSE, MIT-0)"
