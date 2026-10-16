"""Correlate live checkpoint decision time with *independent* ROS odometry.

This is a trace-consistency check, NOT a causal-inference proof or secure
attestation of a Gazebo process. All timestamps compared here are host wall
clock timestamps; ROS simulation acquisition stamps are deliberately not
compared to host Unix time. A fake ROS publisher could fabricate observations.
"""
from __future__ import annotations
import json
import math
from pathlib import Path

class CausalEvidenceError(ValueError):
    pass

def finite_number(x):
    return type(x) in (int, float) and math.isfinite(x)

def audit_causal(mission_path, telemetry_path, *, station, shelter, stationary_tolerance_m=0.40):
    """Reject trajectories that reach the shelter before a live AI allow decision.

    Runs after `run_completion.validate` and `motion_evidence.audit_motion`.
    No inference is made from a ROS acquisition stamp vs a wall-clock stamp.
    """
    if not 0.2 <= stationary_tolerance_m <= 0.8:
        raise CausalEvidenceError('invalid station tolerance')
    m = json.loads(Path(mission_path).read_text(encoding='utf8'))
    if m.get('run_type') not in ('jev_qwen_live_mission','local_vlm_live_mission') or m.get('success') is not True:
        raise CausalEvidenceError('not a completed live AI mission')
    start = m.get('mission_start_unix_ns')
    if type(start) is not int or start <= 0:
        raise CausalEvidenceError('missing mission start wall-clock anchor')
    events = m.get('events')
    if not isinstance(events, list):
        raise CausalEvidenceError('missing event timeline')
    def stage_event(stage):
        matches = [e for e in events if isinstance(e, dict) and e.get('stage') == stage]
        if len(matches) != 1 or not finite_number(matches[0].get('t_wall_s')):
            raise CausalEvidenceError('ambiguous or missing event: ' + stage)
        return matches[0]
    station_event=stage_event('supply_station')
    decision=stage_event('checkpoint_decision')
    shelter_event=stage_event('shelter_approach')
    if station_event.get('arrived') is not True or shelter_event.get('arrived') is not True:
        raise CausalEvidenceError('arrivals not confirmed')
    if decision.get('allow') is not True or decision.get('reason') != 'on_site_supply_confirmed':
        raise CausalEvidenceError('the AI checkpoint did not grant a valid on-site permission')
    t_station, t_decision, t_shelter = [e['t_wall_s'] for e in (station_event, decision, shelter_event)]
    if not (0 <= t_station < t_decision < t_shelter <= 3600):
        raise CausalEvidenceError('impossible mission event order')
    absolute = [start + round(t*1_000_000_000) for t in (t_station, t_decision, t_shelter)]
    lines=Path(telemetry_path).read_text(encoding='utf8').splitlines()
    try: recs=[json.loads(line) for line in lines]
    except ValueError as exc: raise CausalEvidenceError('invalid independent telemetry') from exc
    if not recs or recs[0].get('kind') != 'meta' or recs[0].get('run_id') != m.get('run_id'):
        raise CausalEvidenceError('observer run id mismatch')
    observer_start=recs[0].get('start_unix_ns')
    if type(observer_start) is not int or observer_start > start+1_000_000_000:
        raise CausalEvidenceError('observer not started before mission')
    observations=[]
    truth=[]
    last_t=None
    for r in recs[1:]:
        t=r.get('wall_unix_ns')
        if type(t) is not int or t<=0 or (last_t is not None and t < last_t):
            raise CausalEvidenceError('invalid/reversed observer wall clock')
        last_t=t
        if r.get('kind')=='odom':
            if not all(finite_number(r.get(k)) for k in ('x','y')):
                raise CausalEvidenceError('invalid observer position')
            observations.append((t,float(r['x']),float(r['y'])))
        elif r.get('kind')=='ground_truth':
            if not all(finite_number(r.get(k)) for k in ('x','y')):
                raise CausalEvidenceError('invalid ground-truth position')
            truth.append((t,float(r['x']),float(r['y'])))
        elif r.get('kind')!='cmd_vel':
            raise CausalEvidenceError('unexpected ROS observation type')
    # v3.3: prefer Gazebo's own model pose over wheel odometry when bridged.
    source='wheel_odometry'
    if len(truth)>=8:
        observations,source=truth,'gazebo_ground_truth'
    if len(observations)<8:
        raise CausalEvidenceError('not enough external observations')
    def dist(row, xy): return math.hypot(row[1]-xy[0], row[2]-xy[1])
    # Reject a physically completed shelter visit before authorization, even
    # if a second post-decision visit has been fabricated in the same trace.
    if any(dist(o,shelter)<=stationary_tolerance_m for o in observations if o[0]<absolute[1]):
        raise CausalEvidenceError('shelter visited before the AI checkpoint authorization')
    before=[o for o in observations if absolute[0]+200_000_000 <= o[0] < absolute[1]]
    after=[o for o in observations if absolute[1] <= o[0] <= absolute[2]+2_000_000_000]
    if len(before)<2:
        raise CausalEvidenceError('missing independent checkpoint dwell samples')
    if any(dist(o,station)>stationary_tolerance_m for o in before):
        raise CausalEvidenceError('robot left station while the AI checkpoint was still deciding')
    if len(after)<3 or not any(dist(o,shelter)<=stationary_tolerance_m for o in after):
        raise CausalEvidenceError('no post-authorization shelter arrival observed')
    if not any(dist(o,station)>stationary_tolerance_m for o in after):
        raise CausalEvidenceError('post-authorization movement not observed')
    return {'pass':True,'scope':'WALL_CLOCK_CORRELATED_ROS_TOPIC_TRACE_NOT_AUTHENTICATED_PHYSICS',
            'run_id':m['run_id'],'mission_start_unix_ns':start,
            'event_wall_unix_ns':{'station':absolute[0], 'decision':absolute[1], 'shelter':absolute[2]},
            'position_source':source,
            'stationary_samples_before_decision':len(before),
            'samples_from_decision_to_shelter':len(after)}
