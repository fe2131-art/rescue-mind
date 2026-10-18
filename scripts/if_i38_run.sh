#!/usr/bin/env bash
# EXPLORATORY re-run of study IF's 36+ texts with intent prompt i38 (the prompt study A used; R9 noted that IF measured only the shipped i35).
# Not a registered claim: the registered IF result stays the i35 one.  Output: experiments/results/if_i38_raw.jsonl, if_i38_summary.json.
# About 2 minutes of GPU.  Run on the HOST: bash scripts/if_i38_run.sh.  Prints IF_I38_DONE, or IF_ABORT.  Port 8765 must be free.
set -uo pipefail
cd "$(dirname "$0")/.."
CT=${IF_CONTAINER:-rm-next}
STOP=experiments/results/if_i38_stop_server.sh
LOG=experiments/results/if_i38_server.log
export IF_TAG=i38
abort() { echo "IF_ABORT: $*" >&2; exit 1; }
for f in experiments/PREREGISTRATION_IF.md experiments/intent_flip_set.jsonl scripts/intent_flip_eval.py; do
  git ls-files --error-unmatch "$f" >/dev/null 2>&1 || abort "$f is not committed"
  git diff --quiet HEAD -- "$f" || abort "$f has uncommitted changes"
done
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
  "cd $PWD && HF_HUB_OFFLINE=1 python3 scripts/local_vlm_server.py --model Qwen/Qwen3.5-9B --prompt-set v35 --intent-prompt i38 --port 8765 > $PWD/$LOG 2>&1"
for _ in $(seq 1 200); do curl -s -m 5 http://127.0.0.1:8765/health | grep -q ready && break; sleep 3; done
curl -s -m 5 http://127.0.0.1:8765/health | grep -q ready || { stop_server; abort "server did not become ready (see $LOG)"; }
python3 scripts/intent_flip_eval.py --run; rc=$?
stop_server
[ $rc -eq 0 ] || abort "scoring failed (rc=$rc)"
# the registered rule counts a parser error as a refusal; a server that died half way would then look like a defence that works
nerr=$(python3 -c "
import json
print(sum(1 for l in open('experiments/results/if_i38_raw.jsonl') if l.strip() and json.loads(l).get('error')))")
[ "${nerr:-1}" -eq 0 ] || abort "$nerr of the texts ended in a parser error (server problem? see $LOG); if_i38_raw.jsonl is kept; move its error rows to the trash folder and rerun to resume"
python3 scripts/intent_flip_eval.py --analyse || abort "analysis failed"
echo IF_I38_DONE
