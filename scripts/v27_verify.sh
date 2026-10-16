#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p verification/v27
python3 -m unittest discover -s tests -v > verification/v27/unittest.log 2>&1
python3 scripts/v27_acquisition_campaign.py > verification/v27/acquisition_campaign_stdout.json
python3 scripts/v26_stationary_campaign.py > verification/v27/previous_stationary_campaign_stdout.json
python3 scripts/v24_fault_campaign.py > verification/v27/previous_negative_campaign_stdout.json
python3 scripts/v25_camera_audit.py > verification/v27/previous_camera_geometry_stdout.json
python3 -m compileall -q rescuemind ros scripts tests
for f in scripts/*.sh; do bash -n "$f"; done
for scene in nominal swapped empty; do
  python3 scripts/v27_orchestrate.py --plan --scenario live --scene "$scene" > "verification/v27/plan_${scene}.json"
done
python3 scripts/v27_orchestrate.py --plan --scenario motion-check --scene nominal > verification/v27/plan_motion.json
python3 - <<'PY'
import json,re,shutil,xml.etree.ElementTree as ET
from pathlib import Path
from rescuemind.scene_variants import audit_scenarios
from rescuemind.gazebo_transport_contract import validate_static
from rescuemind.v23_protocol import validate_protocol
R=Path.cwd()
assert audit_scenarios(R/'worlds/scenarios')['pass']
for scene in ('nominal','swapped','empty'):
    validate_static(R/f'worlds/scenarios/rescuemind_{scene}.sdf',R/'configs/ros_gz_bridge_v20.yaml')
    d=json.loads((R/f'verification/v27/plan_{scene}.json').read_text())
    assert '--run-live' in str(d['mission'])
assert '--motion-check' in str(json.loads((R/'verification/v27/plan_motion.json').read_text())['mission'])
validate_protocol(json.loads((R/'experiments/v23_locked_protocol.json').read_text()))
text=(R/'verification/v27/unittest.log').read_text()
m=re.search(r'Ran (\d+) tests in',text)
assert m and 'OK' in text and 'FAILED' not in text
cam=json.loads((R/'verification/v27/synthetic_camera_campaign.json').read_text())
assert cam['matched']==cam['total']==14
sta=json.loads((R/'verification/v26/synthetic_stationary_campaign.json').read_text())
assert sta['matched']==sta['total']==12
negative=json.loads((R/'verification/v24/v24_synthetic_fault_campaign.json').read_text())
assert negative['all_match']
report={'release':'2.7.0','date_jst':'2026-10-16','scope':'OFFLINE_UNIT_MOCK_ROS_SYNTHETIC_IMAGE_STATIC_SDF',
 'python_tests':int(m.group(1)),'python_all_passed':True,
 'new_synthetic_image_conditions':cam['total'],'new_synthetic_image_matched':cam['matched'],
 'previous_stationary_fault_conditions':sta['total'],'previous_denial_fault_conditions':negative['n'],
 'controlled_sdf_scenes':3,'supervisor_command_plans':4,'preregistered_proposed_trials':30,
 'ros_cli_here':bool(shutil.which('ros2')),'gazebo_cli_here':bool(shutil.which('gz')),
 'actual_gazebo':'NOT_TESTED','actual_jev_api':'NOT_TESTED',
 'actual_qwen_api':'NOT_TESTED','actual_rosbag':'NOT_TESTED','submission_video':'NOT_CREATED',
 'warning':'No empirical object-recognition accuracy or actual wheel-motion verified.'}
(R/'verification/v27/verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
PY
