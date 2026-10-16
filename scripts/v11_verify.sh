#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p outputs/release
python3 -m compileall -q rescuemind ros scripts tests
python3 -m unittest discover -s tests -v >outputs/release/v11_unittest.log 2>&1
python3 scripts/v11_camera_fault_campaign.py >outputs/release/v11_camera_campaign.stdout
python3 scripts/v09_fault_matrix.py >outputs/release/v11_decision_fault_matrix.stdout
python3 scripts/validate_gazebo_world.py >outputs/release/v11_static_scene.stdout
python3 scripts/run_waypoint_regression.py >outputs/release/v11_ideal_kinematic.stdout
python3 ros/gazebo_waypoint_mission.py >outputs/release/v11_dry_run.stdout
for file in scripts/*.sh; do bash -n "$file"; done
python3 - <<'PY'
import json, re, shutil, sys, platform
from pathlib import Path
r=Path.cwd(); txt=(r/'outputs/release/v11_unittest.log').read_text()
m=re.search(r'Ran (\d+) tests in',txt)
assert m and 'FAILED' not in txt and '\nOK' in txt
cam=json.loads((r/'outputs/release/v11_camera_fault_campaign.json').read_text())
base=json.loads((r/'outputs/release/v09_fault_matrix.json').read_text())
scene=json.loads((r/'outputs/release/v09_static_scene_contract.json').read_text())
assert cam['cases']==500 and cam['pass_count']==500 and cam['all_pass']
assert base['cases']==972 and scene['status']=='PASS'
report={'version':'1.1','date_utc':'2026-10-16', 'python_unittest':{'status':'PASS','count':int(m.group(1))},
 'offline_camera_fault_campaign':{'status':'PASS','cases':cam['cases'],'pass_count':cam['pass_count'],
                                  'conditions':cam['by_condition']},
 'existing_software_fault_matrix':{'cases':base['cases'],'allowed':base['allowed'],'rejected':base['rejected']},
 'static_sdf_bridge_contract':'PASS','ideal_kinematics':'PASS',
 'environment':{'python':platform.python_version(),'ros2_available':bool(shutil.which('ros2')),
                'gz_available':bool(shutil.which('gz')),'nvidia_smi_available':bool(shutil.which('nvidia-smi'))},
 'real_jev_image_inference':'NOT_TESTED','real_qwen38_image_inference':'NOT_TESTED',
 'real_gazebo_run':'NOT_TESTED','real_robot_video':'NOT_CREATED',
 'scope':'Offline unit/fake-ROS/statics only; does not establish real VLM accuracy, real Gazebo contact physics, or an eligible submission video.'}
(r/'outputs/release/v11_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False,indent=2))
PY
python3 scripts/public_release_audit.py >outputs/release/v11_public_release_audit.stdout
