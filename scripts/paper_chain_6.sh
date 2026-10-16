#!/usr/bin/env bash
# I-13 fairness check: Clef-Flash with task-worded questions on all development sets, then the selection.
cd "$(dirname "$0")/.."
pkill -f local_vlm_server; pkill -f clef_server; sleep 3
HF_HUB_OFFLINE=1 python3 scripts/clef_server.py --port 8767 > /tmp/clef_task.log 2>&1 &
until curl -s http://127.0.0.1:8767/health | grep -q ready; do sleep 3; done
for s in "v1:experiments/vlm_devset" "v2:experiments/vlm_devset_v2" "dh:experiments/vlm_devset_hazard" "dh2:experiments/vlm_devset_hazard2"; do
  [ -f "experiments/results/devset_${s%%:*}_clef2.json" ] || python3 scripts/clef_devset_eval.py --schema task --devset "${s#*:}" --tag "${s%%:*}_clef2" >/dev/null 2>&1
  echo "DONE clef2 ${s%%:*}"
done
pkill -f clef_server
python3 scripts/i13_select.py > experiments/results/i13_select_stdout.log 2>&1
echo CHAIN6_DONE
