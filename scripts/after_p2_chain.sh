#!/usr/bin/env bash
# After P2: merge the per-run layout support (I-17, branch worktree-agent-ac85b5ba081cc1f61), test, then run study L.
cd "$(dirname "$0")/.."
until grep -q P2_DONE "$1" 2>/dev/null; do sleep 60; done
git merge --no-edit -m "I-17: per-run arena layouts (study L support: layout model, build_variant(layout), per-run configs, --centers, audits follow the layout)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" worktree-agent-ac85b5ba081cc1f61 || { git merge --abort; echo MERGE_CONFLICT; exit 1; }
docker exec rm-dev rescuemind-entrypoint python3 -m unittest discover -s tests > experiments/results/l_merge_tests.log 2>&1 || { echo TESTS_FAILED; exit 1; }
git push -q && echo MERGED
bash scripts/l_run.sh > experiments/results/l_run_stdout.log 2>&1
tail -3 experiments/results/l_run_stdout.log
