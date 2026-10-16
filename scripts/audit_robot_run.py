"""Check a JSON mission log for machine-readable progress, not physical authenticity."""
from __future__ import annotations
import argparse
import json
from rescuemind.checkpoint import decide_checkpoint
from rescuemind import jev, qwen35
from pathlib import Path


def audit(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    stages=data.get('events',[])
    visits=[e for e in stages if e.get('arrived') is True]
    names=[e.get('stage') for e in visits]
    is_mission=data.get('run_type') in ('jev_qwen_mission','jev_qwen_live_mission')
    gate=data.get('preflight') or {}
    allow=(gate.get('gate',{}).get('allow') is True if data.get('run_type')=='jev_qwen_mission'
           else data.get('run_type')=='jev_qwen_live_mission' and data.get('intent_gate',{}).get('allow') is True
           and data.get('preflight') is None)
    matched=names==['supply_station','shelter_approach']
    has_telemetry=len(data.get('trace',[]))>=2
    checkpoint=data.get('checkpoint') or {}
    check_dec=checkpoint.get('decision') or {}
    frame_events=[e for e in stages if e.get('stage')=='checkpoint_frame']
    has_valid_sha=(len(frame_events)==1 and isinstance(frame_events[0].get('image_sha256'),str)
                   and len(frame_events[0]['image_sha256'])==64
                   and frame_events[0]['image_sha256']==checkpoint.get('image_sha256'))
    timeline=[e.get('stage') for e in stages if e.get('arrived') is True or e.get('stage') in ('checkpoint_frame','checkpoint_decision')]
    correct_timeline=timeline==['supply_station','checkpoint_frame','checkpoint_decision','shelter_approach']
    approved_checkpoint=check_dec.get('allow') is True and check_dec.get('reason')=='on_site_supply_confirmed'
    model_calls=checkpoint.get('model_calls') or {}
    j = model_calls.get('jev') or {}
    q = model_calls.get('qwen') or {}
    authenticated_jev=j.get('model')==jev.MODEL_ID and j.get('real_model') is True
    authenticated_qwen=q.get('model') in ('qwen3.8-omni-flash',qwen35.DEFAULT_MODEL,qwen35.DEFAULT_MODEL.split('/')[-1]) and q.get('real_model') is True
    expected=(data.get('intent') or {}).get('item')
    reproducible_decision=False
    if expected in ('water','medicine'):
        calc=decide_checkpoint(expected,j,q)
        reproducible_decision=(calc.to_dict()==check_dec)
    timestamps=[e.get('t_wall_s') for e in stages]
    ordered_timestamps=bool(timestamps) and all(isinstance(t,(int,float)) and t>=0 and t<86400 for t in timestamps) and timestamps==sorted(timestamps)
    no_error_event=not any(e.get('stage')=='error' for e in stages)
    checks={'mission_mode_jev_qwen':is_mission,'correct_first_stage_authorization':allow,
            'supply_then_shelter_events':matched,'telemetry_in_record':has_telemetry,
            'on_site_checkpoint_approved':approved_checkpoint,
            'on_site_frame_hash_corresponds_to_decision':has_valid_sha,
            'jev_model_recorded_at_checkpoint':authenticated_jev,
            'qwen_model_recorded_at_checkpoint':authenticated_qwen,
            'checkpoint_recomputed_from_both_model_results':reproducible_decision,
            'monotonic_event_timestamps':ordered_timestamps,
            'no_error_event':no_error_event,
            'checkpoint_between_stages':correct_timeline,
            'software_declared_success':data.get('success') is True,
            'no_physical_pickup_claim':data.get('physical_pickup') is False}
    return {'automated_log_checks':checks,'automated_pass':all(checks.values()),
            'robot_motion_independently_verified':False,
            'manual_evidence_needed':['raw Gazebo screen recording','timestamp continuity','live Jev/Qwen logs','visual proof of navigation','no personally identifying data']}

def main():
    a=argparse.ArgumentParser();a.add_argument('--record',required=True);a.add_argument('--out',default='outputs/gazebo_evidence_audit.json');v=a.parse_args()
    report=audit(v.record)
    p=Path(v.out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))
    raise SystemExit(0 if report['automated_pass'] else 2)
if __name__=='__main__':main()
