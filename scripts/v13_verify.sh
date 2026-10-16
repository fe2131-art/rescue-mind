#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p outputs/release
python3 -m compileall -q rescuemind ros scripts tests
python3 -m unittest discover -s tests -v > outputs/release/v13_unittest.log 2>&1
python3 scripts/v12_velocity_fault_campaign.py > outputs/release/v13_velocity_fault_campaign.stdout
python3 scripts/v11_camera_fault_campaign.py > outputs/release/v13_camera_fault_campaign.stdout
python3 scripts/v09_fault_matrix.py > outputs/release/v13_decision_fault_matrix.stdout
python3 scripts/validate_gazebo_world.py > outputs/release/v13_static_scene.stdout
python3 scripts/run_waypoint_regression.py > outputs/release/v13_kinematics.stdout
python3 ros/gazebo_waypoint_mission.py > outputs/release/v13_dry_run.stdout
for sh in scripts/*.sh; do bash -n "$sh"; done
python3 scripts/public_release_audit.py > outputs/release/v13_public_audit.stdout
python3 - <<'PY'
import json,os,re,platform,shutil
from pathlib import Path
root=Path.cwd();log=(root/'outputs/release/v13_unittest.log').read_text()
n=re.search(r'Ran (\d+) tests in',log)
assert n and '\nOK' in log and 'FAILED' not in log
relay=json.loads((root/'outputs/release/v12_velocity_fault_campaign.json').read_text())
cam=json.loads((root/'outputs/release/v11_camera_fault_campaign.json').read_text())
old=json.loads((root/'outputs/release/v09_fault_matrix.json').read_text())
assert relay['cases']==1125 and relay['passes']==1125
assert cam['pass_count']==500 and old['cases']==972
summary={'release':'v1.3','as_of':'2026-10-16',
 'scope':'OFFLINE TESTS + MOCK ROS + STATIC INSPECTION ONLY',
 'test_count':int(n.group(1)),'test_status':'PASS',
 'velocity_guard_fault_cases':relay['cases'],'velocity_guard_fault_passes':relay['passes'],
 'camera_fault_cases':cam['cases'],'decision_fault_cases':old['cases'],
 'source_sdf_static':'PASS','ideal_kinematic_regression':'PASS','shell_syntax':'PASS',
 'graph_guard_test':'synthetic ROS CLI text only',
 'environment_tools':{s:bool(shutil.which(s)) for s in ['ros2','gz','nvidia-smi','ffprobe']},
 'python':platform.python_version(),
 'actual_ros_graph':'NOT_TESTED','gazebo_physics':'NOT_TESTED',
 'jev_real_api':'NOT_TESTED','qwen_real_api':'NOT_TESTED',
 'real_model_accuracy':'NOT_MEASURED','submission_video':'NOT_CREATED',
 'real_transport':'NOT_IMPLEMENTED','certified_safety':False,
 'limitations':['offline pass is not Gazebo or VLM performance','guard process crash cannot guarantee stop']}
(root/'outputs/release/v13_verification.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(summary,indent=2,ensure_ascii=False))
PY
