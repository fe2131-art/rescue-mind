#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p verification/v22
python3 scripts/v22_generate_scenes.py > verification/v22/scene_generation.json
python3 -m unittest discover -s tests -v > verification/v22/unit_tests.log 2>&1
python3 -m compileall -q rescuemind ros scripts tests
for f in scripts/*.sh; do bash -n "$f"; done
for scene in nominal swapped empty; do
  python3 scripts/v22_orchestrate.py --plan --scenario live --scene "$scene" > "verification/v22/plan_${scene}.json"
done
python3 scripts/v22_orchestrate.py --plan --scenario motion-check --scene nominal > verification/v22/plan_motion.json
python3 - <<'PY'
import json,re,shutil
from pathlib import Path
from rescuemind.scene_variants import audit_scenarios
from rescuemind.gazebo_transport_contract import validate_static
root=Path.cwd()
v=root/'verification/v22'
s=(v/'unit_tests.log').read_text()
m=re.search(r'Ran (\d+) tests in',s)
assert m and 'OK' in s and 'FAILED' not in s
scene=audit_scenarios(root/'worlds/scenarios')
for name in ('nominal','swapped','empty'):
  plan=json.loads((v/f'plan_{name}.json').read_text())
  assert plan['scene']==name and len(plan['scene_sha256'])==64
  assert plan['mission'][-1].find('--run-live')>=0
  assert plan['services'][0][-1].endswith(f'rescuemind_{name}.sdf')
  assert 'jev' in plan['notes'].lower()
  validate_static(root/f'worlds/scenarios/rescuemind_{name}.sdf',root/'configs/ros_gz_bridge_v20.yaml')
report={'version':'2.2','scope':'OFFLINE_STATIC_AND_MOCKED_ROS',
        'unit_tests_passed':int(m.group(1)),
        'scene_variants_static':scene,'orchestrator_plan_count':4,
        'real_gazebo_physics':'NOT_TESTED','real_jev_api':'NOT_TESTED',
        'real_qwen_api':'NOT_TESTED','real_rosbag':'NOT_TESTED',
        'real_submission_mp4':'NOT_CREATED',
        'gazebo_executable_present':bool(shutil.which('gz')),
        'ros2_executable_present':bool(shutil.which('ros2')),
        'warning':'Generated Gazebo SDFs are not rendered; no actual vision recognition statistics.'}
(v/'V22_VERIFICATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
PY
