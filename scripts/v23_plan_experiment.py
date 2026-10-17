#!/usr/bin/env python3
"""Pre-register a reproducible schedule; print manual real-Gazebo capture commands.

This deliberately does not launch API calls or label the model input with scene truth.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rescuemind.v23_protocol import dump_protocol

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repetitions',type=int,default=5)
    p.add_argument('--seed',type=int,default=20261016)
    p.add_argument('--out',type=Path,default=ROOT/'experiments/v23_locked_protocol.json')
    p.add_argument('--commands',type=Path,default=ROOT/'experiments/v23_commands.sh')
    a=p.parse_args(argv)
    protocol=dump_protocol(a.out,a.repetitions,a.seed)
    commands=['#!/usr/bin/env bash','set -euo pipefail','# Run ONE scenario at a time on Ubuntu/Gazebo AFTER checking the camera image.',
              '# This script prints (does not execute) candidate runs; capture evidence requires human review.']
    for t in protocol['trials']:
        item='\u98f2\u6599\u6c34' if t['expected']=='water' else '\u533b\u7642\u7269\u8cc7'
        statement=f"python3 scripts/v22_orchestrate.py --run --scenario live --scene {t['scene']} --capture-rosbag --instruction '\u907f\u96e3\u6240B\u306b{item}\u3092\u5c4a\u3051\u3066'"
        commands.extend([f'# {t["id"]} repeat={t["repeat"]} ; protocol truth is NOT fed to model',f'echo {json.dumps(statement,ensure_ascii=False)}'])
    a.commands.parent.mkdir(parents=True,exist_ok=True)
    a.commands.write_text('\n'.join(commands)+'\n',encoding='utf-8')
    print(json.dumps({'planned_n':len(protocol['trials']),'protocol':str(a.out),'commands_print_only':str(a.commands),'executed_trials':0},ensure_ascii=False,indent=2))
    return 0
if __name__=='__main__':raise SystemExit(main())
