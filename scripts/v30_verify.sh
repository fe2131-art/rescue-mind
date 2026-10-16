#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p verification/v30
python3 -m unittest discover -s tests -v > verification/v30/unittest.log 2>&1
python3 scripts/v30_orchestration_campaign.py > verification/v30/campaign_stdout.json 2> verification/v30/campaign_unittest.log
python3 scripts/v29_checkpoint_campaign.py > verification/v30/v29_jev_campaign_stdout.json
python3 scripts/v28_clock_campaign.py > verification/v30/v28_clock_campaign_stdout.json
python3 scripts/v27_acquisition_campaign.py > verification/v30/v27_acquisition_campaign_stdout.json
python3 scripts/v26_stationary_campaign.py > verification/v30/v26_stationary_campaign_stdout.json
python3 scripts/v24_fault_campaign.py > verification/v30/v24_denial_campaign_stdout.json
python3 scripts/v25_camera_audit.py > verification/v30/v25_camera_stdout.json
python3 -m compileall -q rescuemind ros scripts tests
for f in scripts/*.sh; do bash -n "$f"; done
for scene in nominal swapped empty; do
  python3 scripts/v30_orchestrate.py --plan --scenario live --scene "$scene" --capture-rosbag > "verification/v30/plan_${scene}.json"
done
python3 scripts/v30_orchestrate.py --plan --scenario motion-check --scene nominal > verification/v30/plan_motion_without_bag.json
python3 - <<'PY'
import json,shutil,re
from pathlib import Path
from rescuemind.scene_variants import audit_scenarios
from rescuemind.gazebo_transport_contract import validate_static
from rescuemind.v23_protocol import validate_protocol
from rescuemind import jev
r=Path.cwd();log=(r/'verification/v30/unittest.log').read_text()
m=re.search(r'Ran (\d+) tests in',log)
assert m and re.search(r'^OK\s*$',log,re.M) and 'FAILED' not in log
assert audit_scenarios(r/'worlds/scenarios')['pass']
for scene in ('nominal','swapped','empty'):
  validate_static(r/f'worlds/scenarios/rescuemind_{scene}.sdf',r/'configs/ros_gz_bridge_v20.yaml')
  p=json.loads((r/f'verification/v30/plan_{scene}.json').read_text())
  assert p['scene']==scene and any('ros2 bag record' in str(s) for s in p['services'])
p=json.loads((r/'verification/v30/plan_motion_without_bag.json').read_text())
assert any('odom_evidence_recorder.py' in str(x) for x in p['services'])
assert not any('ros2 bag record' in str(x) for x in p['services'])
validate_protocol(json.loads((r/'experiments/v23_locked_protocol.json').read_text()))
assert jev.MODEL_ID=='jev-1.14.0'
campaign=json.loads((r/'verification/v30/orchestration_campaign.json').read_text())
assert campaign['successful'] and campaign['scenario_tests']>=9
art=json.loads((r/'verification/v29/jev_checkpoint_campaign.json').read_text())
assert art['total']==art['matched']==10
report={'release':'3.0.0','source':'Physical-AI応用1講座-最終課題.txt 10/8','python_tests':int(m.group(1)),
'python_tests_pass':True,'v30_mock_orchestration_scenarios':campaign['scenario_tests'],'v30_mock_scenarios_pass':True,
'v29_jev_synthetic_cases':art['total'],'v29_jev_synthetic_matched':art['matched'],
'sdf_scenes_pass':3,'offline_plans_checked':4,'ros2_available':bool(shutil.which('ros2')),
'gz_available':bool(shutil.which('gz')),'scope':'OFFLINE_ONLY_SUBPROCESS_SIGNALS_AND_MOCKED_RUNTIME',
'real_gazebo':'NOT_TESTED','real_jev_api':'NOT_TESTED','real_qwen_api':'NOT_TESTED',
'rosbag2_real_capture':'NOT_TESTED','real_video':'NOT_CREATED','planned_trials_not_executed':30,
'physical_pickup':False,'nav2_dynamic_replanning':False}
(r/'verification/v30/verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
PY
