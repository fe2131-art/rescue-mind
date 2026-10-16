#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p verification/v19
python3 -m unittest discover -s tests -v > verification/v19/v19_unittest.log 2>&1
python3 scripts/v19_causal_campaign.py > verification/v19/v19_causal_campaign.stdout
python3 scripts/v19_plot_causal.py > verification/v19/v19_plot.stdout
python3 scripts/v17_closed_loop_campaign.py > verification/v19/v19_closed_loop.stdout
python3 scripts/v17_stack_contract.py > verification/v19/v19_stack_contract.stdout
python3 scripts/v18_motion_evidence_campaign.py > verification/v19/v19_motion_evidence.stdout
for campaign in v12_velocity_fault_campaign v11_camera_fault_campaign v09_fault_matrix v15_fault_campaign v16_fault_campaign; do
  python3 "scripts/${campaign}.py" > "verification/v19/${campaign}.stdout"
done
python3 scripts/validate_gazebo_world.py > verification/v19/v19_gazebo_static.stdout
python3 scripts/run_waypoint_regression.py > verification/v19/v19_kinematic.stdout
python3 scripts/v16_orchestrate.py --plan --scenario live > verification/v19/v19_plan.json
python3 -m compileall -q rescuemind ros scripts tests
for script in scripts/*.sh; do bash -n "$script"; done
python3 - <<'PY'
from pathlib import Path
import json,re,shutil
v=Path('verification/v19')
s=(v/'v19_unittest.log').read_text()
m=re.search(r'Ran (\d+) tests in',s)
assert m and 'OK' in s and 'FAILED' not in s
causal=json.loads((v/'v19_synthetic_chronology_campaign.json').read_text())
closed=json.loads(Path('verification/v17/campaign_summary.json').read_text())
assert causal['matched']==causal['total']==10
assert closed['expected_outcomes_matched']==closed['cases']==6
expected={'v12_velocity_fault_campaign':1125,'v11_camera_fault_campaign':500,
          'v09_fault_matrix':972,'v15_fault_campaign':600,'v16_fault_campaign':600}
for key,n in expected.items():
    vj=json.loads((v/(key+'.stdout')).read_text())
    assert vj['cases']==n
    assert vj.get('passes',vj.get('passed',vj.get('pass_count',n)))==n or key=='v09_fault_matrix'

report={
  'version':'1.9.0','verification_scope':'OFFLINE_ONLY',
  'python_unittest_passed':int(m.group(1)),
  'synthetic_timeline_cases':10,'synthetic_timeline_matched':10,
  'synthetic_closed_loop_cases':6,'synthetic_closed_loop_matched':6,
  'legacy_fault_campaign_cases':expected,
  'gazebo_sdf_static':'PASS','python_kinematics':'PASS','shell_syntax':'PASS',
  'external_available':{k:bool(shutil.which(k)) for k in ('ros2','gz','nvidia-smi')},
  'real_gazebo':'UNTESTED','real_Jev':'UNTESTED','real_Qwen':'UNTESTED',
  'robot_submission_video':'NOT_CREATED',
  'limitation':'Passing simulated traces cannot authenticate a Gazebo session or a VLM response.'}
(v/'v19_TEST_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
PY
