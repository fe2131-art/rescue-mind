#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p verification/v23
python3 scripts/v22_generate_scenes.py > verification/v23/scenes_regenerated.json
python3 scripts/v23_plan_experiment.py --seed 20261016 --repetitions 5 > verification/v23/protocol_generation.json
python3 -m unittest discover -s tests -v > verification/v23/unittest.log 2>&1
python3 -m compileall -q rescuemind ros scripts tests
for f in scripts/*.sh; do bash -n "$f"; done
python3 scripts/v22_orchestrate.py --plan --scenario live --scene nominal > verification/v23/nominal_plan.json
python3 scripts/v22_orchestrate.py --plan --scenario live --scene swapped > verification/v23/swapped_plan.json
python3 scripts/v22_orchestrate.py --plan --scenario live --scene empty > verification/v23/empty_plan.json
python3 - <<'PY'
import json,re,shutil
from pathlib import Path
from rescuemind.v23_protocol import validate_protocol
from rescuemind.scene_variants import audit_scenarios
from rescuemind.gazebo_transport_contract import validate_static
r=Path.cwd();p=json.loads((r/'experiments/v23_locked_protocol.json').read_text());validate_protocol(p)
scenes=audit_scenarios(r/'worlds/scenarios')
for x in ('nominal','swapped','empty'):
 validate_static(r/f'worlds/scenarios/rescuemind_{x}.sdf',r/'configs/ros_gz_bridge_v20.yaml')
 plan=json.loads((r/f'verification/v23/{x}_plan.json').read_text())
 assert plan['scene']==x and len(plan['scene_sha256'])==64
s=(r/'verification/v23/unittest.log').read_text()
m=re.search(r'Ran (\d+) tests in',s)
assert m and '\nOK\n' in s and 'FAILED' not in s
report={'version':'2.3','as_of_date':'2026-10-16','verification_scope':'OFFLINE_SOFTWARE_STATIC_AND_MOCKED_TESTS',
        'python_tests_passed':int(m.group(1)),
        'controlled_scenes_static':scenes,'experimental_conditions':6,
        'preregistered_trials':p['planned_n'],'fixed_protocol_seed':p['seed'],
        'experimental_real_trials_executed':0,
        'real_gazebo_physics':'NOT_TESTED','real_jev_api':'NOT_TESTED',
        'real_qwen_api':'NOT_TESTED','actual_rosbag':'NOT_TESTED',
        'actual_submission_video':'NOT_CREATED',
        'gazebo_present':shutil.which('gz') is not None,'ros2_present':shutil.which('ros2') is not None,
        'limitations':['Model API results unavailable','Scene-rendered camera image unknown',
                       'Synthetic test responses are not model performance',
                       'Repeated frames from same 3 scenes not independent population samples']}
(r/'verification/v23/verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
PY
