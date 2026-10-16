#!/usr/bin/env bash
# I-11: score the hazard-question variants (Qwen3.5-9B, v35 supply prompts) on development data only.
set -uo pipefail
cd "$(dirname "$0")/.."
serve() {  # hazard_prompt hazard_views
  pkill -f local_vlm_server; while curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1; do sleep 1; done
  python3 scripts/local_vlm_server.py --model Qwen/Qwen3.5-9B --prompt-set v35 --port 8765 \
    --hazard-prompt "$1" --hazard-views "$2" > /tmp/vlm_i11.log 2>&1 &
  until curl -s http://127.0.0.1:8765/health | grep -q ready; do sleep 3; done
}
for p in h35 h36; do for v in full tiles; do
  serve $p $v
  for ds in "dh:experiments/vlm_devset_hazard" "v1:experiments/vlm_devset" "v2:experiments/vlm_devset_v2"; do
    tag="${ds%%:*}_i11_${p}_${v}"
    [ -f "experiments/results/devset_$tag.json" ] || \
      python3 scripts/vlm_devset_eval.py --model Qwen/Qwen3.5-9B --devset "${ds#*:}" --tag "$tag" >/dev/null 2>&1
    echo "DONE $tag"
  done
done; done
pkill -f local_vlm_server
python3 scripts/i11_select.py
