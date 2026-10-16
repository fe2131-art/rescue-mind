#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p verification/v29
python3 -m unittest discover -s tests -v > verification/v29/unittest.log 2>&1
python3 scripts/v29_checkpoint_campaign.py | tee verification/v29/jev_campaign_stdout.json
python3 scripts/v28_clock_campaign.py > verification/v29/v28_clock_campaign_stdout.json
python3 scripts/v27_acquisition_campaign.py > verification/v29/v27_acquisition_campaign_stdout.json
python3 scripts/v26_stationary_campaign.py > verification/v29/v26_stationary_campaign_stdout.json
python3 scripts/v24_fault_campaign.py > verification/v29/v24_denial_campaign_stdout.json
python3 scripts/v25_camera_audit.py > verification/v29/v25_camera_stdout.json
python3 -m compileall -q rescuemind ros scripts tests
for f in scripts/*.sh; do bash -n "$f"; done
for scene in nominal swapped empty; do
 python3 scripts/v29_orchestrate.py --plan --scenario live --scene "$scene" > "verification/v29/plan_${scene}.json"
done
python3 scripts/v29_orchestrate.py --plan --scenario motion-check --scene nominal --capture-rosbag > verification/v29/plan_motion_with_bag.json
python3 - <<'PY'
import json,re,shutil
from pathlib import Path
from rescuemind.scene_variants import audit_scenarios
from rescuemind.gazebo_transport_contract import validate_static
from rescuemind.v23_protocol import validate_protocol
from rescuemind import jev
R=Path.cwd()
assert audit_scenarios(R/'worlds/scenarios')['pass']
for scene in ('nominal','swapped','empty'):
  validate_static(R/f'worlds/scenarios/rescuemind_{scene}.sdf',R/'configs/ros_gz_bridge_v20.yaml')
  plan=json.loads((R/f'verification/v29/plan_{scene}.json').read_text())
  assert plan['scene']==scene and '--run-live' in str(plan['mission'])
plan=json.loads((R/'verification/v29/plan_motion_with_bag.json').read_text())
assert any('rosbag' in str(s) for s in plan['services'])
validate_protocol(json.loads((R/'experiments/v23_locked_protocol.json').read_text()))
text=(R/'verification/v29/unittest.log').read_text()
m=re.search(r'Ran (\d+) tests in',text)
assert m and re.search(r'^OK\s*$',text,re.M) and 'FAILED' not in text
synth=json.loads((R/'verification/v29/jev_checkpoint_campaign.json').read_text())
assert synth['total']==synth['matched']==10
assert jev.MODEL_ID=='jev-1.14.0'
report={'release':'2.9.0','date_jst':'2026-10-16','python_tests':int(m.group(1)),
 'python_tests_pass':True,'jev_synthetic_negatives':synth['total'],'jev_synthetic_matched':synth['matched'],
 'sdf_scenes_pass':3,'plans_checked':4,'ros2_available':bool(shutil.which('ros2')),'gz_available':bool(shutil.which('gz')),
 'bag_finalization_test':'ACTUAL_PYTHON_SUBPROCESS_SIGINT_ONLY_NOT_ROSBAG_RUNTIME',
 'jev_protocol_test':'OFFLINE_SYNTHETIC_NOT_TYPE_SAFE_API_CONFORMANCE_CERTIFICATION',
 'real_gazebo':'NOT_TESTED','real_jev_api':'NOT_TESTED','real_qwen_api':'NOT_TESTED',
 'actual_rosbag_capture':'NOT_TESTED','submission_mp4':'NOT_CREATED','planned_trials_not_executed':30,
 'physical_pickup':False,'nav2_dynamic_replanning':False}
(R/'verification/v29/verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
PY
