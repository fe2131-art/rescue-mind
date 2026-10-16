#!/usr/bin/env python3
"""Register a saved REAL Ubuntu Gazebo trial only after the strict evidence audit.

Does not run Jev/Qwen/Gazebo. --run-dir must be a completed stack run.
"""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rescuemind.v24_run_registry import register,RunRegistrationError

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trial-id',required=True)
    p.add_argument('--run-dir',required=True,type=Path)
    p.add_argument('--protocol',type=Path,default=ROOT/'experiments/v23_locked_protocol.json')
    p.add_argument('--registry',type=Path,default=ROOT/'experiments/v24_run_registry.jsonl')
    a=p.parse_args(argv)
    try:
        result=register(ROOT,json.loads(a.protocol.read_text(encoding='utf-8')),a.trial_id,a.run_dir,a.registry)
    except (ValueError,OSError,KeyError) as e:
        print('DENIED: '+str(e),file=sys.stderr)
        return 2
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return 0
if __name__=='__main__':raise SystemExit(main())
