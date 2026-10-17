#!/usr/bin/env bash
# After study W: merge and register study Q (real-photo supply check; registration = this merge, before any Q inference), run it.
cd "$(dirname "$0")/.."
until grep -qE "W_DONE|W_.*ABORT|W_NOT_STARTED|W_MERGE_CONFLICT|W_TESTS_FAILED" "$1" 2>/dev/null; do sleep 120; done
date +%H:%M; grep -E "W_DONE|ABORT|NOT_STARTED|CONFLICT|FAILED" "$1" | tail -1
if ! git merge-base --is-ancestor worktree-agent-ac893207bdda069d9 HEAD; then
  git merge --no-edit -m "study Q: pre-registration, sample (405 Wikimedia Commons photos, licence per image, label audit frozen), fetch/eval/analysis, run script (registered before any Q inference)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" worktree-agent-ac893207bdda069d9 || { git merge --abort; echo Q_MERGE_CONFLICT; exit 1; }
  nice -n 10 python3 -m unittest discover -s tests > experiments/results/after_w_tests.log 2>&1 || { echo "Q_TESTS_FAILED (see after_w_tests.log; merge kept for inspection)"; exit 1; }
  git push -q; echo Q_REGISTERED
fi
bash scripts/q_run.sh || { echo Q_RUN_ABORT; exit 1; }
echo Q_CHAIN_DONE
