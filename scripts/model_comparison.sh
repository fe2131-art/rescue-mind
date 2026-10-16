#!/usr/bin/env bash
# I-08: identical evaluation of candidate VLMs (run inside the jazzy-next image).
set -uo pipefail
cd "$(dirname "$0")/.."
for spec in "Qwen/Qwen3-VL-8B-Instruct:qwen3vl8b" "Qwen/Qwen3.5-9B:qwen35_9b" "Qwen/Qwen3.5-4B:qwen35_4b"; do
  model=${spec%%:*}; tag=${spec##*:}
  pkill -f local_vlm_server; sleep 3
  python3 scripts/local_vlm_server.py --model "$model" --prompt-set v34 --describe-prompt e0 --port 8765 > "/tmp/vlm_$tag.log" 2>&1 &
  until curl -s http://127.0.0.1:8765/health | grep -q ready; do sleep 3; done
  nvidia-smi --query-gpu=memory.used --format=csv,noheader > "experiments/results/vram_$tag.txt"
  python3 scripts/vlm_devset_eval.py --model "$model" --devset experiments/vlm_devset --tag "v1_$tag" >/dev/null 2>&1
  python3 scripts/vlm_devset_eval.py --model "$model" --devset experiments/vlm_devset_v2 --tag "v2_$tag" >/dev/null 2>&1
  python3 scripts/explanation_eval.py --model "$model" --tag "e0_$tag" | tail -1
  python3 scripts/intent_eval.py --method hybrid --model "$model" --tag "$tag" | head -1
  echo "DONE $tag $(cat experiments/results/vram_$tag.txt)"
done
pkill -f local_vlm_server
