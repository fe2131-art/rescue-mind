#!/usr/bin/env bash
# The final check, to be rerun after EVERY integration (user rule 2026-10-23: "最終確認は常にする").  Commits nothing; prints one PASS/FAIL line per item and a verdict.
#   nice -n 10 bash scripts/final_check.sh            # everything (build, page/word limits, consistency, tests, secret scan, submission facts)
#   QUICK=1 nice -n 10 bash scripts/final_check.sh    # skips the unit tests and the report rebuild
# CPU heavy: run it next to GPU-only jobs (image generation, scoring), not next to closed-loop (Gazebo) campaigns.
cd "$(dirname "$0")/.."
FAILS=0
say() { echo "$1 $2"; [ "$1" = FAIL ] && FAILS=$((FAILS+1)); }
step() { local name="$1"; shift; if "$@" >/tmp/final_check_step.log 2>&1; then say PASS "$name"; else say FAIL "$name: $(tail -2 /tmp/final_check_step.log | tr '\n' ' ' | cut -c1-200)"; fi; }
step "git: tracked files committed (no staged-only drift)" bash -c '! git diff --cached --quiet && exit 1 || exit 0'
if [ -z "$QUICK" ]; then step "rebuild documents" bash scripts/rebuild_docs.sh; else step "paper numbers only" python3 scripts/paper_numbers.py; fi
# page limit: the paper body (everything before the references) must end on page 8; the abstract has its own check in check_consistency.py
PDF=docs/paper/main.pdf
if [ -f $PDF ]; then
  docker run --rm -v "$PWD:/w:ro" -w /w rescuemind:latex bash -c '
    n=$(pdfinfo docs/paper/main.pdf | awk "/^Pages/{print \$2}")
    last=0; for p in $(seq 1 $n); do if pdftotext -f $p -l $p docs/paper/main.pdf - | grep -qE "^([0-9]+\.? +)?(Conclusion|Conclusions|Discussion and Conclusion)"; then last=$p; fi; done
    echo "pages=$n conclusion_page=$last"; [ "$last" -le 8 ] && [ "$last" -ge 1 ]' > /tmp/final_check_pages.log 2>&1 && say PASS "paper body within 8 pages ($(tail -1 /tmp/final_check_pages.log))" || say FAIL "paper body page limit ($(tail -1 /tmp/final_check_pages.log))"
else say FAIL "main.pdf missing"; fi
step "consistency (0 mismatches)" bash -c 'python3 scripts/check_consistency.py 2>&1 | tail -1 | grep -q "^0 mismatch"'
step "secret scan (HEAD tree)" python3 scripts/secret_scan.py
step "readme links" python3 scripts/check_readme_links.py
if [ -z "$QUICK" ]; then
  step "unit tests" make test
  step "test count in docs" bash -c 'n=$(python3 scripts/count_tests.py | grep -oE "[0-9]+" | head -1); grep -q "$n" docs/HANDOFF.md'
fi
step "submission facts (video, report pages)" python3 scripts/update_submission_facts.py
[ -f docs/YOUTUBE_DESCRIPTION.md ] && step "YouTube description <= 5000 chars" bash -c 'n=$(sed -n "/^## 概要欄/,/^## 公開設定チェック/p" docs/YOUTUBE_DESCRIPTION.md | sed "1d;\$d" | wc -m); [ "$n" -le 5000 ]'
VID=outputs/video/PAI最終課題_tetsutetsu.mp4
if [ -f "$VID" ]; then step "video 60-180 s" bash -c 'd=$(ffprobe -v error -show_entries format=duration -of csv=p=0 '"$VID"'); python3 -c "import sys;d=float(\"$d\");sys.exit(0 if 60<=d<=180 else 1)"'; fi
echo "FINAL_CHECK_DONE fails=$FAILS"
[ "$FAILS" -eq 0 ]
