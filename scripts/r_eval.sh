#!/usr/bin/env bash
# Study R (pre-registered): v3.6 offline check on 12 camera degradations of the T2 subset.
set -uo pipefail
cd "$(dirname "$0")/.."
renice -n 5 -p $$ >/dev/null 2>&1 || true
pkill -f local_vlm_server; while curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1; do sleep 1; done
HF_HUB_OFFLINE=1 python3 scripts/local_vlm_server.py --model Qwen/Qwen3.5-9B --prompt-set v35 --port 8765 \
  --hazard-prompt h36 --hazard-views tiles > /tmp/vlm_r.log 2>&1 &
until curl -s http://127.0.0.1:8765/health | grep -q ready; do sleep 3; done
python3 scripts/r_corruption_eval.py --all
pkill -f local_vlm_server
echo R_DONE
