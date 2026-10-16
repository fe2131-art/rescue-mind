"""Verify runtime JSON content before supervisor reports task completion.

Automated log validation is NOT proof that Gazebo or remote models actually ran.
Physical and external API provenance still need independent human review.
"""
from __future__ import annotations
import json
from pathlib import Path

class CompletionError(ValueError):
    pass

def validate(path: Path, scenario: str, expected_run_id: str | None = None) -> dict:
    path=Path(path)
    if not path.is_file():
        raise CompletionError('missing mission.json despite exit code zero')
    try: record=json.loads(path.read_text(encoding='utf-8'))
    except (ValueError,UnicodeError,OSError) as exc:
        raise CompletionError('invalid mission.json') from exc
    if record.get('success') is not True:
        raise CompletionError('mission did not claim successful completion')
    if expected_run_id is not None and record.get('run_id') != expected_run_id:
        raise CompletionError('mission run_id mismatch')
    typ=('local_vlm_live_mission' if record.get('run_type')=='local_vlm_live_mission' and scenario=='live'
         else 'jev_qwen_live_mission' if scenario=='live' else 'motion_check_non_ai')
    if record.get('run_type') != typ:
        raise CompletionError('wrong run_type for requested scenario')
    stages=record.get('events')
    if not isinstance(stages,list) or any(e.get('stage')=='error' for e in stages if isinstance(e,dict)):
        raise CompletionError('missing events or error event in completed mission')
    visits=[e.get('stage') for e in stages if isinstance(e,dict) and e.get('arrived') is True]
    if visits != ['supply_station','shelter_approach']:
        raise CompletionError('missing ordered supply/shelter arrivals')
    if scenario=='live':
        dec=(record.get('checkpoint') or {}).get('decision') or {}
        if dec.get('allow') is not True or dec.get('reason')!='on_site_supply_confirmed':
            raise CompletionError('Jev+Qwen checkpoint did not approve the second leg')
        timeline=[e.get('stage') for e in stages if isinstance(e,dict) and (e.get('arrived') is True or e.get('stage') in ('checkpoint_frame','checkpoint_decision'))]
        if timeline != ['supply_station','checkpoint_frame','checkpoint_decision','shelter_approach']:
            raise CompletionError('checkpoint event order invalid')
        if typ=='local_vlm_live_mission':
            from .local_run_audit import audit_local_checkpoint
            try:
                audit_local_checkpoint(record.get('checkpoint'),
                    next(e for e in stages if isinstance(e,dict) and e.get('stage')=='checkpoint_frame')['image_sha256'],
                    expected=record['intent']['item'])
            except (ValueError, KeyError, TypeError, StopIteration) as exc:
                raise CompletionError('local model evidence failed: '+str(exc)) from exc
        else:
            from scripts.audit_robot_run import audit
            try:
                passed=audit(path)['automated_pass']
            except (ValueError, KeyError, TypeError, OSError) as exc:
                raise CompletionError('full Jev/Qwen log audit could not be recomputed') from exc
            if not passed:
                raise CompletionError('full Jev/Qwen log audit failed')
    return {'software_log_validation':'PASS','scenario':scenario,'run_id':record.get('run_id'),
            'external_provenance_verified':False,'robot_motion_independently_verified':False}
