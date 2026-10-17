#!/usr/bin/env bash
# After study R: J smoke test on a pilot world (VRAM fit of Clef-Flash + Qwen3.5-4B), then campaign H, then campaign J.
cd "$(dirname "$0")/.."
until grep -q R_DONE "$1" 2>/dev/null; do sleep 60; done
docker exec rm-dev rescuemind-entrypoint python3 scripts/r_analysis.py > experiments/results/r_analysis_stdout.log 2>&1
nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -l 1 > experiments/results/j_smoke_vram.csv &
VP=$!
SPEC=$(python3 -c "import json;print(json.dumps(json.load(open('experiments/campaign_h_pilot_protocol.json'))['trials'][0]['world_spec']))")
docker exec rm-next rescuemind-entrypoint python3 scripts/v32_orchestrate.py --run --scenario live --scene swapped --capture-rosbag \
  --instruction '避難所Bに飲料水を届けて' --world-spec "$SPEC" \
  --model Qwen/Qwen3.5-4B --hazard-prompt h35 --hazard-views full --jev-local clef --jev-schema task --jev-hazard-threshold 0.05 \
  > experiments/results/j_smoke_stdout.log 2>&1
kill $VP
d=$(ls -td outputs/runs/*/ | head -1); STATE=$(python3 -c "import json;print(json.load(open('${d}stack_result.json')).get('state'))")
echo "J_SMOKE $(basename $d) $STATE peak_MiB=$(sort -n experiments/results/j_smoke_vram.csv | tail -1)"
docker exec rm-next rescuemind-entrypoint python3 scripts/run_campaign.py --protocol experiments/campaign_h_protocol.json \
  --ledger experiments/results/campaign_H_ledger.jsonl > experiments/results/campaign_H_stdout.log 2>&1
echo H_DONE
if [ "$STATE" = "COMPLETED" ]; then
  nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -l 1 | sed '1i memory_used_mib' > experiments/results/campaign_J_vram.csv &
  VP=$!
  docker exec rm-next rescuemind-entrypoint python3 scripts/run_campaign.py --protocol experiments/campaign_j_protocol.json \
    --ledger experiments/results/campaign_J_ledger.jsonl > experiments/results/campaign_J_stdout.log 2>&1
  kill $VP; echo J_DONE
else
  echo J_SKIPPED_SMOKE_FAILED
fi
