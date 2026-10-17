#!/usr/bin/env bash
# Memory demo footage (I-15): mission 1 (swapped, no memory use, memory written), mission 2 (swapped again, verified memory).
cd "$(dirname "$0")/.."
M=experiments/results/memory_film/film_mem.jsonl
mkdir -p "$(dirname $M)"; rm -f "$M"
SPEC=$(python3 -c "import json;print(json.dumps(json.load(open('experiments/campaign_h_pilot_protocol.json'))['trials'][0]['world_spec']))")
run() {  # tag mode
  python3 scripts/v32_orchestrate.py --run --scenario live --scene swapped --film --capture-rosbag --world-spec "$SPEC" \
    --instruction '避難所Bに飲料水を届けて' --memory-file "$PWD/$M" --memory-mode "$2" >/dev/null 2>&1
  d=$(ls -td outputs/runs/*/ | head -1); echo "$1 $(basename $d) $(python3 -c "import json;print(json.load(open('${d}stack_result.json')).get('state'))")"
}
run mem_seed off
run mem_verified verified
