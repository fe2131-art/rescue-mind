#!/usr/bin/env bash
# P2 (experiments/PREREGISTRATION_P2.md): score the calibration and test samples with both hazard wordings, then analyse.
# Run on the HOST (the client needs pyarrow, which the container lacks):  bash scripts/p2_eval.sh
# The VLM server runs in the container rm-next (host network, same repo path); nothing else may be using port 8765.
set -uo pipefail
cd "$(dirname "$0")/.."
PY=${P2_PYTHON:-/tmp/claude-1008/-home-tetsutani-work-rescue-mind/f9e995f0-1ad1-4f13-bc51-5244c361c481/scratchpad/pqvenv/bin/python}
CT=${P2_CONTAINER:-rm-next}
STOP=experiments/results/p2_stop_server.sh
LOG=experiments/results/p2_server.log

# stop script (runs inside the container)
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

if curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1; then
  echo "port 8765 is already in use; refusing to start" >&2; exit 1
fi
[ -f experiments/results/p2_sample.json ] || "$PY" scripts/p2_calibration.py --sample || exit 1

for w in h36 h35; do
  docker exec -d "$CT" rescuemind-entrypoint bash -c \
    "cd $PWD && HF_HUB_OFFLINE=1 python3 scripts/local_vlm_server.py --model Qwen/Qwen3.5-9B --prompt-set v35 --port 8765 --hazard-prompt $w --hazard-views tiles > $PWD/$LOG.$w 2>&1"
  until curl -s -m 5 http://127.0.0.1:8765/health | grep -q ready; do sleep 3; done
  "$PY" scripts/p2_calibration.py --run --wording "$w"; rc=$?
  stop_server
  if [ $rc -ne 0 ]; then echo "scoring failed for $w (rc=$rc)" >&2; exit $rc; fi
  echo "DONE $w"
done
python3 scripts/p2_calibration.py --analyse
