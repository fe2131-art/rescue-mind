#!/usr/bin/env python3
"""Print planned local-only VLM study commands, no automatic experiment runs.

Scene truth appears in human comments but NEVER in VLM inference requests.
"""
import json,shlex
from pathlib import Path
R=Path(__file__).resolve().parents[1]
p=json.loads((R/'experiments/v23_locked_protocol.json').read_text(encoding='utf8'))
assert p['planned_n']==len(p['trials'])==30
print('# PRE-REGISTERED 30 candidate commands; manually run, one at a time.')
for t in p['trials']:
    item='飲料水' if t['expected']=='water' else '医療物資'
    cmd=['python3','scripts/v32_orchestrate.py','--run','--scenario','live',
         '--scene',t['scene'],'--local-mode','single','--capture-rosbag',
         '--instruction',f'避難所Bに{item}を届けて']
    print(f'# trial_id={t["id"]} order={t["order"]} repeat={t["repeat"]} expected_action={t["expected_action"]} | human-only; log the actual run_id')
    print(shlex.join(cmd))
