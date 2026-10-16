#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p verification/v20
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
# Full legacy regression campaigns, repeated on the modified v2.0 source tree.
bash scripts/v19_verify.sh > verification/v20/legacy_campaigns.stdout 2>&1
python3 -m unittest discover -s tests -v > verification/v20/v20_unittest.log 2>&1
python3 scripts/v20_bridge_audit.py > verification/v20/v20_bridge.json
python3 scripts/v20_orchestrate.py --plan --scenario live --capture-rosbag > verification/v20/v20_sim_bag_plan.json
python3 -m compileall -q rescuemind ros scripts tests
for p in scripts/*.sh; do bash -n "$p"; done
python3 - <<'PY'
import json, re, shutil
from pathlib import Path
v=Path('verification/v20')
s=(v/'v20_unittest.log').read_text()
m=re.search(r'Ran (\d+) tests in',s)
assert m and 'OK' in s and 'FAILED' not in s
bridge=json.loads((v/'v20_bridge.json').read_text())
assert bridge['ok'] and bridge['topic_mappings']==5
plan=json.loads((v/'v20_sim_bag_plan.json').read_text())
assert any('--use-sim-time' in ' '.join(cmd) and '/clock' in ' '.join(cmd) for cmd in plan['services'])
assert plan['readiness'][-1].endswith('v20_live_readiness.sh')
previous=json.loads(Path('verification/v19/v19_TEST_REPORT.json').read_text())
assert previous['synthetic_timeline_matched']==10 and previous['synthetic_closed_loop_matched']==6
report={
 'version':'2.0.0', 'status':'OFFLINE_VERIFICATION_PASSED',
 'python_tests_passed':int(m.group(1)),
 'legacy_v19_regressions':'PASS', 'previous_causal_timeline_synthetic_cases':10,
 'previous_closed_loop_ideal_cases':6,
 'v20_clock_topic_mapping':'STATIC_PASS',
 'v20_rosbag_sim_clock_launch_plan':'PASS',
 'v20_clock_probe_logic':'TESTED_WITH_SYNTHETIC_CLOCK_AND_SENSOR_STAMPS',
 'legacy_fault_campaigns':previous['legacy_fault_campaign_cases'],
 'gazebo_available':bool(shutil.which('gz')),
 'ros2_available':bool(shutil.which('ros2')),
 'real_ros_gazebo':'UNTESTED', 'real_jev':'UNTESTED', 'real_qwen38':'UNTESTED',
 'rosbag2_real_capture':'UNTESTED', 'final_robot_video':'NOT_CREATED',
 'warning':'No model accuracy or physics success was measured. Offline tests only.'}
(v/'V20_VERIFICATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
PY
