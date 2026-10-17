#!/usr/bin/env bash
# Study W-a: render the 675 images (225 worlds x front/left/right) and the fire masks.  Run INSIDE the rm-next container:
#   docker exec rm-next rescuemind-entrypoint bash scripts/w_render.sh
# Order (PREREGISTRATION_W.md): protocol + registration committed -> colour images -> fire masks -> labels -> (then w_eval.sh).
# Resumable: finished worlds are skipped.  Needs ~2 h, GPU for Gazebo rendering only; no other Gazebo stack or GPU job may run.
set -uo pipefail
cd "$(dirname "$0")/.."
renice -n 5 -p $$ >/dev/null 2>&1 || true
P=experiments/campaign_w_protocol.json
R=experiments/PREREGISTRATION_W.md
# the registration must be committed and unchanged before anything is rendered
if command -v git >/dev/null 2>&1; then
  for f in $P $R; do
    git ls-files --error-unmatch "$f" >/dev/null 2>&1 || { echo "W_ABORT: $f is not committed"; exit 1; }
    git diff --quiet HEAD -- "$f" || { echo "W_ABORT: $f differs from the committed version"; exit 1; }
  done
else echo "WARN: git not available, registration commit not checked"; fi
# quiet host: nothing else may use Gazebo or the GPU while rendering
if pgrep -f "gz sim|run_campaign|v32_orchestrate|local_vlm_server" >/dev/null && [ -z "${W_FORCE:-}" ]; then
  echo "W_ABORT: another Gazebo/campaign/VLM process is running (set W_FORCE=1 to override)"; exit 1; fi
until awk '{exit !($1 < 6)}' /proc/loadavg; do sleep 30; done
python3 scripts/make_protocol_w.py || exit 1             # refuses to overwrite a different registered protocol
python3 scripts/build_testset_w.py --images || { echo W_RENDER_FAILED_IMAGES; exit 1; }
python3 scripts/build_testset_w.py --fire-masks || { echo W_RENDER_FAILED_MASKS; exit 1; }
python3 scripts/build_testset_w.py --labels || exit 1
echo W_RENDER_DONE
