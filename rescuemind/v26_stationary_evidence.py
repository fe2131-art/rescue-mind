"""Require stationarity event in the same ROS run before any claimed VLM decision.

Additional provenance constraint: this checks the mission's own chronology;
independent odometry and camera evidence MUST also be audited separately.
"""
from __future__ import annotations
import json, math
from pathlib import Path

class StationaryEvidenceError(ValueError):
    pass


def audit_stationarity(mission: str | Path | dict) -> dict:
    try:
        doc=json.loads(Path(mission).read_text(encoding='utf-8')) if not isinstance(mission,dict) else mission
        if doc.get('run_type') not in ('jev_qwen_live_mission','local_vlm_live_mission'):
            raise StationaryEvidenceError('not a live Jev/Qwen run')
        ev=doc['events']
        if not isinstance(ev,list):
            raise StationaryEvidenceError('events must be a list')
        stages=('camera_aim_aligned','checkpoint_stationary_verified','checkpoint_frame','checkpoint_decision')
        matches={stage:[(i,row) for i,row in enumerate(ev) if row.get('stage')==stage] for stage in stages}
        if any(len(matches[s])!=1 for s in stages):
            raise StationaryEvidenceError('missing or duplicate acquisition event')
        found=[matches[s][0] for s in stages]
        if [idx for idx,_ in found]!=sorted(idx for idx,_ in found):
            raise StationaryEvidenceError('incorrect acquisition event order')
        times=[float(row['t_wall_s']) for _,row in found]
        if not all(math.isfinite(t) and t>=0 for t in times) or times!=sorted(times):
            raise StationaryEvidenceError('non-monotonic mission event times')
        settle=found[1][1]
        if not (0.65 <= float(settle['stable_elapsed_s']) <= 30.0 and
                type(settle['sample_count']) is int and settle['sample_count']>=4 and
                type(settle['reset_count']) is int and settle['reset_count']>=0 and
                float(settle['max_drift_m'])<=0.0201 and
                float(settle['max_yaw_drift_rad'])<=0.0401 and
                float(settle['max_linear_mps'])<=0.0251 and
                float(settle['max_angular_rps'])<=0.0551):
            raise StationaryEvidenceError('stationary gate quality missing/too weak')
        if not (float(settle['stable_elapsed_s']) <= times[1]-times[0]+.05):
            raise StationaryEvidenceError('stationary samples predate alignment')
        if times[2]-times[1]<0.5-0.02:
            raise StationaryEvidenceError('camera frame not sufficiently after stationary gate')
        if not (isinstance(found[2][1].get('image_sha256'),str) and
                len(found[2][1]['image_sha256'])==64 and
                all(c in '0123456789abcdef' for c in found[2][1]['image_sha256'])):
            raise StationaryEvidenceError('missing checkpoint image digest')
        if type(found[3][1].get('allow')) is not bool:
            raise StationaryEvidenceError('missing explicit AI authorization/denial')
        return {'passed':True,'run_id':doc.get('run_id'),
                'stationarity_t_wall_s':times[1], 'frame_t_wall_s':times[2],
                'decision_t_wall_s':times[3], 'samples':settle['sample_count'],
                'caveat':'mission events are self-reported; verify independent odometry and ROS bag'}
    except (OSError,KeyError,TypeError,ValueError,OverflowError) as exc:
        if isinstance(exc,StationaryEvidenceError): raise
        raise StationaryEvidenceError('malformed stationarity receipt: '+str(exc)) from exc
