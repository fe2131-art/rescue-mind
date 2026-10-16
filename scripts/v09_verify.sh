#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
mkdir -p outputs/release
python3 -m compileall -q rescuemind ros tests scripts
python3 -m unittest discover -s tests -v >outputs/release/v09_unittest.log 2>&1
python3 scripts/v09_fault_matrix.py >outputs/release/v09_fault_matrix.stdout
python3 scripts/validate_gazebo_world.py >outputs/release/v09_scene_static.stdout
python3 scripts/run_waypoint_regression.py >outputs/release/v09_waypoint_regression.stdout
python3 ros/gazebo_waypoint_mission.py >outputs/release/v09_dry_run.stdout
for script in scripts/bridge_direct_gazebo.sh scripts/live_readiness.sh scripts/record_gazebo_evidence.sh scripts/v09_verify.sh; do
  bash -n "$script"
done
python3 - <<'PY'
import json,shutil,re
from pathlib import Path
log=Path('outputs/release/v09_unittest.log').read_text()
m=re.search(r'Ran (\d+) tests in',log)
assert m and 'FAILED' not in log and 'OK' in log
fault=json.loads(Path('outputs/release/v09_fault_matrix.json').read_text())
scene=json.loads(Path('outputs/release/v09_static_scene_contract.json').read_text())
assert fault['cases']==972 and fault['allowed']>0 and fault['rejected']>0
assert scene['status']=='PASS'
res={'version':'0.9','test_count':int(m.group(1)),
     'automated_tests':'PASS','software_fault_matrix_cases':fault['cases'],
     'software_fault_matrix_allowed':fault['allowed'],
     'gazebo_sdf_static_contract':scene['status'],
     'gz_executable_available_here':shutil.which('gz') is not None,
     'ros2_executable_available_here':shutil.which('ros2') is not None,
     'real_gazebo_motion_verified':False,'real_jev_api_verified':False,
     'real_qwen38_api_verified':False,'nvidia_gpu_verified':False,
     'submission_robot_video_created':False,
     'disclaimer':'Only mock/kinematic/static tests. The Linux workstation must run the real models and Gazebo.'}
Path('outputs/release/v09_verification_summary.json').write_text(json.dumps(res,ensure_ascii=False,indent=2))
print(json.dumps(res,ensure_ascii=False,indent=2))
PY
