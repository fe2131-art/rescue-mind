#!/usr/bin/env bash
# I-09: repeated live runs with request-gap instrumentation (not an evaluation).
cd "$(dirname "$0")/.."
V34="--model Qwen/Qwen3.5-9B --prompt-set v35 --intent-backend llm --intent-prompt i35 --recovery --explain"
for i in $(seq 1 ${PROBE_N:-10}); do
  scene=$([ $((i % 3)) -eq 0 ] && echo empty || ([ $((i % 3)) -eq 1 ] && echo nominal || echo swapped))
  python3 scripts/v32_orchestrate.py --run --scenario live --scene $scene $V34 --instruction '避難所Bに飲料水をお願いします' >/dev/null 2>&1
  d=$(ls -td outputs/runs/*/ | head -1)
  python3 - "$d" "$scene" <<'PY'
import json,sys,re
d,scene=sys.argv[1],sys.argv[2]
r=json.load(open(d+'stack_result.json')); m=json.load(open(d+'mission.json'))
gaps=[(e['phase'],e['gap_s'],e['t_wall_s']) for e in m['events'] if e.get('stage')=='request_gap']
gcs=[(e['generation'],e['pause_s'],e['t_wall_s']) for e in m['events'] if e.get('stage')=='gc_pause']
slow=[(e['stage'],e['dur_s'],e['t_wall_s']) for e in m['events'] if e.get('stage') in ('slow_spin','slow_publish')]
latch=[l.strip()[-120:] for l in open(d+'velocity_guard.log') if 'stale request latch' in l]
print(json.dumps({'run':r['run_id'],'scene':scene,'state':r['state'],'max_gap':m.get('max_request_gap_s'),'gaps':gaps,'gc':gcs,'slow':slow,'frozen':m.get('gc_frozen_objects'),'guard':latch},ensure_ascii=False),flush=True)
PY
done
