#!/usr/bin/env bash
# Study S: render the 240 images (156 worlds: 52 base worlds x none/attack/benign) and the fire masks.  Run INSIDE the rm-next container:
#   docker exec rm-next rescuemind-entrypoint bash scripts/s_render.sh
# Order (PREREGISTRATION_S.md): protocol + registration committed -> sign check (UV orientation, once) -> colour images -> fire masks -> labels.
# Resumable: finished worlds are skipped.  Sign textures need the Noto Sans CJK fonts of the container and are written to
# worlds/testset_s/signs/ (absolute paths in the SDF, so render and load in the same container).
# No other Gazebo stack or GPU job may run.
set -uo pipefail
cd "$(dirname "$0")/.."
renice -n 5 -p $$ >/dev/null 2>&1 || true
P=experiments/campaign_s_protocol.json
R=experiments/PREREGISTRATION_S.md
if command -v git >/dev/null 2>&1; then
  for f in $P $R; do
    git ls-files --error-unmatch "$f" >/dev/null 2>&1 || { echo "S_ABORT: $f is not committed"; exit 1; }
    git diff --quiet HEAD -- "$f" || { echo "S_ABORT: $f differs from the committed version"; exit 1; }
  done
else echo "WARN: git not available, registration commit not checked"; fi
if pgrep -f "gz sim|run_campaign|v32_orchestrate|local_vlm_server" >/dev/null && [ -z "${S_FORCE:-}" ]; then
  echo "S_ABORT: another Gazebo/campaign/VLM process is running (set S_FORCE=1 to override)"; exit 1; fi
until awk '{exit !($1 < 6)}' /proc/loadavg; do sleep 30; done
python3 scripts/make_protocol_s.py || exit 1             # refuses to overwrite a different registered protocol
if [ -z "${S_SKIP_SIGN_CHECK:-}" ] && [ ! -f experiments/vlm_testset_s/sign_check_ok ]; then
  python3 scripts/build_testset_s.py --sign-check || exit 1
  echo "S_SIGN_CHECK: open experiments/vlm_testset_s/images/signcheck_F.jpg.  Text readable, upright and not mirrored?"
  echo "  yes -> touch experiments/vlm_testset_s/sign_check_ok and run this script again"
  echo "  no  -> export RESCUEMIND_SIGN_TEXTURE_TRANSFORM=fliplr|flipud|rot180 and run this script again (record it in the pre-registration as an amendment)"
  exit 2
fi
python3 scripts/build_testset_s.py --images || { echo S_RENDER_FAILED_IMAGES; exit 1; }
python3 scripts/build_testset_s.py --fire-masks || { echo S_RENDER_FAILED_MASKS; exit 1; }
python3 scripts/build_testset_s.py --labels || exit 1
echo S_RENDER_DONE
