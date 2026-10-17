#!/usr/bin/env bash
# Study X (closed loop, four-bay depot; DRAFT, experiments/PREREGISTRATION_X.md), full sequence.  Run from the MAIN checkout ONLY
# when no other campaign uses Gazebo / the GPU (it drives rm-next) and the depot assets are fetched (scripts/fetch_depot_assets.sh):
#   bash scripts/x_run.sh                 # everything;  X_PARTS="a m" runs the core 44 runs only (steer cell later: X_PARTS="s" --
#                                         note: run_campaign --only re-runs trials already in the ledger, so use each part once)
# (a) mechanics pilot on separate worlds (9 runs; STOPS unless scripts/x_analysis.py --pilot passes)
# (b) design masks of the 24 steer candidates -> registered selection of the 8 hard-class worlds -> protocol regenerated with it
# (c) design masks of the registered protocol, commit of selection + masks + pilot ledger (BEFORE the first X trial)
# (d) the campaign (80 runs; resumable: a finished trial is skipped)   (e) analysis -> experiments/results/x_summary.json
set -uo pipefail
cd "$(dirname "$0")/.."
RES=experiments/results
PROTO=experiments/campaign_x_protocol.json
PILOT=experiments/campaign_x_pilot_protocol.json
CAND=experiments/campaign_x_steer_candidates.json
IN_NEXT=(docker exec rm-next rescuemind-entrypoint)
mkdir -p "$RES"
[ -d worlds/assets/aws-wh ] || { echo "X_ABORT: depot assets missing (scripts/fetch_depot_assets.sh)"; exit 1; }

# (a) pilot
if [ ! -f "$RES/x_pilot_ok" ]; then
  python3 scripts/make_protocol_x.py --pilot || exit 1
  "${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol "$PILOT" --ledger "$RES/campaign_X_pilot_ledger.jsonl" 2>&1 | tail -20
  python3 scripts/x_analysis.py --pilot || { echo "X_ABORT: pilot did not behave as designed; X NOT started" >&2; exit 1; }
  touch "$RES/x_pilot_ok"
fi
echo "X_PILOT_OK"

# (b) steer selection from the candidates' design masks (no model score is used)
if [ ! -f experiments/campaign_x_steer_selection.json ]; then
  python3 scripts/make_protocol_x.py || exit 1
  "${IN_NEXT[@]}" python3 scripts/fire_mask_at_pose.py --protocol "$CAND" --design --design-sides 0.4 || { echo "X_ABORT: candidate masks" >&2; exit 1; }
  python3 scripts/make_protocol_x.py --select-steer experiments/campaign_x_steer_candidates_design_fire_masks.json || exit 1
fi
python3 scripts/make_protocol_x.py --force || exit 1          # protocol with the registered selection
echo "X_SELECTION_DONE"

# (c) design masks of the registered protocol, then commit everything that must exist before the first trial
[ -s experiments/campaign_x_protocol_design_fire_masks.json ] || \
  "${IN_NEXT[@]}" python3 scripts/fire_mask_at_pose.py --protocol "$PROTO" --design --design-sides 0.4 || { echo "X_ABORT: masks" >&2; exit 1; }
[ -s experiments/campaign_x_protocol_design_fire_masks.json ] || { echo "X_ABORT: design fire masks missing" >&2; exit 1; }
git add "$PROTO" experiments/campaign_x_steer_selection.json experiments/campaign_x_steer_candidates_design_fire_masks.json \
  experiments/campaign_x_protocol_design_fire_masks.json experiments/advice_X "$RES/campaign_X_pilot_ledger.jsonl"
git commit -q -m "study X: pilot ledger, steer selection, protocol and design fire masks (before the first X trial)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" -- "$PROTO" experiments/campaign_x_steer_selection.json \
  experiments/campaign_x_steer_candidates_design_fire_masks.json experiments/campaign_x_protocol_design_fire_masks.json experiments/advice_X \
  "$RES/campaign_X_pilot_ledger.jsonl" && git push -q || echo "X_NOTE: nothing new to commit or push" >&2
echo "X_MASKS_DONE"

# (d) campaign (quiet host first)
for i in $(seq 1 60); do awk '{exit !($1 < 6)}' /proc/loadavg && break; sleep 60; done
echo "X_LOAD_AT_START $(cut -d' ' -f1-3 /proc/loadavg)"
ONLY=()
if [ "${X_PARTS:-a m s}" != "a m s" ]; then
  mapfile -t ONLY < <(python3 - "$PROTO" "${X_PARTS}" <<'PY'
import json, sys
p = json.load(open(sys.argv[1])); keep = {'X-' + c for c in sys.argv[2].split()}
print('\n'.join(t['id'] for t in p['trials'] if t['cell'] in keep))
PY
)
fi
"${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol "$PROTO" --ledger "$RES/campaign_X_ledger.jsonl" ${ONLY:+--only "${ONLY[@]}"} \
  2>&1 | tee -a "$RES/campaign_X_stdout.log" | grep -E "^\[|trial|ERROR" | tail -5
[ "${PIPESTATUS[0]}" -eq 0 ] || { echo "X_ABORT: run_campaign.py failed (rerun resumes)" >&2; exit 1; }

# (e) analysis
python3 scripts/x_analysis.py > "$RES/x_analysis_stdout.log" || exit 1
echo "X_DONE"
