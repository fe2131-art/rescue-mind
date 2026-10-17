#!/usr/bin/env bash
# After campaign J: film the memory demo (I-15), then study P2 (real-photo threshold calibration).
cd "$(dirname "$0")/.."
until grep -qE "J_DONE|J_SKIPPED" "$1" 2>/dev/null; do sleep 60; done
docker exec rm-next rescuemind-entrypoint bash scripts/film_memory.sh > experiments/results/film_memory_runs.txt 2>&1
echo FILM_MEMORY_DONE
bash scripts/p2_eval.sh > experiments/results/p2_eval_stdout.log 2>&1
echo P2_DONE
