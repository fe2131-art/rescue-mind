#!/usr/bin/env python3
"""Offline audit of independently observed ROS movement for a completed run.

Do not call this proof of Gazebo provenance without checking the running
simulator and the actual captured video. ROS 2 topics can be spoofed.
"""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.motion_evidence import audit_motion
from rescuemind.run_completion import validate

def audit_run(run_dir, scenario):
    d=Path(run_dir)
    receipt=json.loads((d/'mission.json').read_text())
    run_id=receipt['run_id']
    completion=validate(d/'mission.json',scenario,run_id)
    item=receipt['intent']['item']
    if item not in ('water','medicine'):
        raise ValueError('invalid supply item')
    c=json.loads((ROOT/'configs/gazebo_waypoints.json').read_text())
    motion=audit_motion(d/'independent_ros_topics.jsonl',run_id=run_id,
                        station=c[item],shelter=c['B'])
    causal=None
    if scenario == 'live':
        from rescuemind.causal_evidence import audit_causal
        causal=audit_causal(d/'mission.json',d/'independent_ros_topics.jsonl',
                            station=c[item],shelter=c['B'])
    return {'state':'VALIDATED_SOFTWARE_RECEIPT_AND_INDEPENDENT_ROS_TOPIC_TRAJECTORY',
            'scope':'ROS TOPIC OBSERVATION ONLY; check video + real Gazebo before claiming physics',
            'completion':completion,'motion':motion,'authorization_motion_chronology':causal}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('run_dir',type=Path)
    p.add_argument('--scenario',choices=('motion-check','live'),required=True)
    a=p.parse_args(argv)
    try:
        result=audit_run(a.run_dir,a.scenario)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (ValueError,KeyError,OSError,TypeError) as e:
        print(json.dumps({'state':'REJECTED','reason':str(e)},ensure_ascii=False,indent=2),file=sys.stderr)
        return 2
if __name__=='__main__':raise SystemExit(main())
