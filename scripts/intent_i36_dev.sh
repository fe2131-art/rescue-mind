#!/usr/bin/env bash
# I-08: i36 (i35 + Yes/No self-check) on the intent DEV set for every candidate model.
set -uo pipefail
cd "$(dirname "$0")/.."
for spec in "Qwen/Qwen2.5-VL-3B-Instruct:qwen25vl3b" "Qwen/Qwen3-VL-8B-Instruct:qwen3vl8b" "Qwen/Qwen3.5-9B:qwen35_9b" "Qwen/Qwen3.5-4B:qwen35_4b"; do
  model=${spec%%:*}; tag=${spec##*:}
  pkill -f local_vlm_server; while curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1; do sleep 1; done
  python3 scripts/local_vlm_server.py --model "$model" --prompt-set v35 --intent-prompt i36 --port 8765 > /tmp/vlm_i36.log 2>&1 &
  until curl -s http://127.0.0.1:8765/health | grep -q ready; do sleep 3; done
  python3 scripts/intent_eval.py --method hybrid --model "$model" --tag "i36_$tag" --split dev_v35 > /tmp/i36.txt 2>&1; head -1 /tmp/i36.txt
  echo "DONE $tag"
done
pkill -f local_vlm_server
