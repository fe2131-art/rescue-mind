#!/usr/bin/env bash
# Study XD (DRAFT): render the depot image set (308 main worlds x 3 views + 228 hazard/twin worlds x 3 extra views + 108 ablation
# worlds x 3 views = 1932 images) and the fire masks.  Run INSIDE the rm-next container, nothing else on Gazebo / the GPU:
#   docker exec rm-next rescuemind-entrypoint bash scripts/xd_render.sh
# Order (PREREGISTRATION_XD.md): protocol + registration committed -> SMOKE TEST (one world per class and ablation variant, front view,
# colour + mask; a person looks at experiments/vlm_testset_xd/smoke/smoke_sheet.jpg and creates experiments/results/xd_smoke_ok
# only if every class renders as intended, in particular the mesh / sprite flames and the smoke-only worlds) -> colour images ->
# fire masks -> labels -> (then xd_eval.sh).  Resumable.  About 4.1 h; the GPU is used for Gazebo rendering only.
set -uo pipefail
cd "$(dirname "$0")/.."
renice -n 5 -p $$ >/dev/null 2>&1 || true
P=experiments/campaign_xd_protocol.json
R=experiments/PREREGISTRATION_XD.md
if command -v git >/dev/null 2>&1 && [ -z "${XD_DRAFT:-}" ]; then
  for f in $P $R scripts/make_protocol_xd.py scripts/build_testset_xd.py rescuemind/depot.py rescuemind/robust_scenes.py; do
    git ls-files --error-unmatch "$f" >/dev/null 2>&1 || { echo "XD_ABORT: $f is not committed"; exit 1; }
    git diff --quiet HEAD -- "$f" || { echo "XD_ABORT: $f differs from the committed version"; exit 1; }
  done
fi
if pgrep -f "gz sim|run_campaign|v32_orchestrate|local_vlm_server" >/dev/null && [ -z "${XD_FORCE:-}" ]; then
  echo "XD_ABORT: another Gazebo/campaign/VLM process is running (set XD_FORCE=1 to override)"; exit 1; fi
until awk '{exit !($1 < 6)}' /proc/loadavg; do sleep 30; done
python3 scripts/make_protocol_xd.py || exit 1             # refuses to overwrite a different registered protocol
python3 scripts/build_testset_xd.py --check || exit 1
if [ ! -f experiments/results/xd_smoke_ok ]; then
  python3 scripts/build_testset_xd.py --smoke || { echo XD_RENDER_FAILED_SMOKE; exit 1; }
  echo "XD_SMOKE_DONE: look at experiments/vlm_testset_xd/smoke/smoke_sheet.jpg; touch experiments/results/xd_smoke_ok if all classes look as intended, then rerun"
  exit 2
fi
# a single missed camera frame must not end the unattended queue: the renderer skips the worlds that are finished, so retry (3 tries)
retry() { local n=1; until "$@"; do [ $n -ge 3 ] && return 1; n=$((n+1)); echo "XD_RETRY $n: $*"; sleep 20; done; }
retry python3 scripts/build_testset_xd.py --images || { echo XD_RENDER_FAILED_IMAGES; exit 1; }
retry python3 scripts/build_testset_xd.py --fire-masks || { echo XD_RENDER_FAILED_MASKS; exit 1; }
python3 scripts/build_testset_xd.py --labels || exit 1
echo XD_RENDER_DONE
