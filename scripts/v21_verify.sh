#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p verification/v21
python3 -m unittest discover -s tests -v > verification/v21/all_unittests.log 2>&1
python3 -m compileall -q rescuemind ros scripts tests
for f in scripts/*.sh; do bash -n "$f"; done
python3 scripts/v21_orchestrate.py --plan --scenario live --capture-rosbag > verification/v21/live_plan.json
python3 scripts/v21_orchestrate.py --plan --scenario motion-check > verification/v21/motion_plan.json
python3 - <<'PY'
from pathlib import Path
import json,re,shutil
root=Path('verification/v21')
log=(root/'all_unittests.log').read_text()
m=re.search(r'Ran (\d+) tests in',log)
assert m and 'OK' in log and 'FAILED' not in log
live=json.loads((root/'live_plan.json').read_text())
assert live['readiness'][-1].endswith('v21_live_readiness.sh')
assert any('/clock' in ' '.join(c) and '--use-sim-time' in ' '.join(c) for c in live['services'])
assert '--run-live' in live['mission'][-1]
report={
 'version':'2.1.0','status':'OFFLINE_ONLY_PASS','unit_tests_passed':int(m.group(1)),
 'gazebo_static_cross_contract':'PASS','gazebo_transport_runtime':'NOT_AVAILABLE_IN_THIS_CONTAINER',
 'ros_gazebo_physics':'NOT_TESTED', 'real_jev_api':'NOT_TESTED', 'real_qwen_api':'NOT_TESTED',
 'rosbag_real_capture':'NOT_TESTED','final_real_robot_mp4':'NOT_CREATED',
 'motion_check_plan':'PASS','live_jev_qwen_plan':'PASS',
 'gazebo_executable_present':bool(shutil.which('gz')),
 'ros2_executable_present':bool(shutil.which('ros2')),
 'scope_notice':'Unit tests and mocked Gazebo topic-list behavior; no real Gazebo or model inference.'
}
(root/'V21_VERIFICATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
PY
