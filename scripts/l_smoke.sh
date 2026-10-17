#!/usr/bin/env bash
# Study L development smoke test (experiments/PREREGISTRATION_L.md): 3 sampled layouts that are NOT part of L
# (seed 'L-smoke': one nominal, one swapped, one empty) driven with the full stack, to verify the wiring.
# Run INSIDE the stack container (same as the campaigns), only when no registered campaign is using the GPU/Gazebo:
#   docker exec rm-next rescuemind-entrypoint bash scripts/l_smoke.sh
set -uo pipefail
cd "$(dirname "$0")/.."
PROTO=experiments/campaign_l_smoke_protocol.json
LEDGER=experiments/results/campaign_L_smoke_ledger.jsonl
python3 scripts/make_protocol_l.py --smoke || exit 1
mkdir -p experiments/results
python3 scripts/run_campaign.py --protocol "$PROTO" --ledger "$LEDGER" 2>&1 | tee -a experiments/results/campaign_L_smoke_stdout.log
echo "L_SMOKE_DONE (ledger: $LEDGER)"
