#!/usr/bin/env bash
# Study W: score everything with the local VLM server (Qwen3.5-9B, v3.6 = h36 + tiles) and run the analysis.
#   bash scripts/w_eval.sh                  # W-a (needs w_render.sh first) + W-b
#   W_STAGES="a" bash scripts/w_eval.sh     # only W-a;  "b" only W-b;  add "r" for the optional degradation stage
# Run where the VLM server can start (host python, as scripts/t2_eval.sh, or inside rm-next).  Resumable: finished result
# files are skipped.  An inference error in a stage triggers ONE full re-run of that stage (both files are kept).
# Estimated GPU time: W-a 0.8 h, W-b 2.15 h (T1 with h36+tiles 0.45 h, paraphrases on 1 800 images 1.45 h, T1 with h36 full 0.25 h), optional r 1.6 h.
set -uo pipefail
cd "$(dirname "$0")/.."
renice -n 5 -p $$ >/dev/null 2>&1 || true
STAGES=${W_STAGES:-ab}
MODEL=Qwen/Qwen3.5-9B
RES=experiments/results
W=experiments/vlm_testset_w
LOG=${W_LOG:-/tmp/vlm_w.log}
export HF_HUB_OFFLINE=1
if command -v git >/dev/null 2>&1; then
  for f in experiments/campaign_w_protocol.json experiments/PREREGISTRATION_W.md scripts/w_analysis.py scripts/w_paraphrase_eval.py scripts/local_vlm_server.py; do
    git ls-files --error-unmatch "$f" >/dev/null 2>&1 || { echo "W_ABORT: $f is not committed"; exit 1; }
    git diff --quiet HEAD -- "$f" || { echo "W_ABORT: $f differs from the committed version"; exit 1; }
  done
fi
if [[ "$STAGES" == *a* || "$STAGES" == *r* ]]; then
  [ -f $W/labels.jsonl ] && [ -d $W/fire_masks ] || { echo "W_ABORT: run scripts/w_render.sh first"; exit 1; }
fi
if pgrep -f "run_campaign|v32_orchestrate|gz sim" >/dev/null && [ -z "${W_FORCE:-}" ]; then
  echo "W_ABORT: a campaign or Gazebo is running (set W_FORCE=1 to override)"; exit 1; fi
until awk '{exit !($1 < 6)}' /proc/loadavg; do sleep 30; done

serve() {  # hazard_prompt hazard_views
  pkill -f local_vlm_server; while curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1; do sleep 1; done
  python3 scripts/local_vlm_server.py --model $MODEL --prompt-set v35 --port 8765 --hazard-prompt "$1" --hazard-views "$2" > "$LOG" 2>&1 &
  until curl -s http://127.0.0.1:8765/health | grep -q ready; do sleep 3; done
}
nerr() {  # result file -> number of records with an error (devset or paraphrase format)
  python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
print(sum(1 for r in d['records'] if any('error' in p for p in (r.get('passes') or {}).values()) or 'error' in (r.get('para') or {})))
" "$1"
}
guard() {  # tag command...   run once, re-run once in full if errors remain
  local tag=$1; shift
  local f=$RES/devset_$tag.json
  [ -f "$f" ] && { echo "skip $tag"; return; }
  "$@" >/dev/null 2>&1
  if [ -f "$f" ] && [ "$(nerr "$f")" != "0" ]; then mv "$f" "${f%.json}.attempt1.json"; "$@" >/dev/null 2>&1; fi
  echo "DONE $tag errors=$([ -f "$f" ] && nerr "$f" || echo missing)"
}
ev() { python3 scripts/vlm_devset_eval.py --model $MODEL --devset "$1" --tag "$2"; }
para() { python3 scripts/w_paraphrase_eval.py --devset "$1" --tag "$2" --model $MODEL; }

serve h36 tiles
if [[ "$STAGES" == *a* ]]; then guard w_h36_tiles ev $W w_h36_tiles; fi
if [[ "$STAGES" == *b* ]]; then
  guard t1_i11_h36_tiles ev experiments/vlm_testset_t1 t1_i11_h36_tiles
  for s in dh:experiments/vlm_devset_hazard dh2:experiments/vlm_devset_hazard2 t1:experiments/vlm_testset_t1 t2:experiments/vlm_testset_t2; do
    guard w_para_${s%%:*} para "${s#*:}" "${s%%:*}"
  done
  serve h36 full      # matched arm Ours-full: same wording, full image only (DH, DH2, T2 are already stored)
  guard t1_i11_h36_full ev experiments/vlm_testset_t1 t1_i11_h36_full
fi
if [[ "$STAGES" == *r* ]]; then
  [ -f $RES/devset_w_r_jpeg_S.json ] || python3 scripts/w_degraded_eval.py --all --model $MODEL
fi
if [[ "$STAGES" == *a* ]]; then
  serve h35 full
  guard w_h35_full ev $W w_h35_full
fi
pkill -f local_vlm_server
python3 scripts/w_analysis.py > $RES/w_analysis_stdout.log 2>&1
echo W_EVAL_DONE
