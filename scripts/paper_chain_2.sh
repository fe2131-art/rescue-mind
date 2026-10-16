#!/usr/bin/env bash
# I-10 pilot re-run (hazard threshold 0.05), then T1 fire masks + relabel (amendment 2).
cd "$(dirname "$0")/.."
python3 scripts/run_campaign.py --protocol experiments/campaign_e_pilot_protocol.json \
  --ledger experiments/results/campaign_E_pilot2_ledger.jsonl -- --model Qwen/Qwen3.5-9B --prompt-set v35 \
  --intent-backend llm --intent-prompt i35 --recovery --explain --hazard-threshold 0.05 > experiments/results/campaign_E_pilot2_stdout.log 2>&1
python3 scripts/build_testset_t1.py --fire-masks > experiments/results/t1_masks.log 2>&1
python3 scripts/build_testset_t1.py --relabel >> experiments/results/t1_masks.log 2>&1
echo CHAIN2_DONE
