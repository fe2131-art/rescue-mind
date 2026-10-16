#!/usr/bin/env bash
# I-08 round 2: all candidate models with the model-agnostic v35 vision prompts and the
# i34 / i35 intent prompts on the intent DEV set (the held-out set is not used for tuning).
set -uo pipefail
cd "$(dirname "$0")/.."
serve() {  # model prompt_set intent_prompt
  pkill -f local_vlm_server; sleep 3
  python3 scripts/local_vlm_server.py --model "$1" --prompt-set "$2" --intent-prompt "$3" --port 8765 > /tmp/vlm_cmp.log 2>&1 &
  until curl -s http://127.0.0.1:8765/health | grep -q ready; do sleep 3; done
}
for spec in "Qwen/Qwen2.5-VL-3B-Instruct:qwen25vl3b" "Qwen/Qwen3-VL-8B-Instruct:qwen3vl8b" "Qwen/Qwen3.5-9B:qwen35_9b" "Qwen/Qwen3.5-4B:qwen35_4b"; do
  model=${spec%%:*}; tag=${spec##*:}
  serve "$model" v35 i35
  python3 scripts/vlm_devset_eval.py --model "$model" --devset experiments/vlm_devset --tag "v1_v35_$tag" >/dev/null 2>&1
  python3 scripts/vlm_devset_eval.py --model "$model" --devset experiments/vlm_devset_v2 --tag "v2_v35_$tag" >/dev/null 2>&1
  python3 scripts/intent_eval.py --method hybrid --model "$model" --tag "i35_$tag" --split dev_v35 > /tmp/i35.txt 2>&1; head -1 /tmp/i35.txt
  serve "$model" v35 i34
  python3 scripts/intent_eval.py --method hybrid --model "$model" --tag "i34_$tag" --split dev_v35 > /tmp/i34.txt 2>&1; head -1 /tmp/i34.txt
  echo "DONE $tag"
done
pkill -f local_vlm_server
