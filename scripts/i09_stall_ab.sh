#!/usr/bin/env bash
# I-09 A/B: inject a 0.6 s planner stall while stationary; legacy guard vs v3.4 guard.
cd "$(dirname "$0")/.."
for mode in legacy new legacy new; do
  if [ $mode = legacy ]; then export RESCUEMIND_GUARD_ARGS=--legacy-latch-zero; else export RESCUEMIND_GUARD_ARGS=; fi
  python3 scripts/v32_orchestrate.py --run --scenario motion-check --scene nominal --inject-warmup-stall 0.6 >/dev/null 2>&1
  d=$(ls -td outputs/runs/*/ | head -1)
  python3 - "$d" "$mode" <<'PY'
import json,sys
d,mode=sys.argv[1],sys.argv[2]
r=json.load(open(d+'stack_result.json'))
m=json.load(open(d+'mission.json'))
guard=[l.strip().split('relay state: ')[-1] for l in open(d+'velocity_guard.log') if 'relay state' in l]
print(json.dumps({'mode':mode,'run':r['run_id'],'state':r['state'],'error':(r.get('error') or '')[:90],
                  'injected':[e for e in m['events'] if e['stage']=='injected_stall'],'guard_states':guard[:6]},ensure_ascii=False),flush=True)
PY
done
