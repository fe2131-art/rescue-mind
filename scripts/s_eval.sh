#!/usr/bin/env bash
# Study S: score the 240 images with the local VLM server (Qwen3.5-9B) under three server configurations and run the analysis.
#   bash scripts/s_eval.sh                  # all three
#   S_STAGES="a" bash scripts/s_eval.sh     # a = v3.6 (h36 + tiles: OURS and ONE-PASS), b = Ours-full (h36, full image), c = FREE-FORM (--method json)
# Needs scripts/s_render.sh first (labels.jsonl).  Run where the VLM server can start (host python, or inside rm-next).
# Resumable: finished result files are skipped.  An inference error in a stage triggers ONE full re-run of that stage (both files kept).
# Estimated GPU time (one V100): a 0.18 h (+ 0.05 h legibility check), b 0.10 h, c 0.20 h, plus three model loads (about 0.1 h): about 0.65 h.
set -uo pipefail
cd "$(dirname "$0")/.."
renice -n 5 -p $$ >/dev/null 2>&1 || true
STAGES=${S_STAGES:-abc}
MODEL=Qwen/Qwen3.5-9B
RES=experiments/results
S=experiments/vlm_testset_s
LOG=${S_LOG:-/tmp/vlm_s.log}
export HF_HUB_OFFLINE=1
if command -v git >/dev/null 2>&1; then
  for f in experiments/campaign_s_protocol.json experiments/PREREGISTRATION_S.md scripts/s_analysis.py scripts/s_readcheck.py scripts/local_vlm_server.py; do
    git ls-files --error-unmatch "$f" >/dev/null 2>&1 || { echo "S_ABORT: $f is not committed"; exit 1; }
    git diff --quiet HEAD -- "$f" || { echo "S_ABORT: $f differs from the committed version"; exit 1; }
  done
fi
[ -f $S/labels.jsonl ] || { echo "S_ABORT: run scripts/s_render.sh first"; exit 1; }
if pgrep -f "run_campaign|v32_orchestrate|gz sim" >/dev/null && [ -z "${S_FORCE:-}" ]; then
  echo "S_ABORT: a campaign or Gazebo is running (set S_FORCE=1 to override)"; exit 1; fi
until awk '{exit !($1 < 6)}' /proc/loadavg; do sleep 30; done

serve() {  # extra server arguments...
  pkill -f local_vlm_server; while curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1; do sleep 1; done
  python3 scripts/local_vlm_server.py --model $MODEL --prompt-set v35 --port 8765 "$@" > "$LOG" 2>&1 &
  until curl -s http://127.0.0.1:8765/health | grep -q ready; do sleep 3; done
}
nerr() {  # result file -> number of records with an inference error
  python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
print(sum(1 for r in d['records'] if any('error' in p for p in (r.get('passes') or {}).values())))
" "$1"
}
guard() {  # tag   run once, re-run once in full if errors remain
  local tag=$1
  local f=$RES/devset_$tag.json
  [ -f "$f" ] && { echo "skip $tag"; return; }
  python3 scripts/vlm_devset_eval.py --model $MODEL --devset $S --tag "$tag" >/dev/null 2>&1
  if [ -f "$f" ] && [ "$(nerr "$f")" != "0" ]; then
    mv "$f" "${f%.json}.attempt1.json"
    python3 scripts/vlm_devset_eval.py --model $MODEL --devset $S --tag "$tag" >/dev/null 2>&1
  fi
  echo "DONE $tag errors=$([ -f "$f" ] && nerr "$f" || echo missing)"
}

if [[ "$STAGES" == *a* ]]; then serve --hazard-prompt h36 --hazard-views tiles; guard s_h36_tiles
  [ -f $RES/s_readcheck.json ] || python3 scripts/s_readcheck.py --model $MODEL > /dev/null 2>&1   # manipulation check: can the model read the signs?
fi
if [[ "$STAGES" == *b* ]]; then serve --hazard-prompt h36 --hazard-views full; guard s_h36_full; fi
if [[ "$STAGES" == *c* ]]; then serve --method json; guard s_json; fi
pkill -f local_vlm_server
python3 scripts/s_analysis.py > $RES/s_analysis_stdout.log 2>&1
echo S_EVAL_DONE
