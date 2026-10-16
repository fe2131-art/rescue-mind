#!/usr/bin/env python3
"""Deterministic synthetic odom fault campaign, NOT ROS/Gazebo runtime."""
import json,sys
from pathlib import Path
from types import SimpleNamespace as N
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rescuemind.odom_health import OdomHealth

def fake(stamp=100000000000,x=0.,w=1.,frame='odom'):
    return N(header=N(frame_id=frame,stamp=N(sec=stamp//10**9,nanosec=stamp%10**9)),
             child_frame_id='base_link',pose=N(pose=N(position=N(x=x,y=0.,z=0.),orientation=N(x=0.,y=0.,z=0.,w=w))))

def run():
    groups={}
    for name in ['valid','nan_position','invalid_quaternion','invalid_frame','duplicate_stamp','regressed_stamp']:
        passes=0
        for i in range(100):
            original=100000000000+i*1000000000
            monitor=OdomHealth();assert monitor.observe(fake(original)) is None
            x={'valid':lambda:fake(original+1000000000),
               'nan_position':lambda:fake(original+1000000000,x=float('nan')),
               'invalid_quaternion':lambda:fake(original+1000000000,w=0),
               'invalid_frame':lambda:fake(original+1000000000,frame='map'),
               'duplicate_stamp':lambda:fake(original),
               'regressed_stamp':lambda:fake(original-1000000000)}[name]()
            expected={'valid':None,'nan_position':'invalid_odom_numeric',
                      'invalid_quaternion':'invalid_odom_quaternion',
                      'invalid_frame':'invalid_odom_frames',
                      'duplicate_stamp':'repeated_odom_timestamp',
                      'regressed_stamp':'regressed_odom_timestamp'}[name]
            passes+= monitor.observe(x)==expected
        groups[name]={'cases':100,'passes':passes}
    result={'scope':'SYNTHETIC_ODOMETRY_NOT_GAZEBO','cases':600,'passed':sum(x['passes'] for x in groups.values()),'groups':groups}
    dest=ROOT/'outputs/release/v16_odometry_campaign.json';dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2));assert result['passed']==600

if __name__=='__main__':run()
