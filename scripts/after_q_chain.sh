#!/usr/bin/env bash
# After study Q: merge the integration branch i21-depot (I-19..I-22, depot, k stations, studies A/S/X/XD) into main,
# test, fetch the depot assets, then run study A (pilot -> masks -> registration gate -> 226 runs -> analysis).
cd "$(dirname "$0")/.."
until grep -qE "Q_CHAIN_DONE|Q_RUN_ABORT|Q_MERGE_CONFLICT|Q_TESTS_FAILED" "$1" 2>/dev/null; do sleep 120; done
date +%H:%M; grep -E "Q_CHAIN_DONE|ABORT|CONFLICT|FAILED" "$1" | tail -1
git fetch -q origin
if ! git merge-base --is-ancestor origin/i21-depot HEAD; then
  git merge --no-edit -m "Merge the integration branch i21-depot: I-19 advice may only tighten, I-20 adaptive views, I-21 realistic depot and k stations, I-22 delivery interlock, studies A/S/X/XD registered drafts, restructured paper/report/README

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" origin/i21-depot || { git merge --abort; echo INTEGRATION_MERGE_CONFLICT; exit 1; }
  nice -n 10 python3 -m unittest discover -s tests > experiments/results/after_q_tests.log 2>&1 || { echo "INTEGRATION_TESTS_FAILED (merge kept; see after_q_tests.log)"; exit 1; }
  git push -q; echo INTEGRATION_MERGED
fi
bash scripts/fetch_depot_assets.sh || echo "WARN: depot assets not fetched"
bash scripts/a_run.sh || { echo A_CHAIN_ABORT; exit 1; }
echo A_CHAIN_DONE
