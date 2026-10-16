"""Fail-closed audit of ROS image quality receipts and saved bytes.

Self-reported ROS timestamps are not cryptographically authenticated. This
checks internal consistency and the checkpoint JPEG hash, not camera truth.
"""
from __future__ import annotations
import hashlib,json,math
from pathlib import Path

class ImageEvidenceError(ValueError):
    pass


def audit_capture(mission_path:str|Path, checkpoint_path:str|Path)->dict:
    try:
        mission=json.loads(Path(mission_path).read_text(encoding='utf-8'))
        if mission.get('run_type') not in ('jev_qwen_live_mission','local_vlm_live_mission'):
            raise ImageEvidenceError('non_live_mission')
        events=mission['events']
        wanted=('checkpoint_stationary_verified','checkpoint_image_quality_verified',
                'checkpoint_frame','checkpoint_decision')
        selected=[]
        for stage in wanted:
            rows=[(idx,e) for idx,e in enumerate(events) if isinstance(e,dict) and e.get('stage')==stage]
            if len(rows)!=1:
                raise ImageEvidenceError('missing_or_duplicate_'+stage)
            selected.append(rows[0])
        if [i for i,_ in selected]!=sorted(i for i,_ in selected):
            raise ImageEvidenceError('image_events_out_of_order')
        ts=[float(e['t_wall_s']) for _,e in selected]
        if not all(math.isfinite(x) and x>=0 for x in ts) or ts!=sorted(ts):
            raise ImageEvidenceError('event_times_invalid')
        quality_event=selected[1][1]
        stamps=quality_event['ros_stamps_ns']
        if (not isinstance(stamps,list) or len(stamps)!=2 or
            any(type(i) is not int or i<=0 for i in stamps) or stamps[1]<=stamps[0] or
            quality_event.get('distinct_frames')!=2):
            raise ImageEvidenceError('not_two_distinct_acquisitions')
        gap=float(quality_event['capture_gap_wall_s'])
        if not math.isfinite(gap) or not .149<=gap<=30.0:
            raise ImageEvidenceError('insufficient_camera_capture_gap')
        if ts[1]-ts[0]<.48:
            raise ImageEvidenceError('camera_quality_observation_too_soon_after_stop')
        q=quality_event['image_quality']
        if q.get('quality_ok') is not True or q.get('reasons') != []:
            raise ImageEvidenceError('camera_quality_not_verified')
        if not(320<=int(q['width'])<=4096 and 240<=int(q['height'])<=4096 and
               0<=int(q['p01_luma'])<=int(q['p99_luma'])<=255 and
               int(q['p99_luma'])-int(q['p01_luma'])>=4 and
               0<=float(q['dark_fraction'])<.99 and 0<=float(q['bright_fraction'])<.99):
            raise ImageEvidenceError('camera_quality_metrics_invalid')
        frame=selected[2][1]
        if frame.get('ros_acquisition_stamp_ns')!=stamps[-1]:
            raise ImageEvidenceError('saved_frame_stamp_does_not_match_quality_gate')
        checkpoint=Path(checkpoint_path)
        if not checkpoint.is_file() or checkpoint.stat().st_size<=300:
            raise ImageEvidenceError('checkpoint_image_missing_or_small')
        expected=frame.get('image_sha256')
        digest=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        if digest!=expected:
            raise ImageEvidenceError('checkpoint_image_hash_mismatch')
        if type(selected[3][1].get('allow')) is not bool:
            raise ImageEvidenceError('decision_not_explicit')
        return {'passed':True,'run_id':mission.get('run_id'),'two_acquisitions':2,
                'stamp_pair_ns':stamps,'capture_gap_wall_s':gap,
                'checkpoint_sha256':digest,'quality':q,
                'scope':'self_reported_ROS_stamp_and_hashed_bytes_not_real_Gazebo_proof'}
    except (OSError,KeyError,TypeError,ValueError,OverflowError,AttributeError) as exc:
        if isinstance(exc,ImageEvidenceError):raise
        raise ImageEvidenceError('malformed_image_receipt: '+str(exc)) from exc
