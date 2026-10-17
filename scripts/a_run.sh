#!/usr/bin/env bash
# Study A (I-19), full sequence (experiments/PREREGISTRATION_A.md).  Run from the main checkout ONLY when no other campaign
# uses Gazebo / the GPU (it drives rm-next):   bash scripts/a_run.sh
# (a) mechanics pilot (separate worlds, 27 runs: 24 + 3 A-steer arms), STOPS unless every file-channel run ends as designed and the operator
#     channel extracts the intended advice in >= 9 of 12 runs
# (b) design fire masks (front + two side poses 0.4 m) for the F and A-steer (D) worlds, (c) the registered campaign (226 runs:
#     162 + 64 A-steer),
# (d) analysis -> experiments/results/a_summary.json
set -uo pipefail
cd "$(dirname "$0")/.."
RES=experiments/results
PROTO=experiments/campaign_a_protocol.json
PILOT=experiments/campaign_a_pilot_protocol.json
IN_NEXT=(docker exec rm-next rescuemind-entrypoint)

# (a) pilot
if [ ! -f "$RES/a_pilot_ok" ]; then
  "${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol "$PILOT" --ledger "$RES/campaign_A_pilot_ledger.jsonl" 2>&1 | tail -20
  python3 scripts/a_analysis.py --pilot || { echo "A_ABORT: pilot did not behave as designed; A NOT started" >&2; exit 1; }
  touch "$RES/a_pilot_ok"
fi
echo "A_PILOT_OK"

# (b) design fire masks
[ -s experiments/campaign_a_protocol_design_fire_masks.json ] || \
  "${IN_NEXT[@]}" python3 scripts/fire_mask_at_pose.py --protocol "$PROTO" --design --design-sides 0.4 || { echo "A_ABORT: masks" >&2; exit 1; }
[ -s experiments/campaign_a_protocol_design_fire_masks.json ] || { echo "A_ABORT: design fire masks missing" >&2; exit 1; }
git add experiments/campaign_a_protocol_design_fire_masks.json "$RES/campaign_A_pilot_ledger.jsonl"
git commit -q -m "study A: pilot ledger and design fire masks (before the first A trial)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- experiments/campaign_a_protocol_design_fire_masks.json "$RES/campaign_A_pilot_ledger.jsonl" \
  && git push -q || echo "A_NOTE: nothing new to commit or push for the masks" >&2
echo "A_MASKS_DONE"

# (c0) registration gate: the prereg, the protocol and the frozen advice prompts must be committed and unchanged
for f in experiments/PREREGISTRATION_A.md "$PROTO" experiments/advice_prompts_frozen.json; do
  git ls-files --error-unmatch "$f" >/dev/null 2>&1 || { echo "A_ABORT: $f is not committed" >&2; exit 1; }
  git diff --quiet HEAD -- "$f" || { echo "A_ABORT: $f differs from the committed version" >&2; exit 1; }
done
echo "A_REGISTERED $(git log -1 --format=%h -- experiments/PREREGISTRATION_A.md)"

# (c) campaign
for i in $(seq 1 60); do awk '{exit !($1 < 6)}' /proc/loadavg && break; sleep 60; done   # quiet host
echo "A_LOAD_AT_START $(cut -d' ' -f1-3 /proc/loadavg)"
"${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol "$PROTO" --ledger "$RES/campaign_A_ledger.jsonl" \
  2>&1 | tee -a "$RES/campaign_A_stdout.log" | grep -E "^\[|trial|ERROR" | tail -5
[ "${PIPESTATUS[0]}" -eq 0 ] || { echo "A_ABORT: run_campaign.py failed (rerun resumes)" >&2; exit 1; }

# (d) analysis
python3 scripts/a_analysis.py > "$RES/a_analysis_stdout.log" || exit 1
echo "A_DONE"
