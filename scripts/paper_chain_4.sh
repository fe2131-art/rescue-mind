#!/usr/bin/env bash
# I-11/I-13 development runs (after T1 chain and DH render): Clef-Flash, Qwen3.5-4B on DH, Qwen3.5-9B hazard variants.
cd "$(dirname "$0")/.."
pkill -f local_vlm_server; pkill -f clef_server; sleep 3
HF_HUB_OFFLINE=1 python3 scripts/clef_server.py --port 8767 > /tmp/clef_dev.log 2>&1 &
until curl -s http://127.0.0.1:8767/health | grep -q ready; do sleep 3; done
for s in "v1:experiments/vlm_devset" "v2:experiments/vlm_devset_v2" "dh:experiments/vlm_devset_hazard"; do
  [ -f "experiments/results/devset_${s%%:*}_clef.json" ] || python3 scripts/clef_devset_eval.py --devset "${s#*:}" --tag "${s%%:*}_clef" > /dev/null 2>&1
  echo "DONE clef ${s%%:*}"
done
pkill -f clef_server; sleep 5
python3 scripts/local_vlm_server.py --model Qwen/Qwen3.5-4B --prompt-set v35 --port 8765 > /tmp/q4b_dev.log 2>&1 &
until curl -s http://127.0.0.1:8765/health | grep -q ready; do sleep 3; done
[ -f experiments/results/devset_dh_q4b.json ] || python3 scripts/vlm_devset_eval.py --model Qwen/Qwen3.5-4B --devset experiments/vlm_devset_hazard --tag dh_q4b >/dev/null 2>&1
echo "DONE q4b dh"
pkill -f local_vlm_server; sleep 3
bash scripts/i11_eval.sh
python3 scripts/i13_select.py > experiments/results/i13_select_stdout.log 2>&1
echo CHAIN4_DONE
