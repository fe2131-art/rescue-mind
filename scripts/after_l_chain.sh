#!/usr/bin/env bash
# After study L: merge the I-18 post-run report hook (no effect on decisions), run the tests, then study V.
cd "$(dirname "$0")/.."
until grep -qE "L_DONE|L_ABORT|MERGE_CONFLICT" "$1" 2>/dev/null; do sleep 120; done
date +%H:%M; grep -E "L_DONE|L_ABORT|MERGE_CONFLICT" "$1" | tail -1
if git merge-base --is-ancestor worktree-agent-a94afbeadff714e1e HEAD; then echo "I-18 already merged"
elif git merge --no-edit -m "I-18: operator report generated after every run (non-fatal post-run hook, --no-operator-report)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" worktree-agent-a94afbeadff714e1e; then
  if nice -n 10 python3 -m unittest discover -s tests > experiments/results/after_l_tests.log 2>&1; then git push -q; echo "I18_MERGED"
  else git reset --hard HEAD~1 -q; echo "I18_TESTS_FAILED (merge reverted; see experiments/results/after_l_tests.log)"; fi
else git merge --abort; echo "I18_MERGE_CONFLICT (skipped)"; fi
bash scripts/v_run.sh
