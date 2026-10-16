"""Recalculate local checkpoint decisions; never claim Jev/cloud provenance."""
from __future__ import annotations
from .local_vision import validate_result, local_decision, combine_with_jev, combine_with_look_around, ALLOWED_MODELS, SECONDARY_MODEL

class LocalReceiptError(ValueError):
    pass

def audit_local_checkpoint(checkpoint: dict, image_sha: str, *, expected: str) -> dict:
    if not isinstance(checkpoint, dict) or checkpoint.get('backend')!='LOCAL_ONLY_NO_CLOUD_API':
        raise LocalReceiptError('not a local-only checkpoint')
    calls=checkpoint.get('model_calls')
    if type(calls) is not dict or set(calls)!= {'first','second'}:
        raise LocalReceiptError('missing local model calls')
    mode=checkpoint.get('mode')
    if mode not in ('single','dual'):
        raise LocalReceiptError('missing local mode')
    a,b=calls['first'],calls['second']
    primary=a.get('model') if isinstance(a,dict) else None
    if primary not in ALLOWED_MODELS or primary==SECONDARY_MODEL:
        raise LocalReceiptError('primary model not on the local allow-list')
    for call,idx in ((a,1),(b,2)):
        validate_result(call,primary if idx==1 or mode=='single' else SECONDARY_MODEL,image_sha,idx)
    computed=local_decision(expected,a,b,dual_model=(mode=='dual'))
    if 'jev_call' in checkpoint:   # I-13: recompute the two-model rule from the saved Jev-role answer
        computed=combine_with_jev(computed,checkpoint['jev_call'],expected,
                                  hazard_threshold=checkpoint.get('jev_hazard_threshold',.35))
    if 'look_around' in checkpoint:   # I-14: side views can only turn an approval into a hazard refusal
        peeks=[]
        for pk in checkpoint['look_around'].get('peeks',[]):
            pa,pb=pk['model_calls']['first'],pk['model_calls']['second']
            for call,idx in ((pa,1),(pb,2)):
                validate_result(call,primary,pk['image_sha256'],idx)
            if 'jev_call' in pk:
                hz=combine_with_jev(local_decision(expected,pa,pb),pk['jev_call'],expected,
                                    hazard_threshold=checkpoint.get('jev_hazard_threshold',.35))['reason']
            else:
                hz=local_decision(expected,pa,pb)['reason']
            if (hz=='visible_hazard_at_checkpoint') != bool(pk.get('hazard')):
                raise LocalReceiptError('look-around hazard flag does not match the saved side-view outputs')
            peeks.append({'side':pk['side'],'hazard':hz=='visible_hazard_at_checkpoint'})
        computed=combine_with_look_around(computed,peeks)
    if checkpoint.get('image_sha256')!=image_sha or checkpoint.get('decision')!=computed:
        raise LocalReceiptError('decision or image hash does not match original model outputs')
    return {'pass':True,'mode':mode,'reason':computed['reason'],'allow':computed['allow'],
            'model_diversity':mode=='dual','scope':'SELF_REPORTED_LOCAL_TRANSFORMERS_NOT_GPU_ATTESTATION'}
