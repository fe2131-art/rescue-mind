#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p verification/v26
python3 -m unittest discover -s tests -v > verification/v26/unittest.log 2>&1
python3 scripts/v26_stationary_campaign.py > verification/v26/campaign_stdout.json
python3 scripts/v25_camera_audit.py > verification/v26/v25_projection_stdout.json
python3 scripts/v24_fault_campaign.py > verification/v26/v24_fault_stdout.json
python3 -m compileall -q rescuemind ros scripts tests
for f in scripts/*.sh; do bash -n "$f"; done
for scene in nominal swapped empty; do
 python3 scripts/v26_orchestrate.py --plan --scenario live --scene "$scene" > "verification/v26/plan_${scene}.json"
done
python3 scripts/v26_orchestrate.py --plan --scenario motion-check --scene nominal > verification/v26/plan_motion.json
python3 - <<'PY'
import json,re,shutil,xml.etree.ElementTree as ET
from pathlib import Path
R=Path.cwd()
from rescuemind.scene_variants import audit_scenarios
from rescuemind.gazebo_transport_contract import validate_static
from rescuemind.v23_protocol import validate_protocol
from rescuemind.v26_stationary_evidence import audit_stationarity
assert audit_scenarios(R/'worlds/scenarios')['pass']
for scene in ('nominal','swapped','empty'):
    validate_static(R/f'worlds/scenarios/rescuemind_{scene}.sdf',R/'configs/ros_gz_bridge_v20.yaml')
    plan=json.loads((R/f'verification/v26/plan_{scene}.json').read_text())
    assert plan['scene']==scene and '--run-live' in str(plan['mission'])
assert '--motion-check' in str(json.loads((R/'verification/v26/plan_motion.json').read_text())['mission'])
validate_protocol(json.loads((R/'experiments/v23_locked_protocol.json').read_text()))
text=(R/'verification/v26/unittest.log').read_text()
m=re.search(r'Ran (\d+) tests in',text)
assert m and 'OK' in text and 'FAILED' not in text and 'Traceback' not in text
campaign=json.loads((R/'verification/v26/synthetic_stationary_campaign.json').read_text())
assert campaign['matched']==campaign['total']==12
old=json.loads((R/'verification/v24/v24_synthetic_fault_campaign.json').read_text())
assert old['all_match']
assert len(list((R/'worlds/scenarios').glob('rescuemind_*.sdf')))==3
out={'release':'2.6.0','date_jst':'2026-10-16',
 'scope':'OFFLINE_UNIT_MOCK_ROS_STATIC_SDF_SYNTHETIC',
 'python_tests':int(m.group(1)),'python_all_passed':True,
 'new_synthetic_stationary_conditions':campaign['total'],'new_synthetic_matched':campaign['matched'],
 'old_expected_denial_conditions':old['n'],'old_denial_matched':sum(r['matched'] for r in old['cases']),
 'gazebo_sdf_scenes':3,'plans_checked':4,'preregistered_trial_plans':30,
 'simulator_in_container':bool(shutil.which('gz')),'ros_in_container':bool(shutil.which('ros2')),
 'true_gazebo_run':'NOT_TESTED','true_jev_api':'NOT_TESTED','true_qwen_api':'NOT_TESTED',
 'rosbag_runtime':'NOT_TESTED','submission_mp4':'NOT_CREATED',
 'important':'Synthetic/MOCK success is not real-robot or API performance'}
(R/'verification/v26/verification.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(out,indent=2,ensure_ascii=False))
PY
