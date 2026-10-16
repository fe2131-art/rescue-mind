"""Deterministic synthetic input quality checks; NEVER model accuracy."""
from __future__ import annotations
import json
import random
import sys
from pathlib import Path
from types import SimpleNamespace as N
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.sensor_contract import StreamAudit

def make(kind, stamp, *, fault=False):
    hdr=N(stamp=N(sec=stamp, nanosec=100),frame_id='odom')
    if kind=='camera':
        kwargs={'header':hdr, 'encoding':'rgb8','width':320,'height':240,'step':960,
                'is_bigendian':0,'data':b'\0'*(320*240*3)}
        if fault: kwargs['data']=b'corrupt'
    elif kind=='scan':
        kwargs={'header':hdr,'angle_min':-3.14,'angle_max':3.14,'angle_increment':.01745,
                'range_min':.08,'range_max':10.,'ranges':[float('inf')]*360}
        if fault: kwargs['ranges'][100]=float('nan')
    elif kind=='odom':
        kwargs={'header':hdr,'child_frame_id':'base_link',
                'pose':N(pose=N(position=N(x=0.,y=0.,z=0.),orientation=N(x=0.,y=0.,z=0.,w=1.)))}
        if fault: kwargs['pose'].pose.orientation.w=9.
    else: raise ValueError(kind)
    return N(**kwargs)

def evaluate(n=600,seed=20261016):
    r=random.Random(seed); passes=0; fail_cases=0; failures=[]
    for i in range(n):
        kind=('camera','scan','odom')[i%3]
        faulty=i%5 != 0  # 80% fault injection, 20% valid
        audit=StreamAudit()
        try:
            for j in range(3):
                getattr(audit,{'camera':'add_image','scan':'add_scan','odom':'add_odom'}[kind])(make(kind,j+1,fault=faulty))
        except ValueError:
            denied=True
        else:
            denied=False
        expected=faulty
        if denied==expected: passes+=1
        else: failures.append({'case':i,'kind':kind,'expected_denial':expected,'actual_denial':denied})
        if faulty:fail_cases+=1
    return {'verification_scope':'DETERMINISTIC_SYNTHETIC_SENSOR_INPUTS_NOT_ROS_OR_GAZEBO',
            'seed':seed,'cases':n,'expected_rejected':fail_cases,'passed':passes,
            'failed':len(failures),'issues':failures[:10]}

if __name__=='__main__':
    d=evaluate()
    target=ROOT/'outputs/release/v15_sensor_fault_campaign.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(d,indent=2)+'\n')
    print(json.dumps(d,indent=2))
    if d['failed']:raise SystemExit(1)
