#!/usr/bin/env bash
# Study QI (I-82; experiments/PREREGISTRATION_QI.md), full sequence: wait for study GL, then (under the campaign lock) pilot -> generate R, G, C -> assemble the devsets
# -> start the frozen gate server (v3.6: h36 + tiles) -> score -> stop -> analysis.  Resumable (manifests, devset files).  Run:  bash scripts/qi_run.sh   (via Bash run_in_background)
set -uo pipefail
cd "$(dirname "$0")/.."
RES=experiments/results
IN_NEXT=(docker exec rm-next rescuemind-entrypoint)
abort() { echo "QI_ABORT: $*" | tee -a experiments/results/qi_run.log >&2; exit 1; }
for _ in $(seq 1 1440); do pgrep -f '^bash scripts/gl_run\.sh$' >/dev/null || break; sleep 60; done          # study GL first (one GPU, one lock)
exec 9>/tmp/rescuemind_campaign.lock
flock 9
grep -q FETCH_DONE "$RES/qi_fetch.log" && ! grep -q "^BAD" "$RES/qi_fetch.log" || abort "weights incomplete (qi_fetch.log)"
git ls-files --error-unmatch experiments/PREREGISTRATION_QI.md >/dev/null 2>&1 || abort "PREREGISTRATION_QI.md is not committed"
gen() { "${IN_NEXT[@]}" bash -c "cd $PWD && HF_HUB_OFFLINE=1 PYTHONPATH=/hf/qi_pylib python3 scripts/qi_generate.py --fast $*"; }
DT=float16
if [ ! -s "$RES/qi_manifest_G_pilot.jsonl" ]; then
  gen --mode G --limit 3 --tag _pilot --dtype float16 >> "$RES/qi_generate.log" 2>&1 || { DT=bfloat16; gen --mode G --limit 3 --tag _pilot --dtype bfloat16 >> "$RES/qi_generate.log" 2>&1 || abort "pilot failed in fp16 and bf16 (qi_generate.log)"; }
fi
python3 - <<'PY' > "$RES/qi_dtype.txt"
import json
m=[json.loads(x) for x in open('experiments/results/qi_manifest_G_pilot.jsonl')]
print(m[0]['dtype'])
PY
DT=$(cat "$RES/qi_dtype.txt")
echo "QI_PILOT_OK dtype=$DT"
for m in R G C; do gen --mode $m --dtype "$DT" >> "$RES/qi_generate.log" 2>&1 || abort "generation $m failed (rerun resumes)"; done
python3 scripts/qi_build_devset.py || abort "devset build"
echo "QI_GENERATED"
# frozen gate server, exactly as scripts/xd_eval.sh starts it
"${IN_NEXT[@]}" pkill -f local_vlm_server.py >/dev/null 2>&1 || true
sleep 10
docker exec -d rm-next rescuemind-entrypoint bash -c "cd $PWD && HF_HUB_OFFLINE=1 python3 scripts/local_vlm_server.py --model Qwen/Qwen3.5-9B --prompt-set v35 --port 8765 --hazard-prompt h36 --hazard-views tiles > $PWD/$RES/qi_server.log 2>&1"
for _ in $(seq 1 300); do curl -s -m 5 http://127.0.0.1:8765/health 2>/dev/null | grep -q ready && break; sleep 3; done
curl -s -m 5 http://127.0.0.1:8765/health | grep -q ready || abort "gate server not ready (qi_server.log)"
for m in R G C; do
  [ -f "$RES/devset_qi_${m}_h36_tiles.json" ] && continue
  [ -s "outputs/qi/devset_$m/labels.jsonl" ] || continue
  python3 scripts/vlm_devset_eval.py --model Qwen/Qwen3.5-9B --devset outputs/qi/devset_$m --tag qi_${m}_h36_tiles > "$RES/qi_score_$m.log" 2>&1 || abort "QI_FAIL scoring $m failed (qi_score_$m.log)"
done
"${IN_NEXT[@]}" pkill -f local_vlm_server.py >/dev/null 2>&1 || true
for j in internvl3 idefics3 smolvlm2; do            # P3 (descriptive): the other families on the generated fires and the control edits
  for m in G C; do
    [ -s "outputs/qi/devset_$m/labels.jsonl" ] && "${IN_NEXT[@]}" bash -c "cd $PWD && HF_HUB_OFFLINE=1 python3 scripts/jev_score.py --judge $j --set qi_$m" >> "$RES/qi_judges.log" 2>&1
  done
done
python3 scripts/qi_analysis.py > "$RES/qi_analysis_stdout.log" || abort "analysis"
echo QI_DONE
