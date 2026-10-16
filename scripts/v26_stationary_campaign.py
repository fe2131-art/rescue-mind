#!/usr/bin/env python3
"""Synthetic-only motion traces through production StationaryGate core."""
from pathlib import Path
import csv, json, math, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rescuemind.waypoint import Pose2
from rescuemind.stationary_gate import StationaryGate, MotionUnstable

OUT=ROOT/'verification/v26'
OUT.mkdir(parents=True,exist_ok=True)

def samples(mode):
    rows=[]
    for k in range(25):
        t=round(k*.1+.1,4)
        x=yaw=linear=angular=0.
        if mode=='steady_jitter':x=0.002*math.sin(k*.3);yaw=0.003*math.cos(k*.3);linear=.006;angular=.004
        if mode=='coasting_linear':linear=.12;x=.012*k
        if mode=='coasting_spin':angular=.19;yaw=.019*k
        if mode=='lateral_push':x=0 if k<10 else .045
        if mode=='angular_push':yaw=0 if k<10 else .11
        if mode=='post_lock_velocity':linear=0 if k<13 else .12
        if mode=='post_lock_roll':angular=0 if k<13 else .20
        if mode=='repeated_time':t=.1 if k>4 else t
        if mode=='invalid_twist' and k==8:linear=float('nan')
        if mode=='brief_coast_then_rest' and k<7:linear=.12;x=.015*k
        if mode=='never_observe_enough' and k>1:break
        rows.append((t,x,yaw,linear,angular))
    return rows

EXPECTED={
 'steady': 'LOCKED', 'steady_jitter':'LOCKED', 'coasting_linear':'NOT_LOCKED',
 'coasting_spin':'NOT_LOCKED','lateral_push':'MOTION_FAULT',
 'angular_push':'MOTION_FAULT', 'post_lock_velocity':'MOTION_FAULT',
 'post_lock_roll':'MOTION_FAULT','repeated_time':'CLOCK_FAULT',
 'invalid_twist':'INVALID_FAULT','brief_coast_then_rest':'LOCKED',
 'never_observe_enough':'NOT_LOCKED',
}

def run():
    results=[];traces=[]
    for mode,expected in EXPECTED.items():
        gate=StationaryGate()
        outcome='NOT_LOCKED';reason=None
        for t,x,yaw,v,w in samples(mode):
            try:
                gate.observe(Pose2(x,0.,yaw),v,w,t)
            except MotionUnstable as exc:
                reason=str(exc)
                outcome=('CLOCK_FAULT' if 'time' in reason else
                         'INVALID_FAULT' if 'invalid_stationary' in reason else 'MOTION_FAULT')
                break
            traces.append({'scenario':mode,'t_s':t,'x_m':x,'yaw_rad':yaw,'linear_mps':v,
                           'angular_rps':w,'locked':int(gate.locked)})
            if gate.locked:outcome='LOCKED'
        result={'scenario':mode,'expected':expected,'actual':outcome,'matched':outcome==expected,
                'samples':gate.samples,'resets':gate.resets,'reason':reason}
        results.append(result)
    with (OUT/'synthetic_stationary_traces.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(traces[0]))
        writer.writeheader();writer.writerows(traces)
    report={'scope':'DETERMINISTIC_SYNTHETIC_NOT_GAZEBO',
            'total':len(results),'matched':sum(x['matched'] for x in results),
            'results':results,'real_ros_gazebo_api':'NOT_TESTED'}
    (OUT/'synthetic_stationary_campaign.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(report,indent=2,ensure_ascii=False))
    if report['matched']!=report['total']:
        raise SystemExit(2)
    return report
if __name__=='__main__':run()
