#!/usr/bin/env bash
# Study XD (DRAFT): score the rendered set with the local VLM server (Qwen3.5-9B, v3.6 = h36 + tiles) and run the analysis.
#   bash scripts/xd_eval.sh                  # image set (needs xd_render.sh first)
#   XD_STAGES="ar" bash scripts/xd_eval.sh   # "a" = depot images, "r" = real fire-free photographs (needs the manifest, see xd_realphoto.py)
# Estimated GPU time: a 1.6 h (1932 images x 2 passes x 1.33 s + one model load), r 0.1 h (200 photographs, one pass).
# Resumable: a finished result file is skipped.  An inference error triggers ONE full re-run of the stage (both files are kept).
# Run it on the HOST (bash scripts/xd_eval.sh): the VLM server is started in the container rm-next (the host python has no transformers),
# the clients and the analysis run on the host (stage r reads ~/.cache/rescuemind/warehouse_negatives, which the container cannot see).
# Prints XD_EVAL_DONE, or XD_ABORT on any failure (docs/PREFLIGHT_2026-10-18.md).
set -uo pipefail
cd "$(dirname "$0")/.."
renice -n 5 -p $$ >/dev/null 2>&1 || true
STAGES=${XD_STAGES:-a}
MODEL=Qwen/Qwen3.5-9B
RES=experiments/results
XD=experiments/vlm_testset_xd
LOG=${XD_LOG:-experiments/results/xd_server.log}
case "$LOG" in /*) ;; *) LOG=$PWD/$LOG;; esac
CT=${XD_CONTAINER:-rm-next}
export HF_HUB_OFFLINE=1
abort() { echo "XD_ABORT: $*" >&2; exit 1; }
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
# stage r needs the investigator's photographs (>= 200, with a manifest); without them it is skipped with a note, never a failure of stage a
RDIR=${XD_REAL_DIR:-$HOME/.cache/rescuemind/warehouse_negatives}
if [[ "$STAGES" == *r* ]] && [ ! -f "$RDIR/manifest.jsonl" ]; then
  echo "XD_NOTE: stage r skipped: $RDIR/manifest.jsonl is missing (collect >= 200 fire-free photographs first, see scripts/xd_realphoto.py)" >&2
  STAGES=${STAGES//r/}
  [ -n "$STAGES" ] || abort "nothing left to run"
fi
until awk '{exit !($1 < 6)}' /proc/loadavg; do sleep 30; done
# The server runs in the container rm-next.  On the host it is started with `docker exec -d`; inside the container directly.
# The wait for it is bounded: a server that cannot start must not hang the queue.
if [ -f /.dockerenv ]; then HOSTMODE=0; else HOSTMODE=1; fi
stop_server() {
  if [ $HOSTMODE -eq 1 ]; then docker exec "$CT" rescuemind-entrypoint pkill -f local_vlm_server.py >/dev/null 2>&1 || true
  else pkill -f local_vlm_server.py >/dev/null 2>&1 || true; fi
  for _ in $(seq 1 120); do curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1 || break; sleep 1; done
  sleep 5      # let the GPU memory be released
}
stop_server
args="--model $MODEL --prompt-set v35 --port 8765 --hazard-prompt h36 --hazard-views tiles"
if [ $HOSTMODE -eq 1 ]; then
  docker exec -d "$CT" rescuemind-entrypoint bash -c "cd $PWD && HF_HUB_OFFLINE=1 python3 scripts/local_vlm_server.py $args > $LOG 2>&1" \
    || abort "cannot start the server in the container $CT"
else
  python3 scripts/local_vlm_server.py $args > "$LOG" 2>&1 &
fi
ready=
for _ in $(seq 1 ${XD_READY_TRIES:-300}); do curl -s -m 5 http://127.0.0.1:8765/health 2>/dev/null | grep -q ready && { ready=1; break; }; sleep 3; done
[ -n "$ready" ] || { stop_server; abort "the VLM server did not become ready within 15 minutes (see $LOG)"; }
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
    [ -f "$f" ] || { stop_server; abort "xd_h36_tiles: no result file (vlm_devset_eval.py failed; see $LOG)"; }
  fi
fi
rok=
if [[ "$STAGES" == *r* ]]; then
  if python3 scripts/xd_realphoto.py --dir "$RDIR" --sample && python3 scripts/xd_realphoto.py --dir "$RDIR" --run; then rok=1
  else echo "XD_NOTE: real-photograph stage failed (see above); stage a is not affected" >&2; fi
fi
stop_server
if [[ "$STAGES" == *a* ]]; then python3 scripts/xd_analysis.py > $RES/xd_analysis_stdout.log 2>&1 || abort "xd_analysis.py failed (see $RES/xd_analysis_stdout.log)"; fi
[ -n "$rok" ] && { python3 scripts/xd_realphoto.py --analyse > $RES/xd_real_stdout.log 2>&1 || echo "XD_NOTE: xd_realphoto.py --analyse failed (see $RES/xd_real_stdout.log)" >&2; }
echo XD_EVAL_DONE
