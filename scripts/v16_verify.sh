#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p outputs/release
python3 -m unittest discover -s tests -v > outputs/release/v16_unittest.log 2>&1
python3 scripts/v16_fault_campaign.py > outputs/release/v16_odometry_campaign.stdout
python3 scripts/validate_gazebo_world.py > outputs/release/v16_static_gazebo.stdout
python3 scripts/run_waypoint_regression.py > outputs/release/v16_kinematic.stdout
python3 scripts/v16_orchestrate.py --plan --scenario motion-check > outputs/release/v16_motion_plan.json
python3 scripts/v16_orchestrate.py --plan --scenario live > outputs/release/v16_live_plan.json
for f in scripts/*.sh; do bash -n "$f"; done
python3 - <<'PY'
import json,re,shutil
from pathlib import Path
out=Path('outputs/release')
log=(out/'v16_unittest.log').read_text()
count=re.search(r'Ran (\d+) tests in',log)
assert count and '\nOK' in log and '\nFAILED' not in log
f=json.loads((out/'v16_odometry_campaign.json').read_text());assert f['cases']==f['passed']==600
report={'version':'v1.6','date':'2026-10-16','scope':'OFFLINE ONLY',
        'unit_tests':int(count.group(1)),'unit_tests_status':'PASS',
        'odom_injected_cases':600,'odom_passed':600,
        'sdf_static':'PASS','ideal_kinematic':'PASS','shell_syntax':'PASS',
        'ros_tools':{x:bool(shutil.which(x)) for x in ('ros2','gz','nvidia-smi')},
        'Jev_API_real':'UNTESTED','Qwen_API_real':'UNTESTED',
        'Gazebo_actual_runtime':'UNTESTED','submission_robot_video':'NOT CREATED',
        'note':'synthetic tests do not measure robot or VLM success rates'}
(out/'v16_VERIFICATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
PY
