#!/usr/bin/env bash
# One idempotent pipeline to run AFTER the campaigns have finished: regenerates every derived artefact in order.
#
#   bash scripts/finalize_results.sh                 # normal run
#   ALLOW_PARTIAL=1 bash scripts/finalize_results.sh # analyse campaign H even if its ledger has < planned_n final rows
#   ACCOUNT=name bash scripts/finalize_results.sh    # report account (default tetsutetsu)
#
# 1 analyses H J V(+figure) L W Q A S XD X (each gated per study on COMPLETE inputs: planned_n final ledger rows / all
#   devset files covering their image set, via scripts/finalize_gate.py; else it prints SKIP with the reason), derived models
# 2 paper numbers (pending mode, never FINAL) + figures + graphical abstract + PDFs + pending-macro list
# 3 report / README / YouTube text   4 test count + full unit-test suite in rm-dev
# 5 cross-document consistency check (scripts/check_consistency.py; a mismatch is a FAILED step, the run continues)
# 6 summary table with the remaining pending macros; exit code != 0 iff some non-SKIP step FAILED.  Nothing is committed.
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
unset FINAL   # finalize always builds in pending mode; FINAL=1 is a separate, deliberate submission build

# gate ARGS... : run scripts/finalize_gate.py -> GATE_OK (0/1) and GATE_NOTE (count or SKIP reason)
gate() { local r; r=$(python3 scripts/finalize_gate.py "$@"); GATE_OK=0; GATE_NOTE=${r#* }; [ "${r%% *}" = OK ] && GATE_OK=1; return 0; }
# gated NAME CMD... : run the step if the last gate() passed, else SKIP with its reason
gated() { local n=$1; shift; if [ "$GATE_OK" = 1 ]; then step "$n" "$@"; else skip "$n" "$GATE_NOTE"; fi; }

record() { NAMES+=("$1"); STATUS+=("$2"); NOTES+=("${3:-}"); printf '[%-4s] %-28s %s\n' "$2" "$1" "${3:-}"; }
skip()   { record "$1" SKIP "$2"; }
# step NAME CMD... : run, capture output to $LOGDIR/NAME.log, record OK/FAIL (tail of the log is shown on failure)
step() {
  local name=$1; shift
  echo ">>> $name: $*"
  if "$@" >"$LOGDIR/$name.log" 2>&1; then record "$name" OK
  else local rc=$?; tail -n 15 "$LOGDIR/$name.log" | sed 's/^/    | /'; record "$name" FAIL "rc=$rc, log $LOGDIR/$name.log"; fi
}
last_ok_name() { local i; for i in "${!NAMES[@]}"; do [ "${NAMES[$i]}" = "$1" ] && [ "${STATUS[$i]}" = OK ] && return 0; done; return 1; }
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
gate ledger "$HL" experiments/campaign_h_protocol.json
[ "$GATE_OK" = 1 ] || echo "WARNING: campaign H: $GATE_NOTE" >&2
gated h_analysis python3 scripts/h_analysis.py; last_ok && [ "$GATE_OK" = 1 ] && H_OK=1
if [ "$H_OK" = 1 ]; then step h_change_rate_model python3 scripts/h_change_rate_model.py; step h_k_scaling python3 scripts/h_k_scaling.py
else skip h_change_rate_model "h_analysis did not run/succeed"; skip h_k_scaling "h_analysis did not run/succeed"; fi

gate ledger $RES/campaign_J_ledger.jsonl experiments/campaign_j_protocol.json $RES/campaign_J_vram.csv
gated j_analysis python3 scripts/j_analysis.py

# V: closed-loop memory study (registered predictions + design fire masks are inputs) and its prediction-vs-observation figure
gate ledger $RES/campaign_V_ledger.jsonl experiments/campaign_v_protocol.json $RES/v_predictions.json experiments/campaign_v_protocol_design_fire_masks.json
gated v_analysis python3 scripts/v_analysis.py
if [ -f scripts/make_v_figure.py ] && last_ok_name v_analysis; then step make_v_figure "${IN_RMDEV[@]}" python3 scripts/make_v_figure.py
else skip make_v_figure "v_analysis did not run/succeed (committed predictions-only figure kept)"; fi

gate ledger $RES/campaign_L_ledger.jsonl experiments/campaign_l_protocol.json experiments/campaign_l_protocol_design_fire_masks.json
gated l_analysis python3 scripts/l_analysis.py

# W: image-level look-around / adaptive extra views / scrutiny policies / oracle steering (all inside w_analysis.py) + prior-art baselines
W_MISS=""; for f in devset_t1_i11_h36_tiles devset_t1_i11_h36_full devset_t2_i11_h36_tiles devset_t2_i11_h36_full devset_w_para_dh devset_w_para_dh2 devset_w_para_t1 devset_w_para_t2; do [ -f $RES/$f.json ] || W_MISS="$W_MISS $f"; done
if [ ! -f scripts/w_analysis.py ]; then GATE_OK=0; GATE_NOTE="scripts/w_analysis.py missing"
elif [ -n "$W_MISS" ]; then GATE_OK=0; GATE_NOTE="study W incomplete (missing:$W_MISS)"
else gate devsets experiments/vlm_testset_w/labels.jsonl w_h36_tiles; fi
gated w_analysis python3 scripts/w_analysis.py

# Q: real-photo supply check; merges at its own chain, so only when its script, registration, sample and all score rows exist
gate q
gated q_analysis python3 scripts/q_analysis.py

# A: advice study incl. A-steer (adaptive attacker); S: sign/text attacks (all five devset configurations); XD: depot image eps; X: depot closed loop
gate ledger $RES/campaign_A_ledger.jsonl experiments/campaign_a_protocol.json experiments/campaign_a_protocol_design_fire_masks.json
gated a_analysis python3 scripts/a_analysis.py
gate devsets experiments/vlm_testset_s/labels.jsonl s_h36_tiles s_h36_full s_json s_ocrmask_h36_tiles s_ign_h36_tiles
gated s_analysis python3 scripts/s_analysis.py
gate devsets experiments/vlm_testset_xd/labels.jsonl xd_h36_tiles
gated xd_analysis python3 scripts/xd_analysis.py
gate ledger $RES/campaign_X_ledger.jsonl experiments/campaign_x_protocol.json experiments/campaign_x_protocol_design_fire_masks.json
gated x_analysis python3 scripts/x_analysis.py

if [ -f $RES/p2_scores_h36.jsonl ] && [ -f $RES/p2_scores_h35.jsonl ]; then
  step p2_calibration python3 scripts/p2_calibration.py --analyse   # checks 400+400 rows per wording itself
else skip p2_calibration "need p2_scores_h36.jsonl and p2_scores_h35.jsonl"; fi

step r_analysis "${IN_RMDEV[@]}" python3 scripts/r_analysis.py

# I-19 advice: descriptive consistency/robustness curve (needs the measured per-check rates) and the injection-eval summary (live VLM; never run here)
if [ -f $RES/h_change_rate.json ]; then step advice_curve python3 scripts/advice_curve.py
else skip advice_curve "need h_change_rate.json (h_change_rate_model)"; fi
if [ -f $RES/advice_injection_eval.json ]; then
  step advice_injection_summary python3 -c "import json;d=json.load(open('$RES/advice_injection_eval.json'));print({k:v for k,v in d.items() if not isinstance(v,(list,dict))});print(sorted(k for k,v in d.items() if isinstance(v,(list,dict)))[:30])"
else skip advice_injection_summary "no advice_injection_eval.json (scripts/advice_injection_eval.py needs the live VLM server; --oracle gives the by-construction numbers)"; fi

step count_tests "${IN_RMDEV[@]}" python3 scripts/count_tests.py

# ---------------------------------------------------------------- 2. paper (pending mode: unfinished results print a grey "(pending)")
step paper_numbers python3 scripts/paper_numbers.py
step make_paper_figures "${IN_RMDEV[@]}" python3 scripts/make_paper_figures.py
step graphical_abstract "${IN_RMDEV[@]}" python3 scripts/make_graphical_abstract.py   # H/J numbers appear in the abstract automatically
step build_paper bash scripts/build_paper.sh
TBD_LIST=""
{ # report mode: never fatal.  Same criterion as `paper_numbers.py --final` (pending macros + pending tables).
  TBD_LIST=$( { grep -h '^.newcommand.*{.TBD}' docs/paper/numbers.tex 2>/dev/null | sed -E 's/^\\newcommand\{\\([A-Za-z]+)\}.*/\1/'
                grep -l '\\TBD' docs/paper/tab_*.tex 2>/dev/null | xargs -r -n1 basename; } | sort -u | paste -sd' ' - )
}
TBD_N=$(echo "$TBD_LIST" | wc -w)
echo "pending (TBD) macros/tables: $TBD_N"; [ "$TBD_N" -gt 0 ] && echo "  $TBD_LIST" | fold -s -w 150

# ---------------------------------------------------------------- 3. report / README / YouTube
step make_report "${IN_RMDEV[@]}" python3 scripts/make_report.py --account "$ACCOUNT"
step update_readme_results python3 scripts/update_readme_results.py
step make_youtube_description python3 scripts/make_youtube_description.py

# ---------------------------------------------------------------- 4. tests, then the cross-document consistency check (a mismatch is a FAILED step; the run continues)
step unit_tests "${IN_RMDEV[@]}" python3 -m unittest discover -s tests -q
step check_consistency python3 scripts/check_consistency.py

# ---------------------------------------------------------------- 6. summary
P_MAIN=$(pdf_pages docs/paper/main.pdf); P_SUP=$(pdf_pages docs/paper/supplement.pdf)
P_REP=$(pdf_pages "docs/report/説明資料_PAI最終課題_${ACCOUNT}.pdf")
echo; echo "================ finalize_results summary ================"
for i in "${!NAMES[@]}"; do printf '%-28s %-5s %s\n' "${NAMES[$i]}" "${STATUS[$i]}" "${NOTES[$i]}"; done
echo "----"
echo "pages: paper main=$P_MAIN supplement=$P_SUP report=$P_REP"
echo "remaining pending macros/tables: $TBD_N"; [ "$TBD_N" -gt 0 ] && echo "$TBD_LIST" | fold -s -w 150 | sed "s/^/  /"
echo "test summary: $(tail -n 3 "$LOGDIR/unit_tests.log" 2>/dev/null | tr '\n' ' ')"
echo "---- git status --short"; git status --short
NFAIL=0; for s in "${STATUS[@]}"; do [ "$s" = FAIL ] && NFAIL=$((NFAIL+1)); done
echo "=========================================================="
echo "failed steps: $NFAIL   (logs: $LOGDIR)"
[ "$NFAIL" -eq 0 ]
