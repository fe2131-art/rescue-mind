#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p outputs/release
python3 -m compileall -q rescuemind ros scripts tests
python3 -m unittest discover -s tests -v > outputs/release/v12_unittest.log 2>&1
python3 scripts/v12_velocity_fault_campaign.py > outputs/release/v12_velocity_fault_campaign.stdout
python3 scripts/v11_camera_fault_campaign.py > outputs/release/v12_camera_fault_campaign.stdout
python3 scripts/v09_fault_matrix.py > outputs/release/v12_decision_fault_matrix.stdout
python3 scripts/validate_gazebo_world.py > outputs/release/v12_static_scene.stdout
python3 scripts/run_waypoint_regression.py > outputs/release/v12_kinematics.stdout
python3 ros/gazebo_waypoint_mission.py > outputs/release/v12_dry_run.stdout
for sh in scripts/*.sh; do bash -n "$sh"; done
python3 - <<'PY'
import json,os,re,platform,shutil
from pathlib import Path
root=Path.cwd();log=(root/'outputs/release/v12_unittest.log').read_text()
n=re.search(r'Ran (\d+) tests in',log)
assert n and '\nOK' in log and 'FAILED' not in log
relay=json.loads((root/'outputs/release/v12_velocity_fault_campaign.json').read_text())
cam=json.loads((root/'outputs/release/v11_camera_fault_campaign.json').read_text())
old=json.loads((root/'outputs/release/v09_fault_matrix.json').read_text())
assert relay['cases']==1125 and relay['passes']==1125
assert cam['pass_count']==500 and old['cases']==972
assert (root/'worlds/rescuemind_test_arena.sdf').exists()
summary={'release':'v1.2','date':'2026-10-16','scope':'OFFLINE UNIT/Fake ROS/STATIC ONLY',
 'python_tests':int(n.group(1)),'python_test_status':'PASS',
 'velocity_relay_fault_cases':relay['cases'],'velocity_relay_fault_pass':relay['passes'],
 'camera_watch_previous_cases':cam['cases'],
 'decision_gate_previous_cases':old['cases'],'static_sdf_xml':'PASS',
 'ideal_kinematic_trace':'PASS',
 'environment':{s:bool(shutil.which(s)) for s in ['ros2','gz','nvidia-smi']},
 'python':platform.python_version(),
 'real_gazebo_execution':'NOT_TESTED','real_jev_inference':'NOT_TESTED',
 'real_qwen_inference':'NOT_TESTED','submission_robot_video':'NOT_CREATED',
 'physical_transport':'NOT_IMPLEMENTED',
 'safety_certification':'NONE'}
(root/'outputs/release/v12_verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
PY
python3 scripts/public_release_audit.py > outputs/release/v12_public_audit.stdout
