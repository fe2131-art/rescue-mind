#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p verification/v17
python3 -m unittest discover -s tests -v > verification/v17/v17_unittest.log 2>&1
python3 scripts/v17_closed_loop_campaign.py > verification/v17/v17_closed_loop.stdout
python3 scripts/v17_stack_contract.py > verification/v17/v17_stack_contract.stdout
python3 scripts/v17_plot_experiments.py > verification/v17/v17_plot.stdout
python3 scripts/validate_gazebo_world.py > verification/v17/v17_static_gazebo.stdout
python3 scripts/run_waypoint_regression.py > verification/v17/v17_kinematic.stdout
python3 scripts/v16_orchestrate.py --plan --scenario motion-check > verification/v17/v17_plan_motion.json
python3 scripts/v16_orchestrate.py --plan --scenario live > verification/v17/v17_plan_live.json
for f in scripts/*.sh; do bash -n "$f"; done
python3 - <<'PY'
import json,re,shutil,subprocess,sys
from pathlib import Path
p=Path('verification/v17')
log=(p/'v17_unittest.log').read_text()
m=re.search(r'Ran (\d+) tests in',log)
assert m and 'OK' in log and 'FAILED' not in log,log[-1500:]
loop=json.loads((p/'campaign_summary.json').read_text())
static=json.loads((p/'stack_contract.json').read_text())
assert loop['cases']==6 and loop['expected_outcomes_matched']==6
assert static['ok']
info={'version':'1.7.0','date':'2026-10-16',
      'scope':'OFFLINE SCRIPTED / STATIC / PYTHON TESTS ONLY',
      'unittest_count':int(m.group(1)),'unittest':'PASS',
      'scripted_closed_loop_scenarios':loop['cases'],
      'scripted_expected_outcomes_matched':loop['expected_outcomes_matched'],
      'gazebo_ros_bridge_static_contract':'PASS',
      'ideal_kinematics':'PASS','sdf_static':'PASS',
      'script_syntax':'PASS',
      'tools_in_this_environment':{key:bool(shutil.which(key)) for key in ('ros2','gz','nvidia-smi')},
      'real_Jev_API':'UNTESTED','real_Qwen_API':'UNTESTED','real_Gazebo_robot':'UNTESTED',
      'robot_video_60_180s':'NOT_CREATED',
      'limitations':'Scripted permit is not real AI; ideal unicycle is not Gazebo; no performance/safety guarantees.'}
(p/'v17_TEST_REPORT.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(info,ensure_ascii=False,indent=2))
PY
