#!/usr/bin/env bash
# Study QJ (I-90; experiments/PREREGISTRATION_QJ.md): generate N0, NF, NB (text-to-image), score with the frozen gate (v3.6 h36 + tiles), analysis.  Resumable.  Run via Bash run_in_background.
set -uo pipefail
cd "$(dirname "$0")/.."
RES=experiments/results
IN_NEXT=(docker exec rm-next rescuemind-entrypoint)
abort() { echo "QJ_ABORT: $*" | tee -a $RES/qj_run.log >&2; exit 1; }
for _ in $(seq 1 1440); do pgrep -f '^bash scripts/(qi_run|qi_run2)\.sh$' >/dev/null || break; sleep 60; done
exec 9>/tmp/rescuemind_campaign.lock
flock 9
git ls-files --error-unmatch experiments/PREREGISTRATION_QJ.md >/dev/null 2>&1 || abort "PREREGISTRATION_QJ.md is not committed"
for m in N0 NF NB; do
  "${IN_NEXT[@]}" bash -c "cd $PWD && HF_HUB_OFFLINE=1 PYTHONPATH=/hf/qi_pylib python3 scripts/qj_generate.py --fast --mode $m --dtype float16" >> $RES/qj_generate.log 2>&1 || abort "generation $m failed (rerun resumes)"
done
python3 scripts/qj_build_devset.py || abort "devset build"
echo "QJ_GENERATED"
"${IN_NEXT[@]}" pkill -f local_vlm_server.py >/dev/null 2>&1 || true
sleep 10
docker exec -d rm-next rescuemind-entrypoint bash -c "cd $PWD && HF_HUB_OFFLINE=1 python3 scripts/local_vlm_server.py --model Qwen/Qwen3.5-9B --prompt-set v35 --port 8765 --hazard-prompt h36 --hazard-views tiles > $PWD/$RES/qj_server.log 2>&1"
for _ in $(seq 1 300); do curl -s -m 5 http://127.0.0.1:8765/health 2>/dev/null | grep -q ready && break; sleep 3; done
curl -s -m 5 http://127.0.0.1:8765/health | grep -q ready || abort "gate server not ready (qj_server.log)"
for m in N0 NF NB; do
  [ -f "$RES/devset_qj_${m}_h36_tiles.json" ] && continue
  python3 scripts/vlm_devset_eval.py --model Qwen/Qwen3.5-9B --devset outputs/qj/devset_$m --tag qj_${m}_h36_tiles > "$RES/qj_score_$m.log" 2>&1 || abort "QJ_FAIL scoring $m failed (qj_score_$m.log)"
done
"${IN_NEXT[@]}" pkill -f local_vlm_server.py >/dev/null 2>&1 || true
python3 scripts/qj_analysis.py > "$RES/qj_analysis_stdout.log" || abort "analysis"
echo QJ_DONE
