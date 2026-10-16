#!/usr/bin/env bash
# Paper test set T1: score every pre-registered model / method on the 600 held-out images.
# Writes experiments/results/devset_t1_<tag>.json; analyse with scripts/t1_analysis.py.
set -uo pipefail
cd "$(dirname "$0")/.."
LOG=${T1_LOG:-/tmp/vlm_t1.log}
serve() {  # model method
  pkill -f local_vlm_server; while curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1; do sleep 1; done
  python3 scripts/local_vlm_server.py --model "$1" --method "$2" --prompt-set v35 --port 8765 > "$LOG" 2>&1 &
  until curl -s http://127.0.0.1:8765/health | grep -q ready; do sleep 3; done
}
run() {  # model method tag
  [ -f "experiments/results/devset_$3.json" ] && { echo "skip $3"; return; }
  [ -n "${T1_ONLY:-}" ] && [ "$T1_ONLY" != "$3" ] && return
  serve "$1" "$2"
  python3 scripts/vlm_devset_eval.py --model "$1" --devset experiments/vlm_testset_t1 --tag "$3" >/dev/null 2>&1
  echo "DONE $3"
}
run Qwen/Qwen3.5-9B scored t1_qwen35_9b
run Qwen/Qwen3.5-4B scored t1_qwen35_4b
run Qwen/Qwen3-VL-8B-Instruct scored t1_qwen3vl8b
run Qwen/Qwen2.5-VL-3B-Instruct scored t1_qwen25vl3b
run Qwen/Qwen3.5-9B json t1_json_qwen35_9b
run Qwen/Qwen2.5-VL-3B-Instruct json t1_json_qwen25vl3b
pkill -f local_vlm_server
