"""Offline internal consistency audit: on-site camera stamp vs Gazebo /clock.

Checks self-reported ROS receipts only. A compromised ROS publisher/JSON may spoof
it; video and actual Gazebo replay are still required for credible evidence.
"""
from __future__ import annotations
import json, math
from pathlib import Path

class ClockEvidenceError(ValueError):
    pass


def audit_clock_capture(mission:dict|Path|str)->dict:
    try:
        if isinstance(mission,(Path,str)):
            mission=json.loads(Path(mission).read_text(encoding='utf8'))
        if mission.get('run_type') not in ('jev_qwen_live_mission','local_vlm_live_mission'):
            raise ClockEvidenceError('not_live_mission')
        events=mission['events']
        if not isinstance(events,list):raise ClockEvidenceError('invalid_events')
        sequence=('checkpoint_stationary_verified','checkpoint_image_quality_verified',
                  'checkpoint_camera_sim_clock_verified','checkpoint_frame','checkpoint_decision')
        matches=[]
        for stage in sequence:
            found=[(i,e) for i,e in enumerate(events) if isinstance(e,dict) and e.get('stage')==stage]
            if len(found)!=1:raise ClockEvidenceError('missing_or_duplicate_'+stage)
            matches.append(found[0])
        indexes=[i for i,_ in matches]
        if indexes!=sorted(indexes):raise ClockEvidenceError('out_of_order_camera_clock_proof')
        timestamps=[]
        for _,e in matches:
            t=e.get('t_wall_s')
            if type(t) not in (int,float) or not math.isfinite(t) or t<0:
                raise ClockEvidenceError('invalid_event_time')
            timestamps.append(t)
        if timestamps!=sorted(timestamps):raise ClockEvidenceError('nonmonotonic_event_time')
        proof=matches[2][1]; quality=matches[1][1]; frame=matches[3][1]
        def integer(k):
            x=proof.get(k)
            if type(x) is not int or x<=0:raise ClockEvidenceError('bad_'+k)
            return x
        camera_ns=integer('camera_ros_stamp_ns'); clock_ns=integer('sim_clock_ns')
        if proof.get('basis')!='Gazebo_clock_vs_camera_ROS_stamp':
            raise ClockEvidenceError('incorrect_clock_time_basis')
        stamps=quality.get('ros_stamps_ns')
        if not isinstance(stamps,list) or len(stamps)!=2 or any(type(x) is not int for x in stamps):
            raise ClockEvidenceError('missing_quality_stamp_pair')
        if camera_ns!=stamps[-1] or camera_ns!=frame.get('ros_acquisition_stamp_ns'):
            raise ClockEvidenceError('camera_clock_stamp_disagrees_with_saved_frame')
        if type(proof.get('clock_advances')) is not int or proof['clock_advances']<2:
            raise ClockEvidenceError('clock_not_advanced')
        limits=proof.get('limits_s')
        if not isinstance(limits,dict):raise ClockEvidenceError('no_clock_limits')
        for k in ('max_lag','max_lead','max_clock_idle'):
            v=limits.get(k)
            if type(v) not in (int,float) or not math.isfinite(v) or v<=0 or v>30:
                raise ClockEvidenceError('invalid_clock_limit_'+k)
        # Enforce the vetted runtime defaults, not attacker-inflated limits.
        if (limits['max_lag']>1.2 or limits['max_lead']>.25 or limits['max_clock_idle']>.9):
            raise ClockEvidenceError('clock_limits_weakened')
        delta=(clock_ns-camera_ns)/1e9
        if delta > limits['max_lag'] or delta < -limits['max_lead']:
            raise ClockEvidenceError('camera_frame_not_near_gazebo_time')
        reported_lag=proof.get('camera_lag_to_sim_clock_s')
        if type(reported_lag) not in (int,float) or not math.isfinite(reported_lag) or abs(reported_lag-delta)>.00011:
            raise ClockEvidenceError('reported_camera_lag_inconsistent')
        idle=proof.get('clock_callback_idle_s')
        if type(idle) not in (int,float) or not math.isfinite(idle) or idle<0 or idle>limits['max_clock_idle']:
            raise ClockEvidenceError('clock_callback_stale')
        progress_idle=proof.get('clock_progress_idle_s')
        if type(progress_idle) not in (int,float) or not math.isfinite(progress_idle) or progress_idle<0 or progress_idle>limits['max_clock_idle']:
            raise ClockEvidenceError('clock_progress_stalled')
        return {'passed':True,'sim_clock_ns':clock_ns,'camera_ros_stamp_ns':camera_ns,
                'lag_s':round(delta,4),'clock_advances':proof['clock_advances'],
                'scope':'self_reported_ROS_clock_and_image_headers_not_simulator_attestation'}
    except (KeyError,ValueError,OSError,TypeError,AttributeError,OverflowError) as exc:
        if isinstance(exc,ClockEvidenceError):raise
        raise ClockEvidenceError('malformed_clock_evidence: '+str(exc)) from exc
