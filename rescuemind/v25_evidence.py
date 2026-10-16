"""Post-arrival camera alignment audit for v2.5 receipts.

This reads self-reported mission events, not authenticated Gazebo ground truth.
Only applies to v2.5 live checkpoint receipts; older fixtures remain historical.
"""
from __future__ import annotations
from math import isfinite

class AlignmentEvidenceError(ValueError):pass


def audit_alignment(m:dict)->dict:
    if m.get('version') != '2.5' or m.get('run_type') not in ('jev_qwen_live_mission','jev_qwen_mission'):
        return {'status':'legacy_not_v25','scope':'NO_ALIGNMENT_ASSERTION'}
    events=m.get('events')
    if not isinstance(events,list):raise AlignmentEvidenceError('events missing')
    def only(stage):
        v=[(i,e) for i,e in enumerate(events) if isinstance(e,dict) and e.get('stage')==stage]
        if len(v)!=1:raise AlignmentEvidenceError(f'{stage}: expected exactly one event')
        return v[0]
    supply_i,supply=only('supply_station')
    aim_i,aim=only('camera_aim_aligned')
    frame_i,frame=only('checkpoint_frame')
    decision_i,decision=only('checkpoint_decision')
    if not (supply_i < aim_i < frame_i < decision_i):
        raise AlignmentEvidenceError('VLM checkpoint occurred before alignment or invalid ordering')
    if not supply.get('arrived') or aim.get('target_station') != m.get('intent',{}).get('item'):
        raise AlignmentEvidenceError('alignment target not the actual arrived station')
    err=aim.get('error_rad')
    if type(err) not in (float,int) or not isfinite(err) or abs(err)>.10:
        raise AlignmentEvidenceError('aim error too large')
    stamps=[]
    for event in (supply,aim,frame,decision):
        t=event.get('t_wall_s')
        if type(t) not in (int,float) or not isfinite(t) or t<0:
            raise AlignmentEvidenceError('invalid event monotonic offset')
        stamps.append(t)
    if stamps!=sorted(stamps) or frame['t_wall_s']-aim['t_wall_s']<.5:
        raise AlignmentEvidenceError('frame is not fresh after camera alignment')
    frame_ns=frame.get('ros_acquisition_stamp_ns')
    if type(frame_ns)!=int or frame_ns<=0:
        raise AlignmentEvidenceError('missing ROS image acquisition timestamp')
    return {'status':'post_aim_fresh_frame','scope':'SELF_REPORTED_ROS_EVENT_EVIDENCE_NOT_PHYSICS_ATTESTATION',
            'aim_error_rad':err,'frame_stamp_ns':frame_ns}
