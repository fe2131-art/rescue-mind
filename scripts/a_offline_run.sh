#!/usr/bin/env bash
# Study A offline set (PREREGISTRATION_A.md "Offline set", Amendment 1: intent prompt i38): the TEST half, scored once.  bash scripts/a_offline_run.sh
# Prints A_OFFLINE_DONE, or A_OFFLINE_ABORT on any failure.  Nothing else may be using port 8765 or the GPU.
set -uo pipefail
cd "$(dirname "$0")/.."
CT=${IF_CONTAINER:-rm-next}
STOP=experiments/results/a_offline_stop_server.sh
LOG=experiments/results/a_offline_server.log
abort() { echo "A_OFFLINE_ABORT: $*" >&2; exit 1; }
for f in experiments/PREREGISTRATION_A.md experiments/advice_injection_set.jsonl experiments/advice_prompts_frozen.json scripts/advice_injection_eval.py; do
  git ls-files --error-unmatch "$f" >/dev/null 2>&1 || abort "$f is not committed"
  git diff --quiet HEAD -- "$f" || abort "$f has uncommitted changes"
done
[ -s experiments/results/advice_injection_eval_test.json ] && { echo "A_OFFLINE_ABORT: the test half was already scored (scored once only)" >&2; exit 1; }
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
python3 scripts/advice_injection_eval.py --split test --out experiments/results/advice_injection_eval_test.json; rc=$?
stop_server
[ $rc -eq 0 ] || abort "scoring failed (rc=$rc)"
echo A_OFFLINE_DONE
