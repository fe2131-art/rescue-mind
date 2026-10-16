#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
mkdir -p outputs/release
python3 -m compileall -q rescuemind ros tests scripts
python3 -m unittest discover -s tests -v > outputs/release/v08_unittest.log 2>&1
python3 scripts/validate_gazebo_world.py > outputs/release/v08_static_scene.stdout
python3 scripts/run_v08_counterfactual.py > outputs/release/v08_counterfactual.stdout
python3 ros/gazebo_waypoint_mission.py > outputs/release/v08_dry_run.stdout
python3 scripts/run_waypoint_regression.py > outputs/release/v08_kinematic.stdout
python3 - <<'PY'
from pathlib import Path
import json,shutil,re
root=Path('.')
log=(root/'outputs/release/v08_unittest.log').read_text()
count=re.search(r'Ran (\d+) tests in',log)
assert count and 'OK' in log and 'FAILED' not in log
scene=json.loads(Path('outputs/release/v08_static_scene_contract.json').read_text())
counter=json.loads(Path('outputs/release/v08_counterfactual_software.json').read_text())
res={'version':'0.8','test_cases':int(count.group(1)),
     'unittest':'PASS','synthetic_policy_cases':counter['n_cases'],
     'sdf_static_scene_contract':scene['status'],
     'gz_installed':shutil.which('gz') is not None,'ros2_installed':shutil.which('ros2') is not None,
     'external_jev_api_tested':False,'external_qwen_api_tested':False,
     'real_gazebo_motion_verified':False,
     'notes':['No real API keys or Gazebo runtime available to this verification script',
              'All simulated outcomes are synthetic; do not cite as real-world recognition metrics']}
Path('outputs/release/v08_verification.json').write_text(json.dumps(res,ensure_ascii=False,indent=2))
print(json.dumps(res,ensure_ascii=False,indent=2))
PY
