#!/usr/bin/env bash
# Study S: score the 276 images with the local VLM server (Qwen3.5-9B) under four server configurations and run the analysis.
#   bash scripts/s_eval.sh                  # all stages
#   S_STAGES="a" bash scripts/s_eval.sh     # a = v3.6 (h36 + tiles: OURS and ONE-PASS; also OCR-MASK on the masked copies of the images),
#                                           # b = OURS-FULL (h36, full image), c = FREE-FORM (--method json),
#                                           # d = IGNORE-TEXT (prompt set v35ign + hazard prompt h36ign + tiles, original images)
# Needs scripts/s_render.sh first (labels.jsonl).  Run it on the HOST (bash scripts/s_eval.sh): the VLM server is started in the container
# rm-next (the host python has no transformers; IF and Q do the same), the clients and the analysis run on the host.  Inside rm-next it also
# works, provided the OCR boxes exist (S_STAGES=m on the host first: the OCR venv is not visible in the container).
# The OCR-MASK images are made first by scripts/s_ocr_mask.py (CPU only, venv ~/.cache/rescuemind/venv-ocr, no GPU, no server).
# Prints S_EVAL_DONE, or S_ABORT on any failure (docs/PREFLIGHT_2026-10-18.md).
# Resumable: finished result files are skipped.  An inference error in a stage triggers ONE full re-run of that stage (both files kept).
# Estimated: OCR masking 0.12 h (CPU); GPU time (one V100): a 0.20 h (+ 0.06 h legibility check) + 0.20 h (OCR-MASK, same server),
# b 0.11 h, c 0.23 h, d 0.22 h, plus four model loads (about 0.13 h): about 1.15 h GPU, about 1.3 h with the masking.
set -uo pipefail
cd "$(dirname "$0")/.."
renice -n 5 -p $$ >/dev/null 2>&1 || true
STAGES=${S_STAGES:-abcd}
MODEL=Qwen/Qwen3.5-9B
RES=experiments/results
S=experiments/vlm_testset_s
SM=experiments/vlm_testset_s_ocrmask
OCRPY=${S_OCR_PYTHON:-$HOME/.cache/rescuemind/venv-ocr/bin/python}
LOG=${S_LOG:-experiments/results/s_server.log}
case "$LOG" in /*) ;; *) LOG=$PWD/$LOG;; esac
CT=${S_CONTAINER:-rm-next}
export HF_HUB_OFFLINE=1
abort() { echo "S_ABORT: $*" >&2; exit 1; }
if command -v git >/dev/null 2>&1; then
  for f in experiments/campaign_s_protocol.json experiments/PREREGISTRATION_S.md scripts/s_analysis.py scripts/s_readcheck.py scripts/s_ocr_mask.py scripts/local_vlm_server.py; do
    git ls-files --error-unmatch "$f" >/dev/null 2>&1 || { echo "S_ABORT: $f is not committed"; exit 1; }
    git diff --quiet HEAD -- "$f" || { echo "S_ABORT: $f differs from the committed version"; exit 1; }
  done
fi
[ -f $S/labels.jsonl ] || { echo "S_ABORT: run scripts/s_render.sh first"; exit 1; }
if pgrep -f "run_campaign|v32_orchestrate|gz sim" >/dev/null && [ -z "${S_FORCE:-}" ]; then
  echo "S_ABORT: a campaign or Gazebo is running (set S_FORCE=1 to override)"; exit 1; fi
until awk '{exit !($1 < 6)}' /proc/loadavg; do sleep 30; done

# The server runs in the container rm-next (its python has transformers, the host python has not).  On the host it is started with
# `docker exec -d`; inside the container directly.  The wait for it is bounded: a server that cannot start must not hang the queue.
if [ -f /.dockerenv ]; then HOSTMODE=0; else HOSTMODE=1; fi
stop_server() {
  if [ $HOSTMODE -eq 1 ]; then docker exec "$CT" rescuemind-entrypoint pkill -f local_vlm_server.py >/dev/null 2>&1 || true
  else pkill -f local_vlm_server.py >/dev/null 2>&1 || true; fi
  for _ in $(seq 1 120); do curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1 || break; sleep 1; done
  sleep 5      # let the GPU memory be released
}
serve() {  # extra server arguments...
  stop_server
  local args="--model $MODEL --prompt-set v35 --port 8765 $*"
  if [ $HOSTMODE -eq 1 ]; then
    docker exec -d "$CT" rescuemind-entrypoint bash -c "cd $PWD && HF_HUB_OFFLINE=1 python3 scripts/local_vlm_server.py $args > $LOG 2>&1" \
      || abort "cannot start the server in the container $CT"
  else
    python3 scripts/local_vlm_server.py $args > "$LOG" 2>&1 &
  fi
  for _ in $(seq 1 ${S_READY_TRIES:-300}); do curl -s -m 5 http://127.0.0.1:8765/health 2>/dev/null | grep -q ready && return 0; sleep 3; done
  stop_server; abort "the VLM server did not become ready within 15 minutes (see $LOG)"
}
nerr() {  # result file -> number of records with an inference error
  python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
print(sum(1 for r in d['records'] if any('error' in p for p in (r.get('passes') or {}).values())))
" "$1"
}
guard() {  # tag [devset dir]  run once, re-run once in full if errors remain
  local tag=$1
  local dev=${2:-$S}
  local f=$RES/devset_$tag.json
  [ -f "$f" ] && { echo "skip $tag"; return; }
  python3 scripts/vlm_devset_eval.py --model $MODEL --devset "$dev" --tag "$tag" >/dev/null 2>&1
  if [ -f "$f" ] && [ "$(nerr "$f")" != "0" ]; then
    mv "$f" "${f%.json}.attempt1.json"
    python3 scripts/vlm_devset_eval.py --model $MODEL --devset "$dev" --tag "$tag" >/dev/null 2>&1
  fi
  echo "DONE $tag errors=$([ -f "$f" ] && nerr "$f" || echo missing)"
  [ -f "$f" ] || { stop_server; abort "$tag: no result file (vlm_devset_eval.py failed; see $LOG)"; }
}

# OCR-MASK images (CPU, no server): detect text regions with the offline detector and blank them; a missing venv is a hard stop
if [[ "$STAGES" == *a* || "$STAGES" == *m* ]] && [ ! -f $SM/ocr_boxes.json ]; then
  [ -x "$OCRPY" ] || abort "OCR venv missing ($OCRPY; it exists on the host only, so inside rm-next run S_STAGES=m on the host first): python3 -m venv ~/.cache/rescuemind/venv-ocr && ~/.cache/rescuemind/venv-ocr/bin/pip install rapidocr-onnxruntime pillow numpy opencv-python-headless"
  "$OCRPY" scripts/s_ocr_mask.py --src $S --dst $SM > $RES/s_ocr_mask.log 2>&1 || abort "s_ocr_mask.py failed (see $RES/s_ocr_mask.log)"
fi
[ "$STAGES" = m ] && { echo S_OCR_DONE; exit 0; }
if [[ "$STAGES" == *a* ]]; then serve --hazard-prompt h36 --hazard-views tiles; guard s_h36_tiles
  guard s_ocrmask_h36_tiles $SM                                                                  # OCR-MASK: the same server on the masked copies
  [ -f $RES/s_readcheck.json ] || python3 scripts/s_readcheck.py --model $MODEL > /dev/null 2>&1   # manipulation check: can the model read the signs?
  [ -f $RES/s_readcheck.json ] || echo "S_NOTE: s_readcheck.json is missing (the legibility check S0 failed to run; rerun scripts/s_readcheck.py with the server up)" >&2
fi
if [[ "$STAGES" == *b* ]]; then serve --hazard-prompt h36 --hazard-views full; guard s_h36_full; fi
if [[ "$STAGES" == *c* ]]; then serve --method json; guard s_json; fi
if [[ "$STAGES" == *d* ]]; then serve --prompt-set v35ign --hazard-prompt h36ign --hazard-views tiles; guard s_ign_h36_tiles; fi   # IGNORE-TEXT
stop_server
missing=()
[[ "$STAGES" == *a* ]] && for t in s_h36_tiles s_ocrmask_h36_tiles; do [ -f $RES/devset_$t.json ] || missing+=($t); done
[[ "$STAGES" == *b* && ! -f $RES/devset_s_h36_full.json ]] && missing+=(s_h36_full)
[[ "$STAGES" == *c* && ! -f $RES/devset_s_json.json ]] && missing+=(s_json)
[[ "$STAGES" == *d* && ! -f $RES/devset_s_ign_h36_tiles.json ]] && missing+=(s_ign_h36_tiles)
[ ${#missing[@]} -eq 0 ] || abort "result files missing: ${missing[*]}"
python3 scripts/s_analysis.py > $RES/s_analysis_stdout.log 2>&1 || abort "s_analysis.py failed (see $RES/s_analysis_stdout.log)"
echo S_EVAL_DONE
