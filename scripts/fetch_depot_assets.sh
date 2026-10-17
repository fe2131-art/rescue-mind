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
# Some DAE files reference textures by an absolute Windows path; Gazebo then looks for the basename next to the mesh.
for m in $D/models/*/; do
  [ -d "$m/materials/textures" ] && [ -d "$m/meshes" ] && cp -n "$m"/materials/textures/* "$m/meshes/" 2>/dev/null || true
done
echo "textures copied next to the meshes"
python3 - <<'PY'
import re, glob
for f in glob.glob('worlds/assets/aws-wh/models/*/meshes/*.DAE'):
    t = open(f, errors='ignore').read()
    n = re.sub(r'file://C:\\[^<"]*\\([^\\<"]+\.(?:png|jpg|PNG|JPG))', r'\1', t)   # Windows paths -> basename next to the mesh
    if n != t:
        open(f, 'w').write(n)
PY
