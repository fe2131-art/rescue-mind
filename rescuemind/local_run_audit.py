"""Recalculate local checkpoint decisions; never claim Jev/cloud provenance."""
from __future__ import annotations
from .local_vision import V36_HAZARD_THRESHOLD, check_hazard_threshold, LocalInferenceError, validate_result, local_decision, combine_with_jev, combine_with_look_around, ALLOWED_MODELS, SECONDARY_MODEL

class LocalReceiptError(ValueError):
    pass

def audit_local_checkpoint(checkpoint: dict, image_sha: str, *, expected: str,
                           hazard_threshold: float | None = V36_HAZARD_THRESHOLD, require_threshold: bool = False) -> dict:
    """`hazard_threshold`: the tau_h the server must have used (I-19 fix #27); a recorded value that differs is always
    rejected, a missing record only if `require_threshold` (the interlock; saved runs from before the fix lack it)."""
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
    thr_ok=[]
    try:
        thr_ok+=[check_hazard_threshold(c,hazard_threshold,require=require_threshold) for c in (a,b)]
    except LocalInferenceError as e:
        raise LocalReceiptError('hazard threshold: '+str(e)) from e
    computed=local_decision(expected,a,b,dual_model=(mode=='dual'))
    if 'jev_call' in checkpoint:   # I-13: recompute the two-model rule from the saved Jev-role answer
        computed=combine_with_jev(computed,checkpoint['jev_call'],expected,
                                  hazard_threshold=checkpoint.get('jev_hazard_threshold',.35))
    from .mission_memory import apply_memory_caution, peek_hazard, scores_valid
    if not (scores_valid(a) and scores_valid(b)):   # I-19 fix: the front check's hazard scores must be usable (fail closed)
        raise LocalReceiptError('front check without valid hazard scores')
    tau_mem=checkpoint.get('memory_caution_tau_h')   # I-15: memory may only tighten the hazard threshold
    if tau_mem is not None and not (isinstance(tau_mem,float) and 0 < tau_mem < .05):
        raise LocalReceiptError('memory caution threshold must be stricter than the v3.6 threshold')
    base_reason=computed['reason']        # what the standard (v3.6) rule says at the front, before any memory / advice caution
    computed=apply_memory_caution(computed,a,b,tau_mem)
    hard_hazard=(base_reason=='visible_hazard_at_checkpoint')    # R5 #5: a real hazard (p >= tau_h, or either model's label)
    if 'look_around' in checkpoint:   # I-14: side views can only turn an approval into a hazard refusal
        peeks=[]
        for pk in checkpoint['look_around'].get('peeks',[]):
            pa,pb=pk['model_calls']['first'],pk['model_calls']['second']
            for call,idx in ((pa,1),(pb,2)):
                validate_result(call,primary,pk['image_sha256'],idx)
            try:
                thr_ok+=[check_hazard_threshold(c,hazard_threshold,require=require_threshold) for c in (pa,pb)]
            except LocalInferenceError as e:
                raise LocalReceiptError('hazard threshold (side view): '+str(e)) from e
            if 'jev_call' in pk:
                hz=combine_with_jev(local_decision(expected,pa,pb),pk['jev_call'],expected,
                                    hazard_threshold=checkpoint.get('jev_hazard_threshold',.35))['reason']
            else:
                hz=local_decision(expected,pa,pb)['reason']
            hazard=peek_hazard(hz,pa,pb,tau_mem)
            if hazard != bool(pk.get('hazard')):
                raise LocalReceiptError('look-around hazard flag does not match the saved side-view outputs')
            hard_hazard=hard_hazard or hz=='visible_hazard_at_checkpoint' or not (scores_valid(pa) and scores_valid(pb))
            peeks.append({'side':pk['side'],'hazard':hazard})
        ad=checkpoint['look_around'].get('adaptive')
        if ad is not None:   # I-20: recompute whether the extra views were required, and that they were taken
            from .adaptive_views import suspicion
            std=[pk for pk in checkpoint['look_around'].get('peeks',[]) if pk['side'] in ('L','R')]
            p_max=suspicion(checkpoint,std)
            extra=[pk for pk in checkpoint['look_around'].get('peeks',[]) if pk['side'] in ('L2','R2','N')]
            # an extra view that flagged a hazard legitimately ends the extra views early (I-23 finding F1: L/R only was
            # checked, so a run refused at the first or second extra view failed the audit)
            hazard_std=any(q['hazard'] for q in peeks)
            if abs(p_max-float(ad.get('p_max',-1)))>1e-3:
                raise LocalReceiptError('adaptive-view suspicion does not match the saved outputs')
            if (not hazard_std and computed.get('allow') is not False and (p_max>=float(ad['tau_sus']) or ad.get('scrutiny'))
                    and len(extra)<3):
                raise LocalReceiptError('suspicious station approved without the extra views (I-20)')
        computed=combine_with_look_around(computed,peeks)
    if checkpoint.get('image_sha256')!=image_sha or checkpoint.get('decision')!=computed:
        raise LocalReceiptError('decision or image hash does not match original model outputs')
    # R5 #5: a refusal with no real hazard behind it, only the tightened threshold (memory / advice caution)
    caution_only=(computed['allow'] is False and computed['reason']=='visible_hazard_at_checkpoint' and not hard_hazard)
    return {'pass':True,'mode':mode,'reason':computed['reason'],'allow':computed['allow'],'caution_only':caution_only,
            'hazard_threshold':hazard_threshold,'hazard_threshold_verified':bool(thr_ok) and all(thr_ok),
            'model_diversity':mode=='dual','scope':'SELF_REPORTED_LOCAL_TRANSFORMERS_NOT_GPU_ATTESTATION'}
