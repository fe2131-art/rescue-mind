#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p verification/v18
python3 -m unittest discover -s tests -v > verification/v18/v18_unittest.log 2>&1
python3 scripts/v17_closed_loop_campaign.py > verification/v18/v18_closed_loop.stdout
python3 scripts/v17_stack_contract.py > verification/v18/v18_stack_contract.stdout
python3 scripts/v18_motion_evidence_campaign.py > verification/v18/v18_motion_campaign.stdout
python3 scripts/validate_gazebo_world.py > verification/v18/v18_gazebo_static.stdout
python3 scripts/run_waypoint_regression.py > verification/v18/v18_kinematic.stdout
python3 scripts/v16_orchestrate.py --plan --scenario live > verification/v18/v18_plan_only.json
for f in scripts/*.sh; do bash -n "$f"; done
python3 - <<'PY'
import json,re,shutil
from pathlib import Path
p=Path('verification/v18');s=(p/'v18_unittest.log').read_text()
m=re.search(r'Ran (\d+) tests in',s)
assert m and 'OK' in s and 'FAILED' not in s
motion=json.loads((p/'synthetic_motion_evidence_campaign.json').read_text())
cl=json.loads((Path('verification/v17')/'campaign_summary.json').read_text())
contract=json.loads((Path('verification/v17')/'stack_contract.json').read_text())
assert motion['passed']==6 and motion['total']==6
assert cl['expected_outcomes_matched']==6 and contract['ok']
report={'version':'1.8.0','scope':'OFFLINE_PYTHON_AND_SYNTHETIC_ONLY',
        'python_tests_passed':int(m.group(1)),
        'synthetic_motion_evidence_cases':motion['total'],
        'synthetic_motion_expected_results_matched':motion['passed'],
        'scripted_closed_loop_cases':cl['cases'],
        'scripted_closed_loop_expected_results_matched':cl['expected_outcomes_matched'],
        'static_ros_gazebo_contract':True,'python_ideal_kinematics':True,
        'local_available_tools':{x:bool(shutil.which(x)) for x in ('ros2','gz','nvidia-smi')},
        'Jev_live_api':'UNTESTED','Qwen_live_api':'UNTESTED',
        'real_gazebo_robot':'UNTESTED','submission_robot_video':'NOT_CREATED'}
(p/'v18_TEST_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
PY
