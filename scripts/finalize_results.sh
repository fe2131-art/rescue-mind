#!/usr/bin/env bash
# One idempotent pipeline to run AFTER the campaigns have finished: regenerates every derived artefact in order.
#
#   bash scripts/finalize_results.sh                 # normal run
#   ALLOW_PARTIAL=1 bash scripts/finalize_results.sh # analyse campaign H even if its ledger has < planned_n final rows
#   ACCOUNT=name bash scripts/finalize_results.sh    # report account (default tetsutetsu)
#
# 1 analyses (each only if its inputs exist, else SKIP)   2 paper numbers + PDF + TBD report
# 3 report / README / YouTube + SUBMISSION               4 full unit-test suite in rm-dev
# 5 summary table; exit code != 0 iff some non-SKIP step FAILED.  Nothing is committed.
# Never touches rm-next or the GPU.  Host python3 for pure-stdlib/matplotlib scripts; rm-dev for ROS/reportlab ones.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
RES=experiments/results
ACCOUNT=${ACCOUNT:-tetsutetsu}
PQPY=${PQPY:-$HOME/.cache/rescuemind/pqvenv/bin/python}   # python with pyarrow (only needed for p2 --sample/--run, not --analyse)
LOGDIR=${FINALIZE_LOGDIR:-$(mktemp -d "${TMPDIR:-/tmp}/finalize_results.XXXXXX")}
IN_RMDEV=(docker exec rm-dev rescuemind-entrypoint)
NAMES=(); STATUS=(); NOTES=()
export PYTHONDONTWRITEBYTECODE=1

record() { NAMES+=("$1"); STATUS+=("$2"); NOTES+=("${3:-}"); printf '[%-4s] %-28s %s\n' "$2" "$1" "${3:-}"; }
skip()   { record "$1" SKIP "$2"; }
# step NAME CMD... : run, capture output to $LOGDIR/NAME.log, record OK/FAIL (tail of the log is shown on failure)
step() {
  local name=$1; shift
  echo ">>> $name: $*"
  if "$@" >"$LOGDIR/$name.log" 2>&1; then record "$name" OK
  else local rc=$?; tail -n 15 "$LOGDIR/$name.log" | sed 's/^/    | /'; record "$name" FAIL "rc=$rc, log $LOGDIR/$name.log"; fi
}
last_ok() { [ "${STATUS[$((${#STATUS[@]}-1))]}" = OK ]; }
pdf_pages() { # path relative to repo root -> page count (pdfinfo in the latex image), or '?'
  docker run --rm -v "$ROOT/$(dirname "$1"):/w:ro" rescuemind:latex pdfinfo "/w/$(basename "$1")" 2>/dev/null | awk '/^Pages:/{print $2}' | grep . || echo '?'
}

echo "finalize_results: logs in $LOGDIR"
if ! docker exec rm-dev true >/dev/null 2>&1; then
  echo "FATAL: container rm-dev is not running" >&2; exit 2
fi

# ---------------------------------------------------------------- 1. analyses
H_OK=0
HL=$RES/campaign_H_ledger.jsonl
if [ ! -f "$HL" ]; then
  skip h_analysis "no $HL"
