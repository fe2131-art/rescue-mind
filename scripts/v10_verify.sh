#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p outputs/release
python3 -m compileall -q rescuemind ros scripts tests
python3 -m unittest discover -s tests -v >outputs/release/v10_unittest.log 2>&1
python3 scripts/v09_fault_matrix.py >outputs/release/v10_fault_matrix.stdout
python3 scripts/validate_gazebo_world.py >outputs/release/v10_static_gazebo.stdout
python3 scripts/run_waypoint_regression.py >outputs/release/v10_kinematic.stdout
python3 ros/gazebo_waypoint_mission.py >outputs/release/v10_dry_run.stdout
for f in scripts/*.sh; do bash -n "$f"; done
python3 - <<'PY'
import json,re,shutil,hashlib,sys
from pathlib import Path
root=Path.cwd()
log=(root/'outputs/release/v10_unittest.log').read_text()
match=re.search(r'Ran (\d+) tests in',log)
assert match is not None and 'FAILED' not in log and 'OK' in log
fault=json.loads((root/'outputs/release/v09_fault_matrix.json').read_text())
world=json.loads((root/'outputs/release/v09_static_scene_contract.json').read_text())
assert world['status']=='PASS'
assert fault['cases']==972
summary={'version':'1.0','test_count':int(match.group(1)),
  'python_unittest':'PASS','fault_matrix_cases':fault['cases'],
  'fault_matrix_allowed':fault['allowed'], 'fault_matrix_rejected':fault['rejected'],
  'static_gazebo_scene_contract':'PASS',
  'ros2_available_in_this_runtime':bool(shutil.which('ros2')),
  'gz_available_in_this_runtime':bool(shutil.which('gz')),
  'jev_live_verified':False,'qwen_live_verified':False,'gazebo_runtime_verified':False,
  'camera_header_freshness_unit_tested':True,'evidence_hash_check_unit_tested':True,
  'submission_video_verified':False,'notes':'Tests use mocks, synthetic conditions and mathematical simulation. They do not verify real VLM or Gazebo.'}
(root/'outputs/release/v10_verification.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf8')
print(json.dumps(summary,indent=2,ensure_ascii=False))
PY
python3 scripts/public_release_audit.py >outputs/release/v10_public_audit.stdout
