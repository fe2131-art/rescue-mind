#!/usr/bin/env python3
"""Reproducible SYNTHETIC traces for independently testing evidence checks.

All trajectories are fabricated by code for stress testing. They are NEVER
actual ROS/Gazebo measurements or eligible final-project execution evidence.
"""
from __future__ import annotations
import json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rescuemind.motion_evidence import audit_motion,MotionEvidenceError

RUN_ID='f'*16; ST=(1.18,1.13);SH=(2.15,-1.12)

def rows_for(case):
    data=[{'kind':'meta','run_id':RUN_ID,'schema':'synthetic_test'}]
    points=[(0.,0.)]
    for start,end in (((0.,0.),ST),(ST,SH)):
        for i in range(1,61):
            points.append((start[0]+(end[0]-start[0])*i/60,
                           start[1]+(end[1]-start[1])*i/60))
    if case=='absent_shelter':points=points[:61]
    if case=='teleport':points[12]=(5.,5.)
    for idx,(x,y) in enumerate(points):
        data.append({'kind':'odom','ros_stamp_ns':1_000_000_000+idx*500_000_000,
                     'x':x,'y':y,'frame_id':'odom','child_frame_id':'base_link'})
        data.append({'kind':'cmd_vel','linear':0.2,'angular':0.01})
    if case=='clock_regression':
        sample=[r for r in data if r.get('kind')=='odom'];sample[5]['ros_stamp_ns']=sample[4]['ros_stamp_ns']
    if case=='no_velocity':data=[r for r in data if r['kind']!='cmd_vel']
    if case=='runid_mismatch':data[0]['run_id']='0'*16
    return data

def main():
    report=[]
    with tempfile.TemporaryDirectory() as tmp:
        f=Path(tmp)/'synthetic.jsonl'
        for case in ('nominal','absent_shelter','teleport','clock_regression','no_velocity','runid_mismatch'):
            f.write_text('\n'.join(json.dumps(x) for x in rows_for(case))+'\n')
            try:
                result=audit_motion(f,run_id=RUN_ID,station=ST,shelter=SH)
                observed='PASS'; reason=result['scope']
            except MotionEvidenceError as e:
                observed='REJECT';reason=str(e)
            expected='PASS' if case=='nominal' else 'REJECT'
            report.append({'test_case':case,'expected':expected,'observed':observed,
                           'matched':observed==expected,'reason':reason})
    result={'scope':'SYNTHETIC_FIXTURE_NOT_REAL_ROS_OR_GAZEBO',
            'total':len(report),'passed':sum(x['matched'] for x in report),'results':report}
    output=ROOT/'verification/v18/synthetic_motion_evidence_campaign.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if result['passed']!=result['total']:raise SystemExit(3)
if __name__=='__main__':main()
