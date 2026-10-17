#!/usr/bin/env bash
# Study Q (experiments/PREREGISTRATION_Q.md): the whole GPU part, unattended.  Run on the HOST:  bash scripts/q_run.sh
# Qwen3.5-9B supply check (server in the container rm-next, client on the host) -> SigLIP/CLIP baselines (in the container)
# -> analysis.  Prints Q_DONE at the end, Q_ABORT on any failure.  Nothing else may be using port 8765 or the GPU.
set -uo pipefail
cd "$(dirname "$0")/.."
PY=${Q_PYTHON:-$HOME/.cache/rescuemind/pqvenv/bin/python}   # any Python with Pillow
CT=${Q_CONTAINER:-rm-next}
STOP=experiments/results/q_stop_server.sh
LOG=experiments/results/q_server.log
abort() { echo "Q_ABORT: $*" >&2; exit 1; }

# the registration must be committed and unchanged before anything is scored
for f in experiments/PREREGISTRATION_Q.md experiments/q_sample_final.json experiments/q_exclusions.json experiments/q_sample.json; do
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
  sleep 5   # let the GPU memory be released
}

# the container does not mount ~/.cache: stage the 405 final images in a git-ignored repo directory (sha256 checked)
"$PY" scripts/q_eval.py --stage || abort "staging the images failed"

docker exec -d "$CT" rescuemind-entrypoint bash -c \
  "cd $PWD && HF_HUB_OFFLINE=1 python3 scripts/local_vlm_server.py --model Qwen/Qwen3.5-9B --prompt-set v35 --port 8765 > $PWD/$LOG 2>&1"
for _ in $(seq 1 200); do curl -s -m 5 http://127.0.0.1:8765/health | grep -q ready && break; sleep 3; done
curl -s -m 5 http://127.0.0.1:8765/health | grep -q ready || { stop_server; abort "server did not become ready (see $LOG)"; }
"$PY" scripts/q_eval.py --run; rc=$?
stop_server
[ $rc -eq 0 ] || abort "Qwen scoring failed (rc=$rc)"
echo "DONE qwen"

docker exec "$CT" rescuemind-entrypoint bash -c "cd $PWD && HF_HUB_OFFLINE=1 python3 scripts/q_eval.py --zeroshot" || abort "zero-shot baselines failed"
echo "DONE zeroshot"
python3 scripts/q_analysis.py || abort "analysis failed"
echo Q_DONE
