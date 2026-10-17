#!/usr/bin/env bash
# Study L, full sequence (experiments/PREREGISTRATION_L.md).  Run from the MAIN checkout, ONLY when no other campaign uses
# Gazebo / the GPU (it drives rm-next):
#   bash scripts/l_run.sh
# (a) design fire masks (front + two side poses 0.4 m)   (b) smoke ledger; STOPS unless every smoke run completed
# (c) the registered campaign                             (d) analysis -> experiments/results/l_summary.json
set -uo pipefail
cd "$(dirname "$0")/.."
RES=experiments/results
PROTO=experiments/campaign_l_protocol.json
SMOKE_LEDGER=$RES/campaign_L_smoke_ledger.jsonl
IN_NEXT=(docker exec rm-next rescuemind-entrypoint)
mkdir -p "$RES"

# (a) design fire masks
"${IN_NEXT[@]}" python3 scripts/fire_mask_at_pose.py --protocol "$PROTO" --design --design-sides 0.4 || { echo "L_ABORT: fire mask rendering failed" >&2; exit 1; }
[ -s experiments/campaign_l_protocol_design_fire_masks.json ] || { echo "L_ABORT: design fire masks file missing" >&2; exit 1; }
echo "L_MASKS_DONE"

# (b) smoke
"${IN_NEXT[@]}" bash scripts/l_smoke.sh || { echo "L_ABORT: l_smoke.sh failed" >&2; exit 1; }
python3 - "$SMOKE_LEDGER" <<'PY' || { echo "L_ABORT: smoke runs did not all complete; campaign L NOT started. Fix the wiring first (see the ledger above)." >&2; exit 1; }
import json, sys
OK = ('COMPLETED', 'COMPLETED_EXPECTED_DENIAL')
last = {}
try:
    for line in open(sys.argv[1]):
        if line.strip():
            r = json.loads(line); last[r['trial_id']] = r      # latest attempt per smoke trial
except FileNotFoundError:
    pass
bad = {k: r.get('state') for k, r in last.items() if r.get('state') not in OK}
if not last or bad:
    print('smoke not OK:', bad if last else 'ledger empty or missing', file=sys.stderr); sys.exit(1)
print(f'smoke: {len(last)} runs, all in {OK}')
PY
echo "L_SMOKE_OK"

# (c) campaign
"${IN_NEXT[@]}" python3 scripts/run_campaign.py --protocol "$PROTO" --ledger "$RES/campaign_L_ledger.jsonl" \
  2>&1 | tee -a "$RES/campaign_L_stdout.log"
[ "${PIPESTATUS[0]}" -eq 0 ] || { echo "L_ABORT: run_campaign.py failed (rerun resumes if the ledger is kept)" >&2; exit 1; }

# (d) analysis (stdlib; host python3)
python3 scripts/l_analysis.py || exit 1
echo "L_DONE"
