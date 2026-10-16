"""Independent ROS odometry/velocity trace audit for this simulation project.

A separate recorder observes ROS messages, instead of trusting mission-generated
waypoint arrival events.  This is evidence of *observed ROS topic movement*, not
cryptographic proof of a real physics engine, nor a hardware safety mechanism.
"""
from __future__ import annotations
import json,math
from pathlib import Path

class MotionEvidenceError(ValueError):
    pass

def _number(x):
    return type(x) in (int,float) and math.isfinite(x)

def audit_motion(path, *, run_id, station, shelter, tolerance=0.34,
                 min_path_m=0.65, max_observed_speed_mps=1.2):
    if not isinstance(run_id,str) or len(run_id)!=16:
        raise MotionEvidenceError('invalid run id')
    if not 0.10<=tolerance<=0.6:
        raise MotionEvidenceError('invalid tolerance')
    for goal in (station,shelter):
        if len(goal)!=2 or not all(_number(c) for c in goal):
            raise MotionEvidenceError('invalid goal')
    lines=Path(path).read_text(encoding='utf-8').splitlines()
    if not lines: raise MotionEvidenceError('empty telemetry')
    try:
        records=[json.loads(line) for line in lines]
    except (ValueError,TypeError) as e:
        raise MotionEvidenceError('malformed telemetry JSONL') from e
    if not isinstance(records[0],dict) or records[0].get('kind')!='meta' or records[0].get('run_id')!=run_id:
        raise MotionEvidenceError('recorder run_id missing/mismatch')
    odom=[]; velocity=[]
    prev_stamp=None
    for r in records[1:]:
        if not isinstance(r,dict): raise MotionEvidenceError('nonobject telemetry row')
        if r.get('kind')=='odom':
            p=(r.get('x'),r.get('y'))
            s=r.get('ros_stamp_ns')
            if not all(_number(v) for v in p) or type(s) is not int or s<=0:
                raise MotionEvidenceError('invalid odometry data')
            if r.get('frame_id')!='odom' or r.get('child_frame_id')!='base_link':
                raise MotionEvidenceError('odom frame mismatch')
            if prev_stamp is not None and s<=prev_stamp:
                raise MotionEvidenceError('duplicate or reversed acquisition stamps')
            if odom:
                a=odom[-1]; delta=(s-a[0])/1e9
                if math.hypot(p[0]-a[1],p[1]-a[2])/delta>max_observed_speed_mps:
                    raise MotionEvidenceError('unphysically fast observed displacement')
            prev_stamp=s
            odom.append((s,p[0],p[1]))
        elif r.get('kind')=='cmd_vel':
            v=r.get('linear'); w=r.get('angular')
            if not _number(v) or not _number(w):
                raise MotionEvidenceError('invalid velocity telemetry')
            velocity.append((v,w))
        elif r.get('kind')=='ground_truth':
            continue  # audited separately by rescuemind.ground_truth_evidence
        else: raise MotionEvidenceError('unexpected telemetry event')
    if len(odom)<8: raise MotionEvidenceError('too few independent odometry samples')
    if len(velocity)<5 or sum(abs(v)+abs(w)>0.01 for v,w in velocity)<5:
        raise MotionEvidenceError('no independent moving-velocity observations')
    if math.hypot(odom[0][1],odom[0][2])>0.6:
        raise MotionEvidenceError('start not near expected origin')
    def near(row, target):
        return math.hypot(row[1]-target[0],row[2]-target[1])<=tolerance
    first_station=next((i for i,r in enumerate(odom) if near(r,station)),None)
    if first_station is None: raise MotionEvidenceError('supply station not observed')
    first_shelter=next((i for i,r in enumerate(odom) if i>first_station and near(r,shelter)),None)
    if first_shelter is None: raise MotionEvidenceError('shelter after station not observed')
    if first_station<2 or first_shelter-first_station<2:
        raise MotionEvidenceError('insufficient trajectory samples between visits')
    distance=sum(math.hypot(b[1]-a[1],b[2]-a[2]) for a,b in zip(odom,odom[1:]))
    if distance<min_path_m:
        raise MotionEvidenceError('no meaningful actual displacement')
    return {'scope':'independent_ROS_topic_observation_NOT_physics_authentication',
            'run_id':run_id,'odom_count':len(odom),'velocity_count':len(velocity),
            'path_length_m':round(distance,3), 'station_sample_index':first_station,
            'shelter_sample_index':first_shelter,'station_xy':list(station),
            'shelter_xy':list(shelter),'pass':True}
