#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p outputs/release
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
python -m compileall -q rescuemind ros tests
python -m unittest discover -s tests -v 2>&1 | tee outputs/release/unittest.log
python scripts/run_waypoint_regression.py | tee outputs/release/v06_waypoint.stdout
python -m rescuemind.demo --output outputs/release/grid_adaptive.json | tee outputs/release/grid_adaptive.stdout
python -m rescuemind.demo --mode fixed --output outputs/release/grid_fixed.json | tee outputs/release/grid_fixed.stdout
python -m rescuemind.evaluate --output-dir outputs/release | tee outputs/release/evaluate.stdout
python ros/nav2_mission.py --config configs/poses.example.json > outputs/release/nav2_dry_run.stdout
python - <<'PY'
from itertools import product
import json
from pathlib import Path
from rescuemind.safety import decide
n=0;approved=0
for js,qs,jc,qc,pr,co,hz in product(('water','medicine','other'),('water','medicine','other'),('clear','hazard','unknown'),('clear','hazard','unknown'),(.3,.95),(.4,.93),(.01,.9)):
    j={'real_model':True,'supply':js,'scene':jc,'supply_present_probability':pr,'supply_confidence':co,'hazard_probability':hz}
    q={'real_model':True,'supply':qs,'scene':qc}
    n+=1;approved+=decide('water',j,q).allow
out={'kind':'synthetic_fault_injection_contract_test_not_real_ai_performance','cases':n,'approved':approved,'rejected':n-approved}
Path('outputs/release/fault_matrix.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(out)
PY
printf '\n[OK] Python offline checks complete. Outputs in outputs/release/.\n'
python scripts/run_checkpoint_faultstudy.py | tee outputs/release/v07_checkpoint_faultstudy.stdout
