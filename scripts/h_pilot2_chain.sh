#!/usr/bin/env bash
# I-15 pilot round 2 (after the observed-supply fix): relocation route + naive skip, then resume study R.
cd "$(dirname "$0")/.."
n0=$(grep -c saved experiments/results/r_eval_stdout.log)
until [ "$(grep -c saved experiments/results/r_eval_stdout.log)" -gt "$n0" ]; do sleep 20; done
docker exec rm-next bash scripts/stop_r.sh; sleep 5
while curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1; do sleep 2; done
docker exec rm-next rescuemind-entrypoint python3 scripts/run_campaign.py --protocol experiments/campaign_h_pilot_protocol.json \
  --ledger experiments/results/campaign_H_pilot2_ledger.jsonl --only HP02 HP03 > experiments/results/campaign_H_pilot2_stdout.log 2>&1
echo PILOT2_DONE
docker exec rm-next rescuemind-entrypoint bash scripts/r_eval.sh >> experiments/results/r_eval_stdout.log 2>&1
echo R_DONE
