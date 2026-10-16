#!/usr/bin/env bash
# I-12: interleaved A/B/C of DDS publication settings on the control topics (motion-check, no VLM).
# Not an evaluation of the AI; measures blocking publish() calls and request gaps seen by the guard.
cd "$(dirname "$0")/.."
for i in $(seq 1 ${PROBE_N:-10}); do
  for mode in default async best_effort; do
    python3 scripts/v32_orchestrate.py --run --scenario motion-check --scene nominal --dds-mode $mode >/dev/null 2>&1
    d=$(ls -td outputs/runs/*/ | head -1)
    python3 - "$d" "$mode" <<'PY'
import json,sys
d,mode=sys.argv[1],sys.argv[2]
r=json.load(open(d+'stack_result.json'))
try: m=json.load(open(d+'mission.json'))
except Exception: m={'events':[]}
ev=m.get('events',[])
guard=[l.split('relay state: ')[-1].strip() for l in open(d+'velocity_guard.log') if 'relay state' in l]
print(json.dumps({'mode':mode,'run':r['run_id'],'state':r['state'],
  'slow_publish':[e['dur_s'] for e in ev if e.get('stage')=='slow_publish'],
  'request_gaps':[e['gap_s'] for e in ev if e.get('stage')=='request_gap'],
  'max_gap':m.get('max_request_gap_s'),
  'guard_stale':sum(s.startswith('stale') for s in guard),'error':(r.get('error') or '')[:80]}),flush=True)
PY
  done
done
