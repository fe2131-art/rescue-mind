#!/usr/bin/env bash
# CPU-offline-only verification: NO V100 model loaded, NO Gazebo run, NO API.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT";export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p verification/v32
python3 -m unittest discover -s tests -q > verification/v32/python_tests.log 2>&1
python3 -m compileall -q rescuemind ros scripts tests
for script in scripts/*.sh; do bash -n "$script";done
for scene in nominal swapped empty;do
  timeout 40s python3 scripts/v32_orchestrate.py --plan --scenario live --scene "$scene" --local-mode single --capture-rosbag > "verification/v32/plan_${scene}.json"
done
timeout 40s python3 scripts/v32_orchestrate.py --plan --scenario live --scene nominal --local-mode dual > verification/v32/plan_dual.json
timeout 40s python3 scripts/v32_orchestrate.py --plan --scenario motion-check --scene nominal --capture-rosbag > verification/v32/plan_motion.json
timeout 40s python3 scripts/v32_print_trial_commands.py > verification/v32/planned_30_trials.txt
python3 scripts/local_gpu_preflight.py --mode single > verification/v32/gpu_preflight_THIS_CONTAINER.json || true
python3 - <<'PY'
from pathlib import Path
import json,re,shutil
R=Path.cwd();v=R/'verification/v32'
log=(v/'python_tests.log').read_text()
match=re.search(r'Ran (\d+) tests in',log)
assert match and int(match.group(1))>=506 and re.search(r'^OK\s*$',log,re.M)
for scene in ('nominal','swapped','empty'):
 p=json.loads((v/f'plan_{scene}.json').read_text())
 assert p['cloud_api_used'] is False and p['local_mode']=='single'
 assert any('local_vlm_server.py' in ' '.join(s) for s in p['services'])
 assert '--inference-backend local' in p['mission'][-1]
 assert 'jev-1.14.0' not in p['mission'][-1]
 assert any('ros2 bag record' in ' '.join(c) for c in p['services'])
d=json.loads((v/'plan_dual.json').read_text());assert any('SmolVLM2-2.2B' in str(s) for s in d['services'])
m=json.loads((v/'plan_motion.json').read_text());assert not any('local_vlm_server' in str(s) for s in m['services'])
assert (v/'planned_30_trials.txt').read_text().count('trial_id=')==30
from rescuemind.scene_variants import audit_scenarios
assert audit_scenarios(R/'worlds/scenarios')['pass']
pre=json.loads((v/'gpu_preflight_THIS_CONTAINER.json').read_text())
report={'release':'3.2.0-local-first','scope':'CPU_UNIT_TESTS_WITH_MOCK_ROS_AND_HTTP_PLUS_STATIC_SDF_NOT_REAL_GPU',
 'python_tests':int(match.group(1)),'all_tests_passed':True,
 'local_plans_verified':5,'trial_commands_planned':30,'trials_executed':0,
 'cuda_visible_in_packaging_environment':shutil.which('nvidia-smi') is not None,
 'local_gpu_preflight_ready_in_packaging_environment':pre['ready'],
 'real_V100_local_model_inference':'NOT_TESTED',
 'real_Gazebo_movement':'NOT_TESTED','real_ROSbag_capture':'NOT_TESTED',
 'real_scene_vision_accuracy':'NOT_MEASURED','submission_video':'NOT_CREATED',
 'cloud_api_used_in_v32_local_lane':False,
 'old_cloud_lane_kept':'scripts/v31_orchestrate.py',
 'physical_pickup':'NOT_IMPLEMENTED',
 'notice':'Two prompts from a single Qwen2.5-VL-3B are not two independent models.'}
(v/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
PY
