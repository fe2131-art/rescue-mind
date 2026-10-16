#!/usr/bin/env python3
"""v2.8 strict trial registry; demands ROS /clock aligned camera before append.

Historical v24_register_trial.py is retained only to reproduce earlier
synthetic-fixture tests. Use this entrypoint for all new v2.8 results.
"""
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.v28_clock_evidence import audit_clock_capture,ClockEvidenceError
from rescuemind.v24_run_registry import register,RunRegistrationError

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trial-id',required=True)
    p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--protocol',type=Path,default=ROOT/'experiments/v23_locked_protocol.json')
    p.add_argument('--registry',type=Path,default=ROOT/'experiments/v28_verified_trials.jsonl')
    a=p.parse_args(argv)
    try:
        mission=json.loads((a.run_dir/'mission.json').read_text(encoding='utf8'))
        if mission.get('version')!='2.8':
            raise RunRegistrationError('v2.8 mission version required; older trial receipts not accepted')
        audit_clock_capture(mission)
        result=register(ROOT,json.loads(a.protocol.read_text(encoding='utf8')),
                        a.trial_id,a.run_dir,a.registry)
    except (ClockEvidenceError,RunRegistrationError,OSError,ValueError,KeyError,TypeError) as exc:
        print('DENIED: '+str(exc),file=sys.stderr)
        return 2
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0
if __name__=='__main__':raise SystemExit(main())
