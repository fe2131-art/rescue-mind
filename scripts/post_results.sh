#!/usr/bin/env bash
# After a registered study ends (I-170): regenerate everything that reads result files, then run the completeness checks.
#   bash scripts/post_results.sh JL IJ JM      # exit 1 if a check fails; the Reading paragraphs and FINDINGS rows are written by hand before
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/multiplicity.py | tail -1
nice -n 10 python3 scripts/paper_numbers.py | tail -1 | cut -c1-80
python3 scripts/make_registrations.py | tail -1
python3 scripts/trial_chain.py --write | head -1
python3 scripts/update_readme_results.py | tail -1 | cut -c1-80
python3 scripts/make_youtube_description.py | tail -1 | cut -c1-100
python3 scripts/check_bib.py | tail -1
python3 scripts/check_study_coverage.py | tail -1
python3 scripts/ingest_check.py "$@"
echo POST_RESULTS_OK
