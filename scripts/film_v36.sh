#!/usr/bin/env bash
# v3.6 demo footage (final configuration = orchestrator defaults) for the submission video.
cd "$(dirname "$0")/.."
run() {  # tag scene instruction [extra...]
  local tag=$1 scene=$2 instr=$3; shift 3
  python3 scripts/v32_orchestrate.py --run --scenario live --scene "$scene" --film --capture-rosbag --instruction "$instr" "$@" >/dev/null 2>&1
  d=$(ls -td outputs/runs/*/ | head -1); echo "$tag $(basename $d) $(python3 -c "import json;print(json.load(open('${d}stack_result.json')).get('state'))")"
}
run deliver nominal '避難所Bで飲み水が足りないそうです'
run recover swapped '避難所Bに救急箱を届けてください'
run empty empty '避難所Bに飲料水をお願いします'
W03=$(python3 -c "import json;p=json.load(open('experiments/campaign_g_protocol.json'));print(json.dumps([t for t in p['trials'] if t['world']=='W03'][0]['world_spec']))")
run hidden_fire nominal 'Bの避難所に救急箱をお願い' --world-spec "$W03"
