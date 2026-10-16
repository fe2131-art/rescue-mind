#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p verification/v25
python3 -m unittest discover -s tests -v > verification/v25/unittest.log 2>&1
python3 scripts/v25_camera_audit.py > verification/v25/camera_audit_stdout.json
python3 -m compileall -q rescuemind ros scripts tests
for f in scripts/*.sh; do bash -n "$f"; done
python3 scripts/v22_orchestrate.py --plan --scenario live --scene nominal > verification/v25/plan_nominal.json
python3 scripts/v22_orchestrate.py --plan --scenario live --scene swapped > verification/v25/plan_swapped.json
python3 scripts/v22_orchestrate.py --plan --scenario live --scene empty > verification/v25/plan_empty.json
python3 scripts/v24_fault_campaign.py > verification/v25/v24_fault_stdout.json
python3 - <<'PYTHON'
import json,re,shutil
from pathlib import Path
R=Path.cwd()
from rescuemind.v23_protocol import validate_protocol
validate_protocol(json.loads((R/'experiments/v23_locked_protocol.json').read_text()))
log=(R/'verification/v25/unittest.log').read_text()
m=re.search(r'Ran (\d+) tests in',log)
assert m and 'OK' in log and 'FAILED' not in log
for scene in ('nominal','swapped','empty'):
    data=json.loads((R/f'verification/v25/plan_{scene}.json').read_text())
    assert data['scene']==scene
p=json.loads((R/'verification/v25/camera_projection.json').read_text())
assert p['static_scene_audit']['pass']
out={'release':'2.5.0','date':'2026-10-16','scope':'OFFLINE_PYTHON_MOCK_ROS_STATIC_FOV',
     'python_tests':int(m.group(1)),'tests_passed':True,
     'camera_fov_static_pass':True,
     'locked_preregistered_trials':30,
     'ros2_in_container':bool(shutil.which('ros2')),'gz_in_container':bool(shutil.which('gz')),
     'gazebo_physical_run':'NOT_TESTED','jev_live_api':'NOT_TESTED','qwen_live_api':'NOT_TESTED',
     'actual_mp4_submission':'NOT_CREATED',
     'limitations':['camera geometric projection cannot detect occlusion or exposure','VLM real accuracy unmeasured','artificial ROS integration is not Gazebo']}
(R/'verification/v25/verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False,indent=2))
PYTHON