else
  planned=$(python3 -c "import json;print(json.load(open('experiments/campaign_h_protocol.json'))['planned_n'])")
  have=$(python3 -c "
import json
print(sum(1 for x in open('$HL') if x.strip() and json.loads(x).get('final', True)))")
  if [ "$have" -lt "$planned" ]; then
    echo "WARNING: campaign H ledger has $have/$planned final rows (incomplete)" >&2
    NOTE_H="partial $have/$planned"
    if [ "${ALLOW_PARTIAL:-0}" != 1 ]; then
      skip h_analysis "incomplete $have/$planned final rows (ALLOW_PARTIAL=1 to force)"
    else step h_analysis python3 scripts/h_analysis.py; last_ok && H_OK=1; fi
  else
    step h_analysis python3 scripts/h_analysis.py; last_ok && H_OK=1
  fi
fi
if [ "$H_OK" = 1 ]; then step h_change_rate_model python3 scripts/h_change_rate_model.py; step h_k_scaling python3 scripts/h_k_scaling.py
else skip h_change_rate_model "h_analysis did not run/succeed"; fi

J_FINAL=$( [ -f $RES/campaign_J_ledger.jsonl ] && python3 -c "import json;print(sum(json.loads(l).get('final',True) for l in open('$RES/campaign_J_ledger.jsonl') if l.strip()))" || echo 0)
J_PLAN=$(python3 -c "import json;print(json.load(open('experiments/campaign_j_protocol.json'))['planned_n'])")
if [ -f $RES/campaign_J_ledger.jsonl ] && [ -f $RES/campaign_J_vram.csv ] && { [ "$J_FINAL" -ge "$J_PLAN" ] || [ "${ALLOW_PARTIAL:-0}" = 1 ]; }; then
  step j_analysis python3 scripts/j_analysis.py
else skip j_analysis "campaign J incomplete ($J_FINAL/$J_PLAN final rows)"; fi

V_FINAL=$( [ -f $RES/campaign_V_ledger.jsonl ] && python3 -c "import json;print(sum(json.loads(l).get('final',True) for l in open('$RES/campaign_V_ledger.jsonl') if l.strip()))" || echo 0)
V_PLAN=$(python3 -c "import json;print(json.load(open('experiments/campaign_v_protocol.json'))['planned_n'])")
if [ -f $RES/campaign_V_ledger.jsonl ] && [ -f $RES/v_predictions.json ] && [ -f experiments/campaign_v_protocol_design_fire_masks.json ] && { [ "$V_FINAL" -ge "$V_PLAN" ] || [ "${ALLOW_PARTIAL:-0}" = 1 ]; }; then
  step v_analysis python3 scripts/v_analysis.py
else skip v_analysis "study V incomplete ($V_FINAL/$V_PLAN final rows, or predictions/masks missing)"; fi

W_IN="devset_w_h36_tiles devset_t1_i11_h36_tiles devset_t1_i11_h36_full devset_t2_i11_h36_tiles devset_t2_i11_h36_full devset_w_para_dh devset_w_para_dh2 devset_w_para_t1 devset_w_para_t2"
W_MISS=""; for f in $W_IN; do [ -f $RES/$f.json ] || W_MISS="$W_MISS $f"; done
if [ -f scripts/w_analysis.py ] && [ -z "$W_MISS" ]; then
  step w_analysis python3 scripts/w_analysis.py
else skip w_analysis "study W incomplete (missing:${W_MISS:- scripts/w_analysis.py})"; fi

if [ -f $RES/p2_scores_h36.jsonl ] && [ -f $RES/p2_scores_h35.jsonl ]; then
  step p2_calibration python3 scripts/p2_calibration.py --analyse   # checks 400+400 rows per wording itself
else skip p2_calibration "need p2_scores_h36.jsonl and p2_scores_h35.jsonl"; fi

step r_analysis "${IN_RMDEV[@]}" python3 scripts/r_analysis.py
step count_tests "${IN_RMDEV[@]}" python3 scripts/count_tests.py

# ---------------------------------------------------------------- 2. paper
step paper_numbers python3 scripts/paper_numbers.py
step build_paper bash scripts/build_paper.sh
TBD_LIST=""
{ # report mode: never fatal.  Same criterion as `paper_numbers.py --final` (pending macros + pending tables).
  TBD_LIST=$( { grep -h '^.newcommand.*{.TBD}' docs/paper/numbers.tex 2>/dev/null | sed -E 's/^\\newcommand\{\\([A-Za-z]+)\}.*/\1/'
                grep -l '\\TBD' docs/paper/tab_*.tex 2>/dev/null | xargs -r -n1 basename; } | sort -u | paste -sd' ' - )
}
TBD_N=$(echo "$TBD_LIST" | wc -w)
echo "pending (TBD) macros/tables: $TBD_N"; [ "$TBD_N" -gt 0 ] && echo "  $TBD_LIST" | fold -s -w 150

# ---------------------------------------------------------------- 3. report / README / YouTube
step graphical_abstract "${IN_RMDEV[@]}" python3 scripts/make_graphical_abstract.py   # H/J numbers appear in the abstract automatically
step make_report "${IN_RMDEV[@]}" python3 scripts/make_report.py --account "$ACCOUNT"
step update_readme_results python3 scripts/update_readme_results.py
step make_youtube_description python3 scripts/make_youtube_description.py

# ---------------------------------------------------------------- 4. tests
step unit_tests "${IN_RMDEV[@]}" python3 -m unittest discover -s tests -q

# ---------------------------------------------------------------- 5. summary
P_MAIN=$(pdf_pages docs/paper/main.pdf); P_SUP=$(pdf_pages docs/paper/supplement.pdf)
P_REP=$(pdf_pages "docs/report/説明資料_PAI最終課題_${ACCOUNT}.pdf")
echo; echo "================ finalize_results summary ================"
for i in "${!NAMES[@]}"; do printf '%-28s %-5s %s\n' "${NAMES[$i]}" "${STATUS[$i]}" "${NOTES[$i]}"; done
echo "----"
echo "pages: paper main=$P_MAIN supplement=$P_SUP report=$P_REP"
echo "remaining TBD: $TBD_N ${TBD_LIST:+($TBD_LIST)}"
echo "test summary: $(tail -n 3 "$LOGDIR/unit_tests.log" 2>/dev/null | tr '\n' ' ')"
echo "---- git status --short"; git status --short
NFAIL=0; for s in "${STATUS[@]}"; do [ "$s" = FAIL ] && NFAIL=$((NFAIL+1)); done
echo "=========================================================="
echo "failed steps: $NFAIL   (logs: $LOGDIR)"
[ "$NFAIL" -eq 0 ]
