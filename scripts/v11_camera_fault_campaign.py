"""Reproducible OFFLINE camera-liveness fault injection study (NOT Gazebo).

500 deterministic cases, covering uninterrupted, dropout, replay, regression,
and invalid timestamps. The oracle is a predefined expected outcome per fault.
Neither inference accuracy nor physical navigation is measured here.
"""
from __future__ import annotations
import argparse
import csv
import json
import random
from collections import Counter
from pathlib import Path
from types import SimpleNamespace as NS
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rescuemind.camera_watch import CameraWatch


def ros_frame(sec):
    if sec is None:
        return NS(header=NS(stamp=NS(sec=0,nanosec=0)))
    n=int(round(sec*1e9))
    return NS(header=NS(stamp=NS(sec=n//1_000_000_000,nanosec=n%1_000_000_000)))


def run_campaign(n=100, seed=20261016):
    rng=random.Random(seed)
    output=[]
    for kind in ('healthy','dropout','replay','regression','missing_stamp'):
        for i in range(n):
            heartbeat_age=round(rng.uniform(.7,1.5),3)
            dt=.10
            w=CameraWatch(started_at=0.,max_age_s=heartbeat_age,startup_grace_s=1.)
            freeze_at=3. + rng.random()*.5
            stamp=0.
            reason=None
            for tick in range(91):
                t=round(tick*dt,2)
                valid=t>=.1 and kind=='healthy' or (.1<=t<freeze_at and kind!='healthy')
                if valid:
                    stamp=t
                    w.observe(ros_frame(stamp),t)
                elif t>=freeze_at:
                    if kind=='replay':
                        w.observe(ros_frame(stamp),t)
                    elif kind=='regression' and t<freeze_at+dt:
                        w.observe(ros_frame(stamp-1.),t)
                    elif kind=='missing_stamp' and t<freeze_at+dt:
                        w.observe(ros_frame(None),t)
                reason=w.check(t)
                if reason:
                    break
            predicted=reason or 'running'
            expected={'healthy':'running','dropout':'stale_camera_frames',
                      'replay':'stale_camera_frames','regression':'regressed_camera_stamp',
                      'missing_stamp':'invalid_camera_stamp'}[kind]
            output.append({'condition':kind,'replicate':i,'camera_max_age_s':heartbeat_age,
                           'fault_at_s':round(freeze_at,3), 'terminal':predicted,
                           'expected':expected,'pass':predicted==expected})
    return output


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out',default='outputs/release/v11_camera_fault_campaign.json')
    p.add_argument('--csv',default='outputs/release/v11_camera_fault_campaign.csv')
    a=p.parse_args()
    rows=run_campaign()
    summary={'kind':'OFFLINE_CAMERA_LIVENESS_FAULT_INJECTION_NOT_GAZEBO',
             'cases':len(rows),'pass_count':sum(r['pass'] for r in rows),
             'fail_count':sum(not r['pass'] for r in rows),
             'by_condition':dict(Counter(r['condition'] for r in rows)),
             'all_pass':all(r['pass'] for r in rows),
             'real_ros_tested':False,'real_camera_tested':False}
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    target=Path(a.csv);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0].keys()));writer.writeheader();writer.writerows(rows)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    if not summary['all_pass']:
        raise SystemExit(1)
if __name__=='__main__':main()
