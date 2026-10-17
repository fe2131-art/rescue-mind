#!/usr/bin/env bash
# After study V: merge study W (image-level; registration = this merge, before any W image is rendered), test, then run W.
cd "$(dirname "$0")/.."
until grep -qE "V_DONE|V_ABORT" "$1" 2>/dev/null; do sleep 120; done
date +%H:%M; grep -E "V_DONE|V_ABORT" "$1" | tail -1
grep -q V_DONE "$1" || { echo "W_NOT_STARTED (V did not finish)"; exit 1; }
if ! git merge-base --is-ancestor worktree-agent-a065158341fac6202 HEAD; then
  git merge --no-edit -m "study W: pre-registration, protocol, image builder, paraphrase endpoint, analysis and tests (registered before any W image is rendered or scored)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" worktree-agent-a065158341fac6202 || { git merge --abort; echo "W_MERGE_CONFLICT"; exit 1; }
  if nice -n 10 python3 -m unittest discover -s tests > experiments/results/after_v_tests.log 2>&1; then git push -q; echo W_REGISTERED
  else git revert -m 1 --no-edit HEAD -q; git push -q; echo "W_TESTS_FAILED (merge reverted)"; exit 1; fi
fi
docker exec rm-next rescuemind-entrypoint bash scripts/w_render.sh || { echo W_RENDER_ABORT; exit 1; }
docker exec rm-next rescuemind-entrypoint bash scripts/w_eval.sh || { echo W_EVAL_ABORT; exit 1; }
echo W_DONE
