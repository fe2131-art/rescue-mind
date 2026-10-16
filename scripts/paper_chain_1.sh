#!/usr/bin/env bash
# Render T1, then run the campaign-E mechanics pilot (sequential: one Gazebo at a time).
cd "$(dirname "$0")/.."
python3 scripts/build_testset_t1.py > experiments/results/t1_render.log 2>&1
python3 scripts/run_campaign.py --protocol experiments/campaign_e_pilot_protocol.json \
  --ledger experiments/results/campaign_E_pilot_ledger.jsonl -- --model Qwen/Qwen3.5-9B --prompt-set v35 \
  --intent-backend llm --intent-prompt i35 --recovery --explain > experiments/results/campaign_E_pilot_stdout.log 2>&1
echo CHAIN_DONE
