#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p verification/v24
# All previous functionality + updated controlled-scene tests
python3 -m unittest discover -s tests -v > verification/v24/unittest.log 2>&1
python3 scripts/v24_fault_campaign.py > verification/v24/fault_campaign_stdout.json
python3 -m compileall -q rescuemind ros scripts tests
for f in scripts/*.sh; do bash -n "$f"; done
python3 scripts/v22_orchestrate.py --plan --scenario live --scene nominal > verification/v24/plan_nominal.json
python3 scripts/v22_orchestrate.py --plan --scenario live --scene swapped > verification/v24/plan_swapped.json
python3 scripts/v22_orchestrate.py --plan --scenario live --scene empty > verification/v24/plan_empty.json
python3 - <<'PY'
import json,re,shutil
from pathlib import Path
from rescuemind.v23_protocol import validate_protocol
from rescuemind.scene_variants import audit_scenarios
from rescuemind.gazebo_transport_contract import validate_static
R=Path.cwd()
proto=json.loads((R/'experiments/v23_locked_protocol.json').read_text())
validate_protocol(proto)
scenes=audit_scenarios(R/'worlds/scenarios')
for name in ('nominal','swapped','empty'):
 validate_static(R/f'worlds/scenarios/rescuemind_{name}.sdf',R/'configs/ros_gz_bridge_v20.yaml')
 plan=json.loads((R/f'verification/v24/plan_{name}.json').read_text())
 assert plan['scene']==name
assert scenes['pass']
log=(R/'verification/v24/unittest.log').read_text()
m=re.search(r'Ran (\d+) tests in',log)
assert m and '\nOK\n' in log and 'FAILED' not in log
fault=json.loads((R/'verification/v24/v24_synthetic_fault_campaign.json').read_text())
assert fault['all_match']
result={'version':'2.4','as_of':'2026-10-16','scope':'OFFLINE_TESTS_STATIC_AND_SYNTHETIC',
        'python_tests':int(m.group(1)),'synthetic_negative_fault_cases':fault['n'],
        'synthetic_negative_fault_correct':sum(e['matched'] for e in fault['cases']),
        'planned_real_trials':proto['planned_n'],'real_trials_executed_in_current_container':0,
        'scene_sdf_static_pass':True,
        'ros2_available':bool(shutil.which('ros2')),'gz_available':bool(shutil.which('gz')),
        'actual_jev_api':'NOT_TESTED','actual_qwen_api':'NOT_TESTED',
        'gazebo_physics':'NOT_TESTED','robot_submission_video':'NOT_CREATED',
        'notes':['v2.4 audit explicitly distinguishes intentional AI rejection from crash',
                 'offline fixtures are NOT robot/VLM accuracy evidence']}
(R/'verification/v24/verification.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(result,indent=2,ensure_ascii=False))
PY
