#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p verification/v31
# Reproduce all earlier fault-injection work, SDF checks and current unittest suite.
bash scripts/v30_verify.sh > verification/v31/prior_work_regression.log 2>&1
python3 -m unittest discover -s tests -q > verification/v31/unittest.log 2>&1
python3 scripts/v31_graph_fault_campaign.py > verification/v31/graph_campaign_stdout.json
python3 -m compileall -q rescuemind ros scripts tests
for f in scripts/*.sh; do bash -n "$f"; done
for scene in nominal swapped empty; do
 python3 scripts/v31_orchestrate.py --plan --scenario live --scene "$scene" --capture-rosbag > "verification/v31/plan_${scene}.json"
done
python3 scripts/v31_orchestrate.py --plan --scenario motion-check --scene nominal > verification/v31/plan_motion.json
python3 - <<'PY'
import json,shutil,re
from pathlib import Path
from rescuemind.runtime_guard_graph import GUARD_NAME
R=Path.cwd();data=(R/'verification/v31/unittest.log').read_text()
m=re.search(r'Ran (\d+) tests in',data)
assert m and re.search(r'^OK\s*$',data,re.M) and 'FAILED' not in data
for scene in ('nominal','swapped','empty'):
 p=json.loads((R/f'verification/v31/plan_{scene}.json').read_text())
 assert any('runtime_guard_graph_watch.py' in ' '.join(c) for c in p['services'])
 assert any('guard_graph_watch.jsonl' in ' '.join(c) for c in p['services'])
 assert any('ros2 bag record' in ' '.join(c) for c in p['services'])
p=json.loads((R/'verification/v31/plan_motion.json').read_text())
assert any('runtime_guard_graph_watch.py' in ' '.join(c) for c in p['services'])
c=json.loads((R/'verification/v31/graph_fault_campaign.json').read_text())
assert c['tested']==c['matched'] and c['all_matched'] and GUARD_NAME=='rescuemind_velocity_guard'
report={'release':'3.1.0','assignment':'Physical AI応用1講座 最終課題（10/8版）',
        'unit_tests':int(m.group(1)),'unit_tests_passed':True,
        'v31_synthetic_graph_conditions':c['tested'],
        'v31_synthetic_graph_matched':c['matched'],
        'real_ros2_installed':bool(shutil.which('ros2')),
        'real_gazebo_installed':bool(shutil.which('gz')),
        'runtime_graph_monitor_implementation':'IMPLEMENTED_BUT_UNTESTED_WITH_REAL_ROS',
        'live_ros_graph_monitor':'NOT_TESTED','real_Jev_API':'NOT_TESTED',
        'real_Qwen_API':'NOT_TESTED','real_Gazebo_movement':'NOT_TESTED',
        'real_ROSbag_capture':'NOT_TESTED','submission_video':'NOT_CREATED',
        'physical_grasping':'NOT_IMPLEMENTED',
        'claim_scope':'UNIT_TESTS_MOCK_ROS_SYNTHETIC_GRAPH_STATIC_GAZEBO_CONTRACTS'}
(R/'verification/v31/verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
PY
