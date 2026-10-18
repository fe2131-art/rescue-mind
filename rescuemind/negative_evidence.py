"""Verify an expected *on-site AI denial* with independent ROS movement evidence.

Negative trial != a crash. We require the robot reached the station, a real
on-site Jev+Qwen checkpoint returned DENY, and independent /odom remained at
that station through the post-decision observation window. Simulated or fake
model responses do not qualify as real API evaluation evidence.
"""
from __future__ import annotations
import json,math
from pathlib import Path

class DenialEvidenceError(ValueError):
    pass

def _strict_num(x):
    return type(x) in (int,float) and math.isfinite(x)

def audit_denial(mission_path, telemetry_path, *, station, shelter, tolerance=0.43,
                 min_samples_after=2, extra_points=()) -> dict:
    m=json.loads(Path(mission_path).read_text(encoding='utf-8'))
    if m.get('run_type') not in ('jev_qwen_live_mission','local_vlm_live_mission') or m.get('success') is not False:
        raise DenialEvidenceError('not a failed live AI mission')
    run_id=m.get('run_id')
    if type(run_id)!=str or len(run_id)!=16 or any(c not in '0123456789abcdef' for c in run_id):
        raise DenialEvidenceError('invalid run id')
    start=m.get('mission_start_unix_ns')
    if type(start)!=int or start<=0:
        raise DenialEvidenceError('missing mission time anchor')
    events=m.get('events')
    if not isinstance(events,list):
        raise DenialEvidenceError('missing mission events')
    def event(stage):
        rows=[e for e in events if isinstance(e,dict) and e.get('stage')==stage]
        if len(rows)!=1 or not _strict_num(rows[0].get('t_wall_s')):
            raise DenialEvidenceError('missing/ambiguous event '+stage)
        return rows[0]
    sta,dec=event('supply_station'),event('checkpoint_decision')
    if sta.get('arrived') is not True or dec.get('allow') is not False:
        raise DenialEvidenceError('did not reach station and explicitly deny')
    if dec.get('reason')=='on_site_supply_confirmed':
        raise DenialEvidenceError('allow reason on denial')
    if any(e.get('stage')=='shelter_approach' and e.get('arrived') for e in events if isinstance(e,dict)):
        raise DenialEvidenceError('mission falsely reports shelter arrival')
    if not (0 <= sta['t_wall_s'] < dec['t_wall_s'] < 3600):
        raise DenialEvidenceError('wrong event chronology')
    checkpoint=m.get('checkpoint')
    if not isinstance(checkpoint,dict) or checkpoint.get('decision',{}).get('allow') is not False:
        raise DenialEvidenceError('missing/contradictory checkpoint output')
    calls=checkpoint.get('model_calls',{})
    if m['run_type']=='local_vlm_live_mission':
        from .local_run_audit import audit_local_checkpoint
        from .real_profile import audit_kwargs     # I-26: {} unless the run used --site-config
        audit_local_checkpoint(checkpoint,checkpoint.get('image_sha256',''),expected=m.get('intent',{}).get('item'),**audit_kwargs(m))
    elif calls.get('jev',{}).get('real_model') is not True or calls.get('qwen',{}).get('real_model') is not True:
        raise DenialEvidenceError('not marked as real model inference')
    t_station=start+round(sta['t_wall_s']*1e9)
    t_decision=start+round(dec['t_wall_s']*1e9)
    with Path(telemetry_path).open(encoding='utf8') as f:
        obs=[json.loads(line) for line in f if line.strip()]
    if not obs or obs[0].get('kind')!='meta' or obs[0].get('run_id')!=run_id:
        raise DenialEvidenceError('independent recorder run mismatch')
    samples=[]; truth=[]; prev_t=None
    for r in obs[1:]:
        if r.get('kind') not in ('odom','cmd_vel','ground_truth'):
            raise DenialEvidenceError('unexpected observation kind')
        t=r.get('wall_unix_ns')
        if type(t)!=int or t<=0 or (prev_t is not None and t<prev_t):
            raise DenialEvidenceError('non-monotonic observation wall time')
        prev_t=t
        if r['kind']=='odom':
            if not all(_strict_num(r.get(k)) for k in ('x','y')):
                raise DenialEvidenceError('invalid independent odometry')
            if r.get('frame_id')!='odom' or r.get('child_frame_id')!='base_link':
                raise DenialEvidenceError('wrong odometry frame')
            samples.append((t,float(r['x']),float(r['y'])))
        elif r['kind']=='ground_truth':
            if not all(_strict_num(r.get(k)) for k in ('x','y')):
                raise DenialEvidenceError('invalid ground-truth position')
            truth.append((t,float(r['x']),float(r['y'])))
    # v3.3: prefer Gazebo's own model pose over wheel odometry when bridged.
    source='wheel_odometry'
    if len(truth)>=8:
        samples,source=truth,'gazebo_ground_truth'
    if len(samples)<8:
        raise DenialEvidenceError('too few odometry observations')
    def dist(p,xy): return math.hypot(p[1]-xy[0],p[2]-xy[1])
    if any(dist(o,shelter)<=tolerance for o in samples):
        raise DenialEvidenceError('shelter observed despite AI denial')
    dwell=[o for o in samples if t_station+200_000_000<=o[0]<=t_decision]
    after=[o for o in samples if o[0]>=t_decision]
    if len(dwell)<2 or len(after)<min_samples_after:
        raise DenialEvidenceError('insufficient independent stationary evidence')
    # I-14: look-around side views are logged checkpoint poses; the robot may stand at any of them
    allowed=[tuple(station)]+[tuple(x) for x in extra_points]
    if any(min(dist(o,xy) for xy in allowed)>tolerance for o in dwell+after):
        raise DenialEvidenceError('left station before/after denial')
    # Cannot prove actual physics. This requires continued recorder samples after the denial.
    return {'pass':True,'run_id':run_id,'scope':'INDEPENDENT_ROS_OBSERVATION_NOT_AUTHENTICATED_GAZEBO',
            'checkpoint_reason':dec['reason'],'position_source':source,'dwell_samples':len(dwell),
            'post_denial_samples':len(after),'outcome':'DENIED_AND_OBSERVED_STATIONARY'}
