#!/usr/bin/env bash
# DH2 development runs (all I-13 candidates), then the selection.
cd "$(dirname "$0")/.."
D=experiments/vlm_devset_hazard2
pkill -f local_vlm_server; pkill -f clef_server; sleep 3
HF_HUB_OFFLINE=1 python3 scripts/clef_server.py --port 8767 > /tmp/clef_dh2.log 2>&1 &
until curl -s http://127.0.0.1:8767/health | grep -q ready; do sleep 3; done
[ -f experiments/results/devset_dh2_clef.json ] || python3 scripts/clef_devset_eval.py --devset $D --tag dh2_clef >/dev/null 2>&1
pkill -f clef_server; sleep 5
serve() { pkill -f local_vlm_server; while curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1; do sleep 1; done
  python3 scripts/local_vlm_server.py --model "$1" --prompt-set v35 --port 8765 --hazard-prompt "$2" --hazard-views "$3" > /tmp/vlm_dh2.log 2>&1 &
  until curl -s http://127.0.0.1:8765/health | grep -q ready; do sleep 3; done; }
serve Qwen/Qwen3.5-4B h35 full
[ -f experiments/results/devset_dh2_q4b.json ] || python3 scripts/vlm_devset_eval.py --model Qwen/Qwen3.5-4B --devset $D --tag dh2_q4b >/dev/null 2>&1
for p in h35 h36; do for v in full tiles; do
  serve Qwen/Qwen3.5-9B $p $v
  [ -f experiments/results/devset_dh2_i11_${p}_${v}.json ] || python3 scripts/vlm_devset_eval.py --model Qwen/Qwen3.5-9B --devset $D --tag dh2_i11_${p}_${v} >/dev/null 2>&1
  echo "DONE dh2 $p $v"
done; done
pkill -f local_vlm_server
python3 scripts/i13_select.py > experiments/results/i13_select_stdout.log 2>&1
echo CHAIN5_DONE
