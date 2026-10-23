#!/usr/bin/env bash
# Rebuild every result-dependent document in the safe order (this is what /tmp/rebuild.sh did; now kept in the repo).  Commits nothing.
#   nice -n 10 bash scripts/rebuild_docs.sh
# Never call scripts/build_paper.sh directly: it regenerates the figures, which are restored here with `git checkout --` (fig_calibration.pdf is kept).
cd "$(dirname "$0")/.."
python3 scripts/paper_numbers.py >/dev/null 2>&1 || { echo "FAIL paper_numbers"; exit 1; }
make paper > /tmp/paper_build.log 2>&1 || { echo "FAIL make paper (see /tmp/paper_build.log)"; tail -5 /tmp/paper_build.log; exit 1; }
git checkout -- docs/paper/fig_e_trajectories.pdf docs/paper/fig_fire_size.pdf docs/paper/fig_h_outcomes.pdf docs/paper/fig_lookaround.pdf docs/paper/fig_r_examples.pdf docs/paper/fig_risk_coverage.pdf docs/paper/fig_system.pdf docs/paper/fig_t1_examples.pdf
python3 scripts/update_readme_results.py | tail -1 | cut -c1-60
python3 scripts/make_youtube_description.py | tail -1 | cut -c1-60
docker exec rm-dev rescuemind-entrypoint bash -c "cd $PWD && python3 scripts/make_report.py --account tetsutetsu" 2>&1 | grep -i "main part\|Traceback"
python3 scripts/make_registrations.py | tail -1
echo REBUILD_OK
