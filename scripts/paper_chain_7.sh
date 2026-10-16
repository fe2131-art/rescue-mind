#!/usr/bin/env bash
# Campaign F (registered, 48 trials) -> fire masks at logged poses -> T2 scoring (registered).
cd "$(dirname "$0")/.."
python3 scripts/run_campaign.py --protocol experiments/campaign_f_protocol.json \
  --ledger experiments/results/campaign_F_ledger.jsonl > experiments/results/campaign_F_stdout.log 2>&1
echo F_DONE
python3 scripts/fire_mask_at_pose.py --protocol experiments/campaign_f_protocol.json \
  --ledger experiments/results/campaign_F_ledger.jsonl > experiments/results/campaign_F_masks.log 2>&1
echo F_MASKS_DONE
bash scripts/t2_eval.sh > experiments/results/t2_eval_stdout.log 2>&1
echo CHAIN7_DONE
