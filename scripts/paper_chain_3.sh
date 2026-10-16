#!/usr/bin/env bash
# T1 primary model -> campaign E (registered) -> remaining T1 models / methods. One GPU job at a time.
cd "$(dirname "$0")/.."
export T1_ONLY=t1_qwen35_9b
bash scripts/t1_eval_all.sh > experiments/results/t1_eval_stdout.log 2>&1
python3 scripts/t1_analysis.py > experiments/results/t1_analysis_stdout.log 2>&1
echo T1_PRIMARY_DONE
python3 scripts/run_campaign.py --protocol experiments/campaign_e_protocol.json \
  --ledger experiments/results/campaign_E_ledger.jsonl -- --model Qwen/Qwen3.5-9B --prompt-set v35 \
  --intent-backend llm --intent-prompt i35 --recovery --explain --hazard-threshold 0.05 > experiments/results/campaign_E_stdout.log 2>&1
echo E_DONE
unset T1_ONLY
bash scripts/t1_eval_all.sh >> experiments/results/t1_eval_stdout.log 2>&1
python3 scripts/t1_analysis.py > experiments/results/t1_analysis_stdout.log 2>&1
echo CHAIN3_DONE
