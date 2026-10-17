#!/usr/bin/env bash
# Study V, full sequence (experiments/PREREGISTRATION_V.md).  Run from the main checkout ONLY when no other campaign uses
# Gazebo / the GPU (it drives rm-next):   bash scripts/v_run.sh
# (a) mechanics pilot (separate worlds), STOPS unless every pilot run ends as designed
# (b) design fire masks (front + two side poses 0.4 m)
# (c) model predictions for the drawn sequences -> committed and pushed BEFORE the first V trial
# (d) the registered campaign   (e) analysis -> experiments/results/v_summary.json
set -uo pipefail
cd "$(dirname "$0")/.."
RES=experiments/results
PROTO=experiments/campaign_v_protocol.json
IN_NEXT=(docker exec rm-next rescuemind-entrypoint)

# (a) pilot
if [ ! -f "$RES/v_pilot_ok" ]; then
  "${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol experiments/campaign_v_pilot_protocol.json \
    --ledger "$RES/campaign_V_pilot_ledger.jsonl" 2>&1 | tail -20
  python3 - "$RES/campaign_V_pilot_ledger.jsonl" <<'PY' || { echo "V_ABORT: pilot did not behave as designed; V NOT started" >&2; exit 1; }
import json, sys
want = {'VP01': ('COMPLETED',), 'VP02': ('COMPLETED_EXPECTED_DENIAL',), 'VP03': ('COMPLETED_EXPECTED_DENIAL',),
        'VP04': ('COMPLETED_MEMORY_TRUSTED',)}
last = {}
for line in open(sys.argv[1]):
    if line.strip():
        r = json.loads(line); last[r['trial_id']] = r
for k, ok in want.items():
    r = last.get(k, {})
    print(k, r.get('state'), r.get('observed_action'), r.get('final_station'), r.get('mission_time_s'))
bad = [k for k, ok in want.items() if last.get(k, {}).get('state') not in ok]
sys.exit(1 if bad else 0)
PY
  touch "$RES/v_pilot_ok"
fi
echo "V_PILOT_OK"

# (b) design fire masks
[ -s experiments/campaign_v_protocol_design_fire_masks.json ] || \
  "${IN_NEXT[@]}" python3 scripts/fire_mask_at_pose.py --protocol "$PROTO" --design --design-sides 0.4 || { echo "V_ABORT: masks" >&2; exit 1; }
[ -s experiments/campaign_v_protocol_design_fire_masks.json ] || { echo "V_ABORT: design fire masks missing" >&2; exit 1; }
echo "V_MASKS_DONE"

# (c) registered predictions, committed before the first trial
if [ ! -s "$RES/v_predictions.json" ]; then
  nice -n 10 python3 scripts/v_predict.py > /dev/null || { echo "V_ABORT: v_predict failed" >&2; exit 1; }
  git add "$RES/v_predictions.json" experiments/campaign_v_protocol_design_fire_masks.json "$RES/campaign_V_pilot_ledger.jsonl"
  git commit -q -m "study V: registered model predictions and design fire masks (before the first V trial)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- "$RES/v_predictions.json" experiments/campaign_v_protocol_design_fire_masks.json "$RES/campaign_V_pilot_ledger.jsonl" \
    && git push -q || { echo "V_ABORT: could not commit/push the predictions" >&2; exit 1; }
fi
git merge-base --is-ancestor "$(git log -1 --format=%H -- "$RES/v_predictions.json")" HEAD || { echo "V_ABORT: predictions not committed" >&2; exit 1; }
echo "V_PREDICTIONS_COMMITTED"

# (d) campaign
"${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol "$PROTO" --ledger "$RES/campaign_V_ledger.jsonl" \
  2>&1 | tee -a "$RES/campaign_V_stdout.log" | grep -E "^\[|trial|ERROR" | tail -5
[ "${PIPESTATUS[0]}" -eq 0 ] || { echo "V_ABORT: run_campaign.py failed (rerun resumes)" >&2; exit 1; }

# (e) analysis
python3 scripts/v_analysis.py > "$RES/v_analysis_stdout.log" || exit 1
echo "V_DONE"
