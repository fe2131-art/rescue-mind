#!/usr/bin/env python3
"""Evaluate real-world capture folders without counting mocked tests as VLM accuracy.

Pass one directory per trial (outputs/runs/<run_id>/). The scene was recorded
by the v2.2 supervisor; trial authenticity is NOT cryptographically proven.
"""
from __future__ import annotations
import argparse,csv,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.negative_evidence import audit_denial
from rescuemind.scene_variants import SCENES
from rescuemind.motion_evidence import audit_motion
from rescuemind.causal_evidence import audit_causal
from rescuemind.run_completion import validate


def evaluate(directory:Path)->dict:
    plan=json.loads((directory/'stack_plan.json').read_text())
    status=json.loads((directory/'stack_result.json').read_text())
    mission=json.loads((directory/'mission.json').read_text())
    from rescuemind.v25_evidence import audit_alignment
    audit_alignment(mission)
    expected='ALLOW' if plan.get('scene')=='nominal' else 'DENY'
    if plan.get('scene') not in SCENES or plan.get('scenario')!='live':
        raise ValueError('trial must be v2.2 live with explicit scene')
    if any(x.get('run_id')!=directory.name for x in (status,mission)):
        raise ValueError('run ID mismatch')
    if status.get('scene')!=plan['scene']:
        raise ValueError('different scene in outcome')
    item=mission.get('intent',{}).get('item')
    if item not in ('water','medicine'):
        raise ValueError('unknown supply item')
    waypoints=json.loads((ROOT/'configs/gazebo_waypoints.json').read_text())
    observed='UNVERIFIED'
    try:
        if expected=='ALLOW':
            if status.get('state')!='COMPLETED':
                raise ValueError('nominal trial not completed')
            validate(directory/'mission.json','live',directory.name)
            audit_motion(directory/'independent_ros_topics.jsonl',run_id=directory.name,
                         station=waypoints[item],shelter=waypoints['B'])
            audit_causal(directory/'mission.json',directory/'independent_ros_topics.jsonl',
                         station=waypoints[item],shelter=waypoints['B'])
            observed='ALLOW_AND_REACHED_SHELTER'
        else:
            if status.get('state') not in ('FAILED','COMPLETED_EXPECTED_DENIAL'):
                raise ValueError('counterfactual expected AI denial not observed')
            audit_denial(directory/'mission.json',directory/'independent_ros_topics.jsonl',
                         station=waypoints[item],shelter=waypoints['B'])
            observed='DENY_AND_STATIONARY'
        passed=True;reason='proof_conditions_passed'
    except (ValueError,FileNotFoundError,KeyError,TypeError) as e:
        passed=False;reason=f'{type(e).__name__}:{e}'
    return {'run_id':directory.name,'scene':plan['scene'],'supply':item,
            'expected':expected,'observed':observed,'verified':passed,'reason':reason,
            'basis':'SAVED_LIVE_RUN_LOGS_NOT_TRUE_GAZEBO_PROVENANCE'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('runs',nargs='+',type=Path)
    p.add_argument('--csv',type=Path,default=ROOT/'outputs/v22_trial_audit.csv')
    a=p.parse_args()
    rows=[]
    for directory in a.runs:
        try: rows.append(evaluate(directory))
        except (ValueError,OSError,KeyError,TypeError) as exc:
            rows.append({'run_id':directory.name,'scene':'unknown','supply':'unknown',
                         'expected':'unknown','observed':'UNVERIFIED','verified':False,
                         'reason':f'{type(exc).__name__}:{exc}',
                         'basis':'INVALID_OR_INCOMPLETE_RUN'})
    a.csv.parent.mkdir(parents=True,exist_ok=True)
    with a.csv.open('w',newline='',encoding='utf8') as out:
        w=csv.DictWriter(out,fieldnames=('run_id','scene','supply','expected','observed','verified','reason','basis'))
        w.writeheader();w.writerows(rows)
    print(json.dumps({'total':len(rows),'verified':sum(r['verified'] for r in rows),
                      'csv':str(a.csv),'scope':'No image recognition rate without manually labelled real trials'},
                     indent=2))
    return 0 if all(r['verified'] for r in rows) else 2
if __name__=='__main__':raise SystemExit(main())
