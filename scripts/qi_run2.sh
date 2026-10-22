#!/usr/bin/env bash
# Study QI, Amendment 2 (descriptive extension, no claim): after scripts/qi_run.sh has finished, generate a LARGER fire (G2) and two non-fire look-alikes (K1 vest, K2 warning lamp)
# inside the same masks of the same twins, score them with the frozen gate, and rerun the analysis.  Run:  bash scripts/qi_run2.sh   (via Bash run_in_background)
set -uo pipefail
cd "$(dirname "$0")/.."
RES=experiments/results
IN_NEXT=(docker exec rm-next rescuemind-entrypoint)
abort() { echo "QI_ABORT: $*" | tee -a $RES/qi_run.log >&2; exit 1; }
for _ in $(seq 1 1440); do pgrep -f '^bash scripts/qi_run\.sh$' >/dev/null || break; sleep 60; done          # the main QI sequence first (one GPU, one lock)
grep -q QI_DONE <(tail -5 $RES/qi_run.log) || abort "qi_run.sh did not end with QI_DONE; Amendment 2 not run"
exec 9>/tmp/rescuemind_campaign.lock
flock 9
for m in G2 K1 K2; do
  "${IN_NEXT[@]}" bash -c "cd $PWD && HF_HUB_OFFLINE=1 PYTHONPATH=/hf/qi_pylib python3 scripts/qi_generate.py --fast --mode $m --dtype float16" >> $RES/qi_generate.log 2>&1 || abort "generation $m failed (rerun resumes)"
done
python3 scripts/qi_build_devset.py || abort "devset build"
"${IN_NEXT[@]}" pkill -f local_vlm_server.py >/dev/null 2>&1 || true
sleep 10
docker exec -d rm-next rescuemind-entrypoint bash -c "cd $PWD && HF_HUB_OFFLINE=1 python3 scripts/local_vlm_server.py --model Qwen/Qwen3.5-9B --prompt-set v35 --port 8765 --hazard-prompt h36 --hazard-views tiles > $PWD/$RES/qi_server2.log 2>&1"
for _ in $(seq 1 300); do curl -s -m 5 http://127.0.0.1:8765/health 2>/dev/null | grep -q ready && break; sleep 3; done
curl -s -m 5 http://127.0.0.1:8765/health | grep -q ready || abort "gate server not ready (qi_server2.log)"
for m in G2 K1 K2; do
  [ -f "$RES/devset_qi_${m}_h36_tiles.json" ] && continue
  [ -s "outputs/qi/devset_$m/labels.jsonl" ] || continue
  python3 scripts/vlm_devset_eval.py --model Qwen/Qwen3.5-9B --devset outputs/qi/devset_$m --tag qi_${m}_h36_tiles > "$RES/qi_score_$m.log" 2>&1 || abort "QI_FAIL scoring $m failed (qi_score_$m.log)"
done
"${IN_NEXT[@]}" pkill -f local_vlm_server.py >/dev/null 2>&1 || true
python3 scripts/qi_analysis.py > "$RES/qi_analysis_stdout2.log" || abort "analysis"
echo QI2_DONE
