#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p outputs/release
python3 -m compileall -q rescuemind ros scripts tests
python3 -m unittest discover -s tests -v > outputs/release/v15_unittest.log 2>&1
python3 scripts/v15_fault_campaign.py > outputs/release/v15_fault_campaign.stdout
python3 scripts/v15_orchestrate.py --plan --scenario motion-check > outputs/release/v15_motion_plan.json
python3 scripts/v15_orchestrate.py --plan --scenario live > outputs/release/v15_live_plan.json
python3 scripts/validate_gazebo_world.py > outputs/release/v15_static_scene.stdout
python3 scripts/run_waypoint_regression.py > outputs/release/v15_ideal_kinematic.stdout
python3 scripts/v12_velocity_fault_campaign.py > outputs/release/v15_velocity_campaign.stdout
python3 scripts/v11_camera_fault_campaign.py > outputs/release/v15_camera_campaign.stdout
python3 scripts/v09_fault_matrix.py > outputs/release/v15_decision_campaign.stdout
for file in scripts/*.sh; do bash -n "$file"; done
python3 scripts/public_release_audit.py > outputs/release/v15_public_release_audit.stdout
python3 - <<'PY'
import json,platform,re,shutil
from pathlib import Path
out=Path('outputs/release')
txt=(out/'v15_unittest.log').read_text()
m=re.search(r'Ran (\d+) tests in',txt)
assert m and '\nOK' in txt and '\nFAILED' not in txt, 'unit tests failed'
c=json.loads((out/'v15_sensor_fault_campaign.json').read_text())
assert c['passed']==c['cases']==600 and not c['failed']
a=json.loads((out/'v12_velocity_fault_campaign.json').read_text())
b=json.loads((out/'v11_camera_fault_campaign.json').read_text())
d=json.loads((out/'v09_fault_matrix.json').read_text())
assert a['cases']==a['passes']==1125 and b['pass_count']==500 and d['cases']==972
summary={'release':'v1.5','verification_date':'2026-10-16',
 'scope':'offline software, synthetic ROS messages, physical waypoint mathematics, static XML and scripts only',
 'unit_tests':int(m.group(1)),'unit_tests_status':'PASS',
 'v15_synthetic_sensor_cases':c['cases'],'v15_synthetic_sensor_correct':c['passed'],
 'previous_guard_fault_cases':a['cases'],'previous_camera_cases':b['pass_count'],
 'previous_policy_conditions':d['cases'],
 'sdf_and_bridge_static':'PASS','ideal_kinematics':'PASS',
 'shell_syntax':'PASS','stack_plan':'PASS',
 'runtime_tools_available':{k:bool(shutil.which(k)) for k in ('ros2','gz','nvidia-smi','ffprobe')},
 'actual_gazebo_simulation':'NOT_TESTED','live_ros_sensor_probe':'NOT_TESTED',
 'live_Jev_api':'NOT_TESTED','live_Qwen_api':'NOT_TESTED',
 'actual_vision_accuracy':'NOT_MEASURED','final_submission_video':'NOT_CREATED',
 'note':'Synthetic successes must never be reported as real VLM accuracy or robot completion.'}
(out/'v15_VERIFICATION.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
PY
