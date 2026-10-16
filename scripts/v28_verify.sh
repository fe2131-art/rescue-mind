#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p verification/v28
python3 -m unittest discover -s tests -v > verification/v28/unittest.log 2>&1
python3 scripts/v28_clock_campaign.py > verification/v28/clock_campaign_stdout.json
python3 scripts/v27_acquisition_campaign.py > verification/v28/v27_acquisition_campaign_stdout.json
python3 scripts/v26_stationary_campaign.py > verification/v28/v26_stationary_campaign_stdout.json
python3 scripts/v24_fault_campaign.py > verification/v28/v24_denial_campaign_stdout.json
python3 scripts/v25_camera_audit.py > verification/v28/v25_projection_stdout.json
python3 -m compileall -q rescuemind ros scripts tests
for f in scripts/*.sh; do bash -n "$f"; done
for scene in nominal swapped empty; do
  python3 scripts/v28_orchestrate.py --plan --scenario live --scene "$scene" > "verification/v28/plan_${scene}.json"
done
python3 scripts/v28_orchestrate.py --plan --scenario motion-check --scene nominal > verification/v28/plan_motion.json
python3 - <<'PY'
import json,re,shutil
from pathlib import Path
from rescuemind.scene_variants import audit_scenarios
from rescuemind.gazebo_transport_contract import validate_static
from rescuemind.v23_protocol import validate_protocol
R=Path.cwd()
assert audit_scenarios(R/'worlds/scenarios')['pass']
for scene in ('nominal','swapped','empty'):
    validate_static(R/f'worlds/scenarios/rescuemind_{scene}.sdf',R/'configs/ros_gz_bridge_v20.yaml')
    p=json.loads((R/f'verification/v28/plan_{scene}.json').read_text())
    assert '--run-live' in str(p['mission']) and p['scene']==scene
assert '--motion-check' in str(json.loads((R/'verification/v28/plan_motion.json').read_text())['mission'])
validate_protocol(json.loads((R/'experiments/v23_locked_protocol.json').read_text()))
text=(R/'verification/v28/unittest.log').read_text()
m=re.search(r'Ran (\d+) tests in',text)
assert m and re.search(r'^OK\s*$',text,re.M) and 'FAILED' not in text
clock=json.loads((R/'verification/v28/clock_fault_campaign.json').read_text())
assert clock['total']==clock['matched']==14
v27=json.loads((R/'verification/v27/synthetic_camera_campaign.json').read_text())
assert v27['total']==v27['matched']==14
report={'release':'2.8.0','date_jst':'2026-10-16',
 'basis':'ASSIGNMENT_2026-10-08; V2.7 CODE; OFFICIAL_DOCS',
 'scope':'OFFLINE_TESTS_MOCK_ROS_SYNTHETIC_FAULTS_STATIC_GAZEBO_SDF_ONLY',
 'python_tests':int(m.group(1)),'python_tests_pass':True,
 'new_sim_clock_fault_conditions':clock['total'],'new_sim_clock_fault_matched':clock['matched'],
 'prior_camera_fault_conditions':v27['total'],'prior_camera_fault_matched':v27['matched'],
 'sdf_controlled_scenes':3,'launch_plans':4,'preregistered_trials_planned_not_run':30,
 'ros2_available':bool(shutil.which('ros2')),'gz_available':bool(shutil.which('gz')),
 'gazebo_physics':'NOT_TESTED','jev_real_api':'NOT_TESTED','qwen_real_api':'NOT_TESTED',
 'rosbag_real_recording':'NOT_TESTED','submission_video':'NOT_CREATED',
 'limitations':'Not a real ROS middleware/Gazebo run, not a model accuracy study, no pickup/transport.'}
(R/'verification/v28/verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
PY
