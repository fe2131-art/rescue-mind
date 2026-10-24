#!/usr/bin/env bash
# Study IJ (an answerability probe for unknown destinations; experiments/PREREGISTRATION_IJ.md): about 15 minutes of GPU.  Run on the HOST: bash scripts/ij_run.sh
# 1) hidden states and the zero-shot yes-probability (rm-next, no server), 2) the closed-set destination probabilities of the submitted parser (VLM server on 8765), 3) the analysis (CPU).  Prints IJ_DONE or IJ_ABORT.
set -uo pipefail
cd "$(dirname "$0")/.."
exec 9>/tmp/rescuemind_campaign.lock
flock 9
CT=${IJ_CONTAINER:-rm-next}
RES=experiments/results
STOP=$RES/ij_stop_server.sh
LOG=$RES/ij_server.log
abort() { echo "IJ_ABORT: $*" >&2; exit 1; }
for f in experiments/PREREGISTRATION_IJ.md experiments/intent_eval/ij_v1.jsonl scripts/make_intent_ij_set.py scripts/ij_extract.py scripts/ij_closedset.py scripts/ij_analysis.py scripts/ij_run.sh rescuemind/intent_llm.py; do
  git ls-files --error-unmatch "$f" >/dev/null 2>&1 || abort "$f is not committed"
  git diff --quiet HEAD -- "$f" || abort "$f has uncommitted changes"
done
grep -q '^Status: REGISTERED' experiments/PREREGISTRATION_IJ.md || abort "PREREGISTRATION_IJ.md is not marked REGISTERED"
if curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1; then abort "port 8765 is already in use"; fi
mkdir -p "$RES"
# (1) hidden states (no server running)
if [ ! -f "$RES/ij_features.npz" ]; then
  docker exec "$CT" rescuemind-entrypoint bash -c "cd $PWD && HF_HUB_OFFLINE=1 python3 scripts/ij_extract.py" 2>&1 | tail -3
  [ -f "$RES/ij_features.npz" ] || abort "feature extraction failed"
fi
echo IJ_FEATURES_DONE
# (2) closed-set destination probabilities of the submitted parser
cat > "$STOP" <<'EOS'
#!/usr/bin/env bash
pkill -f local_vlm_server.py || true
for _ in $(seq 1 120); do curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1 || exit 0; sleep 1; done
exit 1
EOS
stop_server() { docker exec "$CT" rescuemind-entrypoint bash "$STOP"; while curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1; do sleep 1; done; sleep 5; }
docker exec -d "$CT" rescuemind-entrypoint bash -c "cd $PWD && HF_HUB_OFFLINE=1 python3 scripts/local_vlm_server.py --model Qwen/Qwen3.5-9B --prompt-set v35 --intent-prompt i35 --port 8765 > $PWD/$LOG 2>&1"
for _ in $(seq 1 200); do curl -s -m 5 http://127.0.0.1:8765/health | grep -q ready && break; sleep 3; done
curl -s -m 5 http://127.0.0.1:8765/health | grep -q ready || { stop_server; abort "server did not become ready (see $LOG)"; }
python3 scripts/ij_closedset.py; rc=$?
stop_server
[ $rc -eq 0 ] || abort "closed-set queries failed (rc=$rc)"
# (3) analysis
python3 scripts/ij_analysis.py || abort "analysis failed"
echo IJ_DONE
