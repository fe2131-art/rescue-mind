#!/usr/bin/env bash
# Submission snapshot (`make snapshot`): if some registered studies (A, S, X, XD, B, IF, Q) have no results at the submission freeze, the paper,
# the supplement, the report, the README text and the YouTube text still read as finished documents: every pending result is the phrase
# "registered, not yet run at submission" (登録済み・提出時点で未実施), with its registration commit and date in the study table.
#
#   make snapshot                 # = bash scripts/build_snapshot.sh   (all of it; nothing tracked is changed)
#   SKIP_PDF=1 make snapshot      # texts only (README, YouTube, paper numbers): no docker, no LaTeX
#   bash scripts/build_snapshot.sh --apply   # additionally copy the snapshot README.md / YOUTUBE_DESCRIPTION.md over the tracked files (a deliberate step at the freeze)
#
# Output (not tracked, docs/snapshot/ is in .gitignore): paper/main.pdf, paper/supplement.pdf, report/*.pdf, README.md, YOUTUBE_DESCRIPTION.md.
# FINAL=1 is the opposite mode (all results present, any pending result refuses the build) and cannot be combined with this one.
# CPU: one core at the lowest priority (a measuring study may be running); no Gazebo, no GPU.
set -euo pipefail
cd "$(dirname "$0")/.."
case "${FINAL:-}" in ''|0) ;; *) echo "SNAPSHOT and FINAL=1 exclude each other" >&2; exit 2;; esac
export SNAPSHOT=1
ACCOUNT="${ACCOUNT:-tetsutetsu}"
DEV="${DEV:-rm-dev}"
python3 scripts/update_readme_results.py --snapshot
python3 scripts/make_youtube_description.py --snapshot 2>&1 | grep -v "^WARNING: chapter" || true
SNAP_DIR="${SNAPSHOT_DIR:-docs/snapshot}"
mkdir -p "$SNAP_DIR/paper"
python3 scripts/paper_numbers.py --snapshot --out "$SNAP_DIR/paper"
if [ "${SKIP_PDF:-0}" != 1 ]; then
  bash scripts/build_paper.sh
  # reportlab lives in the dev container; run the worktree's script from the worktree directory
  nice -n 19 docker exec -w "$PWD" "$DEV" rescuemind-entrypoint python3 scripts/make_report.py --account "$ACCOUNT" --snapshot
fi
python3 scripts/check_consistency.py --snapshot --no-report || true
if [ "${1:-}" = --apply ]; then
  cp "$SNAP_DIR/README.md" README.md
  cp "$SNAP_DIR/YOUTUBE_DESCRIPTION.md" docs/YOUTUBE_DESCRIPTION.md
  echo "applied: README.md and docs/YOUTUBE_DESCRIPTION.md now carry the snapshot wording (commit them at the freeze)"
fi
echo "snapshot done: docs/snapshot/"
