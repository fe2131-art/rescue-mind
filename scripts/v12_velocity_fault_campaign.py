"""Reproducible software-only fault injection for relay decisions (NOT real Gazebo)."""
from __future__ import annotations
import csv
import json
from pathlib import Path
import random
import sys
from types import SimpleNamespace as N
from math import pi
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.velocity_relay import VelocityRelay

def image(t):
    ns=round(t*1e9)
    return N(header=N(stamp=N(sec=ns//1000000000,nanosec=ns%1000000000)))

def scan(dist=3.):
    return N(ranges=[dist]*360,angle_min=-pi,angle_increment=2*pi/360,range_min=.08,range_max=10.)

CONDITIONS=('healthy','missing_request','stale_command','camera_stale','scan_stale',
            'odom_stale','close_obstacle','emergency_stop','invalid_request')

def one(kind, speed):
    r=VelocityRelay(0.)
    r.camera_frame(image(.3),.3);r.laser_scan(scan(),.3);r.odometry(.3)
    if kind=='healthy':r.request(speed,0,.4);at=.41
    elif kind=='missing_request':at=.4
    elif kind=='stale_command':
        r.camera_frame(image(1.0),1.);r.laser_scan(scan(),1.);r.odometry(1.)
        r.request(speed,0,.4);at=1.01
    elif kind=='camera_stale':
        r.laser_scan(scan(),2.5);r.odometry(2.5)
        r.request(speed,0,2.5);at=2.51
    elif kind=='scan_stale':
        r.camera_frame(image(1.5),1.5);r.odometry(1.5)
        r.request(speed,0,1.5);at=1.51
    elif kind=='odom_stale':
        r.camera_frame(image(1.5),1.5);r.laser_scan(scan(),1.5)
        r.request(speed,0,1.5);at=1.51
    elif kind=='close_obstacle':r.laser_scan(scan(.2),.4);r.request(speed,0,.4);at=.41
    elif kind=='emergency_stop':r.emergency_stop(True);r.request(speed,0,.4);at=.41
    else:r.request(float('nan'),0,.4);at=.41
    result=r.decide(at)
    should_move=(kind=='healthy')
    assert (result.linear>0)==should_move,(kind,result)
    assert result.angular==0
    return {'condition':kind,'actual_forward':round(result.linear,3),
            'expected_forward':round(speed,3) if should_move else 0,
            'outcome':'PASS','reason':result.reason}

def main():
    random.seed(20261016)
    rows=[one(kind,random.uniform(.03,.23)) for kind in CONDITIONS for _ in range(125)]
    out=ROOT/'outputs/release';out.mkdir(parents=True,exist_ok=True)
    with (out/'v12_velocity_fault_campaign.csv').open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    report={'kind':'ARTIFICIAL_SOFTWARE_FAULT_INJECTION_NOT_ROS_OR_MODEL_ACCURACY',
            'seed':20261016,'cases':len(rows),'conditions':list(CONDITIONS),
            'passes':sum(r['outcome']=='PASS' for r in rows),
            'expected_moving':125,'actual_moving':sum(r['actual_forward']>0 for r in rows),
            'no_real_gazebo_or_api':True}
    (out/'v12_velocity_fault_campaign.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
