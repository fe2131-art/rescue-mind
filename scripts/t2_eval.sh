#!/usr/bin/env bash
# T2 (pre-registered): score every I-13 candidate configuration on the 600 held-out images.
set -uo pipefail
cd "$(dirname "$0")/.."
D=experiments/vlm_testset_t2
pkill -f local_vlm_server; pkill -f clef_server; sleep 3
HF_HUB_OFFLINE=1 python3 scripts/clef_server.py --port 8767 > /tmp/clef_t2.log 2>&1 &
until curl -s http://127.0.0.1:8767/health | grep -q ready; do sleep 3; done
[ -f experiments/results/devset_t2_clef.json ] || python3 scripts/clef_devset_eval.py --devset $D --tag t2_clef >/dev/null 2>&1
echo "DONE t2_clef"; pkill -f clef_server; sleep 5
serve() {  # model hazard_prompt hazard_views
  pkill -f local_vlm_server; while curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1; do sleep 1; done
  python3 scripts/local_vlm_server.py --model "$1" --prompt-set v35 --port 8765 --hazard-prompt "$2" --hazard-views "$3" > /tmp/vlm_t2.log 2>&1 &
  until curl -s http://127.0.0.1:8765/health | grep -q ready; do sleep 3; done
}
serve Qwen/Qwen3.5-4B h35 full
[ -f experiments/results/devset_t2_q4b.json ] || python3 scripts/vlm_devset_eval.py --model Qwen/Qwen3.5-4B --devset $D --tag t2_q4b >/dev/null 2>&1
echo "DONE t2_q4b"
for p in h35 h36; do for v in full tiles; do
  serve Qwen/Qwen3.5-9B $p $v
  [ -f experiments/results/devset_t2_i11_${p}_${v}.json ] || python3 scripts/vlm_devset_eval.py --model Qwen/Qwen3.5-9B --devset $D --tag t2_i11_${p}_${v} >/dev/null 2>&1
  echo "DONE t2_i11_${p}_${v}"
done; done
pkill -f local_vlm_server
python3 scripts/t2_analysis.py > experiments/results/t2_analysis_stdout.log 2>&1
echo T2_DONE
