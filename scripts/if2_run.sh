#!/usr/bin/env bash
# Study IF2 (experiments/PREREGISTRATION_IF2.md, I-27): about 2 minutes of GPU.  Run on the HOST: bash scripts/if2_run.sh
# Prints IF2_DONE, or IF2_ABORT on any failure.  Nothing else may be using port 8765 or the GPU.
set -uo pipefail
cd "$(dirname "$0")/.."
CT=${IF_CONTAINER:-rm-next}
STOP=experiments/results/if2_stop_server.sh
LOG=experiments/results/if2_server.log
abort() { echo "IF2_ABORT: $*" >&2; exit 1; }
for f in experiments/PREREGISTRATION_IF2.md experiments/intent_flip_set2.jsonl scripts/intent_flip2_eval.py rescuemind/intent_llm.py; do
  git ls-files --error-unmatch "$f" >/dev/null 2>&1 || abort "$f is not committed"
  git diff --quiet HEAD -- "$f" || abort "$f has uncommitted changes"
done
grep -q '^Status: REGISTERED' experiments/PREREGISTRATION_IF2.md || abort "PREREGISTRATION_IF2.md is not marked REGISTERED"
if curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1; then abort "port 8765 is already in use"; fi
mkdir -p experiments/results
cat > "$STOP" <<'EOS'
#!/usr/bin/env bash
pkill -f local_vlm_server.py || true
for _ in $(seq 1 120); do curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1 || exit 0; sleep 1; done
exit 1
EOS
stop_server() {
  docker exec "$CT" rescuemind-entrypoint bash "$STOP"
  while curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1; do sleep 1; done
  sleep 5
}
docker exec -d "$CT" rescuemind-entrypoint bash -c \
  "cd $PWD && HF_HUB_OFFLINE=1 python3 scripts/local_vlm_server.py --model Qwen/Qwen3.5-9B --prompt-set v35 --intent-prompt i35 --port 8765 > $PWD/$LOG 2>&1"
for _ in $(seq 1 200); do curl -s -m 5 http://127.0.0.1:8765/health | grep -q ready && break; sleep 3; done
curl -s -m 5 http://127.0.0.1:8765/health | grep -q ready || { stop_server; abort "server did not become ready (see $LOG)"; }
python3 scripts/intent_flip2_eval.py --run; rc=$?
stop_server
[ $rc -eq 0 ] || abort "scoring failed (rc=$rc)"
# the registered rule counts a parser error as a refusal; a server that died half way would then look like a defence that works
nerr=$(python3 -c "
import json
print(sum(1 for l in open('experiments/results/if2_raw.jsonl') if l.strip() and json.loads(l).get('error')))")
[ "${nerr:-1}" -eq 0 ] || abort "$nerr of the texts ended in a parser error (server problem? see $LOG); if2_raw.jsonl is kept, delete its rows with an error and rerun to resume"
python3 scripts/intent_flip2_eval.py --analyse || abort "analysis failed"
echo IF2_DONE
