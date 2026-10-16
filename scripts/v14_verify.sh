#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p outputs/release
python3 -m compileall -q rescuemind ros scripts tests
python3 -m unittest discover -s tests -v > outputs/release/v14_unittest.log 2>&1
python3 scripts/v14_causal_ablation.py > outputs/release/v14_causal_ablation.stdout
python3 scripts/v14_orchestrate.py --plan --scenario motion-check > outputs/release/v14_motion_plan.json
python3 scripts/v14_orchestrate.py --plan --scenario live > outputs/release/v14_live_plan.json
python3 scripts/v12_velocity_fault_campaign.py > outputs/release/v14_velocity_campaign.stdout
python3 scripts/v11_camera_fault_campaign.py > outputs/release/v14_camera_campaign.stdout
python3 scripts/v09_fault_matrix.py > outputs/release/v14_decision_campaign.stdout
python3 scripts/validate_gazebo_world.py > outputs/release/v14_static_scene.stdout
python3 scripts/run_waypoint_regression.py > outputs/release/v14_ideal_kinematic.stdout
python3 ros/gazebo_waypoint_mission.py > outputs/release/v14_direct_drive_plan.stdout
for file in scripts/*.sh; do bash -n "$file"; done
python3 scripts/public_release_audit.py > outputs/release/v14_public_release_audit.stdout
python3 - <<'PY'
import json,platform,re,shutil,os
from pathlib import Path
root=Path.cwd(); out=root/'outputs/release'
unit=(out/'v14_unittest.log').read_text()
match=re.search(r'Ran (\d+) tests in',unit)
assert match and '\nOK' in unit and 'FAILED' not in unit
relay=json.loads((out/'v12_velocity_fault_campaign.json').read_text())
camera=json.loads((out/'v11_camera_fault_campaign.json').read_text())
gate=json.loads((out/'v09_fault_matrix.json').read_text())
abl=json.loads((out/'v14_synthetic_ablation.json').read_text())
assert relay['cases']==relay['passes']==1125
assert camera['pass_count']==500
assert gate['cases']==972
assert abl['number_of_synthetic_cases']==12
assert abl['policy_comparison']['dual_safety_gate']['false_approvals']==0
summary={'release':'v1.4','date':'2026-10-16',
  'verification_scope':'offline software tests / mocks / static scene checks / subprocess lifecycle only',
  'tests_passed':int(match.group(1)), 'status':'PASS',
  'guard_fault_campaign_cases':relay['cases'], 'camera_fault_campaign_cases':camera['pass_count'],
  'synthetic_policy_conditions':gate['cases'], 'causal_ablation_hand_constructed_cases':len(abl['policy_comparison'])*4,
  'sdf_static':'PASS','ideal_kinematics':'PASS', 'shell_syntax':'PASS',
  'orchestrator_plan':'PASS','real_subprocess_cleanup_test':'PASS',
  'environment_tools':{s:bool(shutil.which(s)) for s in ('gz','ros2','nvidia-smi','ffprobe')},
  'real_Jev_API':'NOT_TESTED','real_Qwen_API':'NOT_TESTED',
  'real_Gazebo':'NOT_TESTED','real_ROS_Gazebo_traffic':'NOT_TESTED',
  'physical_item_transfer':'NOT_IMPLEMENTED','final_submission_video':'NOT_CREATED',
  'warning':'Do not report synthetic false approval as real model accuracy.'}
(out/'v14_VERIFICATION.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
PY
