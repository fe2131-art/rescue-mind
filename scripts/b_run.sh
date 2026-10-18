#!/usr/bin/env bash
# Study B (I-24: advice credit in the closed loop), full run (experiments/PREREGISTRATION_B.md).  Run from the main checkout
# ONLY when no other campaign uses Gazebo / the GPU (it drives rm-next):   bash scripts/b_run.sh
# (0) registration gate: the prereg (status REGISTERED), both protocols and every advice file are committed and unchanged
# (a) mechanics pilot: 1 liar sequence of 3 missions, 6 runs, separate seeds; STOPS unless every run behaves as registered
#     (first station, wasted visits, throttling, audits, settlements = offline recomputation)
# (b) the registered campaign (48 runs: 3 liar + 1 honest sequence x 6 missions x 2 arms)
# (c) analysis -> experiments/results/b_summary.json
# Prints B_DONE at the end, B_ABORT on any failure.  Re-running resumes (finished trials are skipped; the per-(sequence, arm)
# credit ledgers persist in experiments/results/credit_B/).
set -uo pipefail
cd "$(dirname "$0")/.."
RES=experiments/results
PROTO=experiments/campaign_b_protocol.json
PILOT=experiments/campaign_b_pilot_protocol.json
PREREG=experiments/PREREGISTRATION_B.md
IN_NEXT=(docker exec rm-next rescuemind-entrypoint)
abort() { echo "B_ABORT: $*" >&2; exit 1; }

# (0) registration gate
FILES=("$PREREG" "$PROTO" "$PILOT" scripts/make_protocol_b.py scripts/b_analysis.py)
while IFS= read -r f; do FILES+=("$f"); done < <(python3 - "$PROTO" "$PILOT" <<'PY'
import json, sys
for p in sys.argv[1:]:
    print(*json.load(open(p))['advice_files'], sep='\n')
PY
)
[ "${#FILES[@]}" -gt 5 ] || abort "no advice files listed in the protocols"
for f in "${FILES[@]}"; do
  git ls-files --error-unmatch "$f" >/dev/null 2>&1 || abort "$f is not committed"
  git diff --quiet HEAD -- "$f" || abort "$f differs from the committed version"
done
grep -q '^Status: REGISTERED' "$PREREG" || abort "$PREREG is not marked 'Status: REGISTERED'"
python3 scripts/make_protocol_b.py >/dev/null && python3 scripts/make_protocol_b.py --pilot >/dev/null || abort "the generator no longer reproduces the registered protocol"
git diff --quiet HEAD -- "$PROTO" "$PILOT" experiments/advice_B experiments/advice_B_pilot || abort "regenerated protocol or advice files differ"
echo "B_REGISTERED $(git log -1 --format=%h -- "$PREREG")"

"${IN_NEXT[@]}" true >/dev/null 2>&1 || abort "the container rm-next is not running"
# the stack starts its own VLM server on 8765: a leftover one would fail every trial at once and fill the ledger with FAILED rows
for _ in $(seq 1 60); do curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1 || break; sleep 10; done
if curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1; then abort "port 8765 is in use (another VLM server is running)"; fi
python3 scripts/ledger_stack_check.py --protocol "$PILOT" --ledger "$RES/campaign_B_pilot_ledger.jsonl" || abort "stale pilot ledger (see above)"
BLEDGER="$RES/campaign_B_ledger.jsonl"
python3 scripts/ledger_stack_check.py --protocol "$PROTO" --ledger "$BLEDGER" || abort "stale campaign ledger (see above)"

# (a) pilot
if [ ! -f "$RES/b_pilot_ok" ]; then
  for i in $(seq 1 60); do awk '{exit !($1 < 6)}' /proc/loadavg && break; sleep 60; done   # quiet host
  "${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol "$PILOT" --ledger "$RES/campaign_B_pilot_ledger.jsonl" 2>&1 | tail -20
  python3 scripts/b_analysis.py --pilot || abort "pilot did not behave as registered; B NOT started"
  touch "$RES/b_pilot_ok"
  git add "$RES/campaign_B_pilot_ledger.jsonl" "$RES"/credit_B_pilot/*.json 2>/dev/null
  git commit -q -m "I-24 study B: pilot ledger (before the first B trial)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- "$RES/campaign_B_pilot_ledger.jsonl" "$RES"/credit_B_pilot/*.json 2>/dev/null \
    && git push -q || echo "B_NOTE: nothing new to commit or push for the pilot" >&2
fi
echo "B_PILOT_OK"

# (b) campaign
for i in $(seq 1 60); do awk '{exit !($1 < 6)}' /proc/loadavg && break; sleep 60; done
echo "B_LOAD_AT_START $(cut -d' ' -f1-3 /proc/loadavg)"
"${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol "$PROTO" --ledger "$RES/campaign_B_ledger.jsonl" \
  2>&1 | tee -a "$RES/campaign_B_stdout.log" | grep -E "^\[|trial|ERROR" | tail -5
[ "${PIPESTATUS[0]}" -eq 0 ] || abort "run_campaign.py failed (rerun resumes)"

# (c) analysis
python3 scripts/b_analysis.py > "$RES/b_analysis_stdout.log" || abort "analysis failed"
echo "B_DONE"
