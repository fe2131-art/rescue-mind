#!/usr/bin/env bash
# Study JI (I-94; experiments/PREREGISTRATION_JI.md), full sequence: smoke test -> render 240 worlds x 6 views (+ fire masks, labels) -> frozen gate on all 1440 images -> the four judges -> analysis.
#   bash scripts/ji_run.sh        # first call: smoke test, then STOPS (exit 2): look at experiments/vlm_testset_ji/smoke/smoke_sheet.jpg, `touch experiments/results/ji_smoke_ok`, rerun
# Needs the host quiet and nothing else on Gazebo / the GPU (it waits for the campaign lock and refuses to start while gz sim / a campaign / a VLM server runs).  Resumable.  About 3 h render + 1.3 h gate + 4 x 1 h judges.
set -uo pipefail
cd "$(dirname "$0")/.."
RES=experiments/results
IN_NEXT=(docker exec rm-next rescuemind-entrypoint)
abort() { echo "JI_ABORT: $*" | tee -a $RES/ji_run.log >&2; exit 1; }
for _ in $(seq 1 2880); do pgrep -f '^bash scripts/gm_run\.sh$' >/dev/null || break; sleep 60; done          # study GM first (one GPU, one Gazebo, one lock)
exec 9>/tmp/rescuemind_campaign.lock
flock 9
for f in experiments/PREREGISTRATION_JI.md experiments/campaign_ji_protocol.json experiments/ji_thresholds.json scripts/make_protocol_ji.py scripts/build_testset_ji.py scripts/ji_analysis.py scripts/ji_run.sh; do
  git ls-files --error-unmatch "$f" >/dev/null 2>&1 || abort "$f is not committed"
  git diff --quiet HEAD -- "$f" || abort "$f differs from the committed version"
done
if pgrep -f "gz sim|run_campaign|v32_orchestrate|local_vlm_server" >/dev/null; then abort "another Gazebo/campaign/VLM process is running"; fi
for i in $(seq 1 60); do awk '{exit !($1 < 6)}' /proc/loadavg && break; sleep 60; done
render() { "${IN_NEXT[@]}" bash -c "cd $PWD && python3 scripts/build_testset_ji.py $*"; }
if [ ! -f $RES/ji_smoke_ok ]; then
  render --smoke >> $RES/ji_render.log 2>&1 || abort "smoke render failed (ji_render.log)"
  echo "JI_SMOKE_DONE: look at experiments/vlm_testset_ji/smoke/smoke_sheet.jpg; touch $RES/ji_smoke_ok if the fires look as in XD's hard class, then rerun"; exit 2
fi
retry() { local n=1; until "$@"; do [ $n -ge 3 ] && return 1; n=$((n+1)); echo "JI_RETRY $n"; sleep 20; done; }
retry render --images >> $RES/ji_render.log 2>&1 || abort "image render failed"
retry render --fire-masks >> $RES/ji_render.log 2>&1 || abort "mask render failed"
python3 scripts/build_testset_ji.py --labels >> $RES/ji_render.log 2>&1 || abort "labels"
echo "JI_RENDER_DONE"
"${IN_NEXT[@]}" pkill -f local_vlm_server.py >/dev/null 2>&1 || true
sleep 10
docker exec -d rm-next rescuemind-entrypoint bash -c "cd $PWD && HF_HUB_OFFLINE=1 python3 scripts/local_vlm_server.py --model Qwen/Qwen3.5-9B --prompt-set v35 --port 8765 --hazard-prompt h36 --hazard-views tiles > $PWD/$RES/ji_server.log 2>&1"
for _ in $(seq 1 300); do curl -s -m 5 http://127.0.0.1:8765/health 2>/dev/null | grep -q ready && break; sleep 3; done
curl -s -m 5 http://127.0.0.1:8765/health | grep -q ready || abort "gate server not ready (ji_server.log)"
[ -f "$RES/devset_ji_h36_tiles.json" ] || python3 scripts/vlm_devset_eval.py --model Qwen/Qwen3.5-9B --devset experiments/vlm_testset_ji --tag ji_h36_tiles > "$RES/ji_score_gate.log" 2>&1 || abort "JI_FAIL gate scoring (ji_score_gate.log)"
"${IN_NEXT[@]}" pkill -f local_vlm_server.py >/dev/null 2>&1 || true
for j in internvl3 idefics3 smolvlm2 qwen3vl; do
  "${IN_NEXT[@]}" bash -c "cd $PWD && HF_HUB_OFFLINE=1 python3 scripts/jev_score.py --judge $j --set ji" >> $RES/ji_judges.log 2>&1 || abort "JI_FAIL judge $j (ji_judges.log)"
done
python3 scripts/ji_analysis.py > $RES/ji_analysis_stdout.log || abort "analysis"
echo JI_DONE
