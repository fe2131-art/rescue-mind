#!/usr/bin/env bash
# Study XD (DRAFT): score the rendered set with the local VLM server (Qwen3.5-9B, v3.6 = h36 + tiles) and run the analysis.
#   bash scripts/xd_eval.sh                  # image set (needs xd_render.sh first)
#   XD_STAGES="ar" bash scripts/xd_eval.sh   # "a" = depot images, "r" = real fire-free photographs (needs the manifest, see xd_realphoto.py)
# Estimated GPU time: a 1.0 h (1284 images x 2 passes x 1.33 s + one model load), r 0.1 h (200 photographs, one pass).
# Resumable: a finished result file is skipped.  An inference error triggers ONE full re-run of the stage (both files are kept).
set -uo pipefail
cd "$(dirname "$0")/.."
renice -n 5 -p $$ >/dev/null 2>&1 || true
STAGES=${XD_STAGES:-a}
MODEL=Qwen/Qwen3.5-9B
RES=experiments/results
XD=experiments/vlm_testset_xd
LOG=${XD_LOG:-/tmp/vlm_xd.log}
export HF_HUB_OFFLINE=1
if command -v git >/dev/null 2>&1 && [ -z "${XD_DRAFT:-}" ]; then
  for f in experiments/campaign_xd_protocol.json experiments/PREREGISTRATION_XD.md scripts/xd_analysis.py scripts/xd_realphoto.py scripts/local_vlm_server.py; do
    git ls-files --error-unmatch "$f" >/dev/null 2>&1 || { echo "XD_ABORT: $f is not committed"; exit 1; }
    git diff --quiet HEAD -- "$f" || { echo "XD_ABORT: $f differs from the committed version"; exit 1; }
  done
fi
if [[ "$STAGES" == *a* ]]; then
  [ -f $XD/labels.jsonl ] && [ -d $XD/fire_masks ] || { echo "XD_ABORT: run scripts/xd_render.sh first"; exit 1; }
fi
if pgrep -f "run_campaign|v32_orchestrate|gz sim" >/dev/null && [ -z "${XD_FORCE:-}" ]; then
  echo "XD_ABORT: a campaign or Gazebo is running (set XD_FORCE=1 to override)"; exit 1; fi
until awk '{exit !($1 < 6)}' /proc/loadavg; do sleep 30; done
pkill -f local_vlm_server; while curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1; do sleep 1; done
python3 scripts/local_vlm_server.py --model $MODEL --prompt-set v35 --port 8765 --hazard-prompt h36 --hazard-views tiles > "$LOG" 2>&1 &
until curl -s http://127.0.0.1:8765/health | grep -q ready; do sleep 3; done
nerr() { python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
print(sum(1 for r in d['records'] if any('error' in p for p in (r.get('passes') or {}).values())))
" "$1"; }
if [[ "$STAGES" == *a* ]]; then
  f=$RES/devset_xd_h36_tiles.json
  if [ -f "$f" ]; then echo "skip xd_h36_tiles"; else
    python3 scripts/vlm_devset_eval.py --model $MODEL --devset $XD --tag xd_h36_tiles >/dev/null 2>&1
    if [ -f "$f" ] && [ "$(nerr "$f")" != "0" ]; then mv "$f" "${f%.json}.attempt1.json"; python3 scripts/vlm_devset_eval.py --model $MODEL --devset $XD --tag xd_h36_tiles >/dev/null 2>&1; fi
    echo "DONE xd_h36_tiles errors=$([ -f "$f" ] && nerr "$f" || echo missing)"
  fi
fi
if [[ "$STAGES" == *r* ]]; then
  python3 scripts/xd_realphoto.py --sample && python3 scripts/xd_realphoto.py --run || echo "XD_NOTE: real-photograph stage failed (see above)"
fi
pkill -f local_vlm_server
[[ "$STAGES" == *a* ]] && python3 scripts/xd_analysis.py > $RES/xd_analysis_stdout.log 2>&1
[[ "$STAGES" == *r* ]] && python3 scripts/xd_realphoto.py --analyse > $RES/xd_real_stdout.log 2>&1
echo XD_EVAL_DONE
