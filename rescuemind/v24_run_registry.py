"""Bind pre-registered trials to independently checked saved Gazebo run evidence.

Registration is NOT API/physics attestation. It prevents accidental post-hoc
selection, run-ID reuse, altered scene SDF, and missing camera evidence.
"""
from __future__ import annotations
import fcntl
import hashlib
import json
import os
from pathlib import Path
from .v23_protocol import validate_protocol

class RunRegistrationError(ValueError): pass


def proof_for_trial(project_root:Path, protocol:dict,trial_id:str,run_dir:Path)->dict:
    from scripts.v22_audit_trials import evaluate as evaluate_run
    project_root=Path(project_root).resolve();run_dir=Path(run_dir).resolve()
    validate_protocol(protocol)
    trials={r['id']:r for r in protocol['trials']}
    if trial_id not in trials: raise RunRegistrationError('unknown preregistered trial')
    trial=trials[trial_id]
    if run_dir.parent!=project_root/'outputs/runs':
        raise RunRegistrationError('run directory outside outputs/runs')
    if len(run_dir.name)!=16 or any(c not in '0123456789abcdef' for c in run_dir.name):
        raise RunRegistrationError('invalid run folder identifier')
    def read(name):
        try:return json.loads((run_dir/name).read_text(encoding='utf-8'))
        except (ValueError,OSError) as e:raise RunRegistrationError(f'missing/invalid {name}') from e
    plan=read('stack_plan.json');result=read('stack_result.json');mission=read('mission.json')
    if plan.get('scenario')!='live' or plan.get('scene')!=trial['scene']:
        raise RunRegistrationError('scene mismatch with locked trial')
    if result.get('run_id')!=run_dir.name or mission.get('run_id')!=run_dir.name:
        raise RunRegistrationError('run ID mismatch')
    if mission.get('intent',{}).get('item')!=trial['expected']:
        raise RunRegistrationError('supply instruction changed from locked trial')
    sdf=project_root/'worlds/scenarios'/f"rescuemind_{trial['scene']}.sdf"
    digest=hashlib.sha256(sdf.read_bytes()).hexdigest()
    if plan.get('scene_sha256')!=digest:
        raise RunRegistrationError('plan / scene SDF SHA256 mismatch')
    try: audit=evaluate_run(run_dir)
    except (ValueError,OSError,KeyError,TypeError) as e:
        raise RunRegistrationError('ROS evidence audit unavailable') from e
    if not audit['verified']:
        raise RunRegistrationError('independent ROS/AI evidence not sufficient: '+audit['reason'])
    expected='ALLOW_AND_REACHED_SHELTER' if trial['expected_action']=='ALLOW' else 'DENY_AND_STATIONARY'
    if audit['observed']!=expected:
        raise RunRegistrationError('observed behavior not equal to preregistered outcome')
    if trial['expected_action']=='DENY':
        # v2.4 requires the completed post-decision zero-velocity dwell;
        # historical v2.2 FAILED receipts alone are not sufficient.
        from .v24_trial_outcome import classify_negative_run
        own=run_dir/'waypoints.json'      # Study L: per-trial layout waypoints stored in the run folder
        cfg=json.loads((own if own.is_file() else project_root/'configs/gazebo_waypoints.json').read_text())
        try:
            classify_negative_run(run_dir,scene=trial['scene'],run_id=run_dir.name,waypoints=cfg)
        except (ValueError,OSError,KeyError,TypeError) as exc:
            raise RunRegistrationError('incomplete negative trial evidence: '+str(exc)) from exc
        if result.get('state')!='COMPLETED_EXPECTED_DENIAL':
            raise RunRegistrationError('denial outcome not classified by stack supervisor')
    from .v25_evidence import audit_alignment
    audit_alignment(mission)
    events=mission.get('events',[])
    frames=[e for e in events if isinstance(e,dict) and e.get('stage')=='checkpoint_frame']
    if len(frames)!=1 or not isinstance(frames[0].get('image_sha256'),str):
        raise RunRegistrationError('checkpoint camera image evidence missing')
    image=project_root/str(mission.get('checkpoint_image_path',''))
    # Prevent registration of arbitrary files outside the current run folder.
    if image.resolve().parent!=run_dir or not image.is_file():
        raise RunRegistrationError('checkpoint image not inside this run')
    image_hash=hashlib.sha256(image.read_bytes()).hexdigest()
    if frames[0]['image_sha256']!=image_hash:
        raise RunRegistrationError('checkpoint image hash mismatch')
    checkpoint=mission.get('checkpoint')
    if not isinstance(checkpoint,dict) or checkpoint.get('image_sha256')!=image_hash:
        raise RunRegistrationError('AI checkpoint image differs from camera image')
    calls=checkpoint.get('model_calls',{})
    if calls.get('jev',{}).get('model')!='jev-1.14.0' or calls.get('qwen',{}).get('model')!='qwen3.8-omni-flash':
        raise RunRegistrationError('required fixed model IDs missing')
    if calls.get('jev',{}).get('real_model') is not True or calls.get('qwen',{}).get('real_model') is not True:
        raise RunRegistrationError('no live API-labelled checkpoint')
    return {'schema':'rescuemind_v24_registry_v1','trial_id':trial_id,'trial_order':trial['order'],
            'scene':trial['scene'],'expected_supply':trial['expected'],
            'run_id':run_dir.name,'scene_sha256':digest,'checkpoint_sha256':image_hash,
            'observed_behavior':audit['observed'],
            'scope':'INDEPENDENT_ROS_AND_SELF_REPORTED_VLM_RECORDS_NOT_AUTHENTICATED'}


def register(project_root:Path, protocol:dict, trial_id:str,run_dir:Path,registry:Path)->dict:
    record=proof_for_trial(project_root,protocol,trial_id,run_dir)
    registry=Path(registry);registry.parent.mkdir(parents=True,exist_ok=True)
    # Append-only with OS lock to reject duplicate planned trials/run IDs.
    with registry.open('a+',encoding='utf-8') as f:
        fcntl.flock(f.fileno(),fcntl.LOCK_EX)
        try:
            f.seek(0)
            try:existing=[json.loads(line) for line in f if line.strip()]
            except (ValueError,TypeError) as e:raise RunRegistrationError('corrupt registry; refusing append') from e
            if any(x.get('trial_id')==trial_id or x.get('run_id')==record['run_id'] for x in existing):
                raise RunRegistrationError('trial/run already registered; refuse overwrite')
            if any(x.get('checkpoint_sha256')==record['checkpoint_sha256'] for x in existing):
                raise RunRegistrationError('reused checkpoint image across trials')
            f.seek(0,os.SEEK_END)
            f.write(json.dumps(record,ensure_ascii=False,sort_keys=True)+'\n')
            f.flush();os.fsync(f.fileno())
        finally:
            fcntl.flock(f.fileno(),fcntl.LOCK_UN)
    return record
