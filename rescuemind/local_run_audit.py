"""Recalculate local checkpoint decisions; never claim Jev/cloud provenance."""
from __future__ import annotations
from .local_vision import validate_result, local_decision, PRIMARY_MODEL, SECONDARY_MODEL

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
    for call,idx in ((a,1),(b,2)):
        validate_result(call,PRIMARY_MODEL if idx==1 or mode=='single' else SECONDARY_MODEL,image_sha,idx)
    computed=local_decision(expected,a,b,dual_model=(mode=='dual'))
    if checkpoint.get('image_sha256')!=image_sha or checkpoint.get('decision')!=computed:
        raise LocalReceiptError('decision or image hash does not match original model outputs')
    return {'pass':True,'mode':mode,'reason':computed['reason'],'allow':computed['allow'],
            'model_diversity':mode=='dual','scope':'SELF_REPORTED_LOCAL_TRANSFORMERS_NOT_GPU_ATTESTATION'}
