#!/usr/bin/env bash
# Pause study R after its current condition, run the I-15 mechanics pilot (dev worlds), then resume R.
cd "$(dirname "$0")/.."
until [ "$(grep -c saved experiments/results/r_eval_stdout.log)" -ge 2 ]; do sleep 20; done
docker exec rm-next bash scripts/stop_r.sh; sleep 5
while curl -s -m 2 http://127.0.0.1:8765/health >/dev/null 2>&1; do sleep 2; done
docker exec rm-next rescuemind-entrypoint python3 scripts/run_campaign.py --protocol experiments/campaign_h_pilot_protocol.json \
  --ledger experiments/results/campaign_H_pilot_ledger.jsonl > experiments/results/campaign_H_pilot_stdout.log 2>&1
echo PILOT_DONE
docker exec rm-next rescuemind-entrypoint bash scripts/r_eval.sh >> experiments/results/r_eval_stdout.log 2>&1
echo R_DONE
