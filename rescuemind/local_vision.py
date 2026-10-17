"""Local-only, fail-closed vision checkpoint for a GPU workstation.

Single: Qwen2.5-VL-3B is asked two different questions; this is ONE model,
NOT two independent safety votes. Dual: optional SmolVLM2 independent model.
Neither mode proves cargo pickup or a safe passage to the shelter.
"""
from __future__ import annotations
import base64
import hashlib
import json
import math
import re
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

PRIMARY_MODEL = 'Qwen/Qwen2.5-VL-3B-Instruct'
SECONDARY_MODEL = 'HuggingFaceTB/SmolVLM2-2.2B-Instruct'
# I-08 candidates (Apache-2.0, newer generations); selection is evidence-based (IMPROVEMENT_LOG.md)
CANDIDATE_MODELS = ('Qwen/Qwen3-VL-8B-Instruct', 'Qwen/Qwen3.5-9B', 'Qwen/Qwen3.5-4B')
ALLOWED_MODELS = frozenset((PRIMARY_MODEL, SECONDARY_MODEL) + CANDIDATE_MODELS)
DEFAULT_PRIMARY_URL = 'http://127.0.0.1:8765/v1/classify'
DEFAULT_SECONDARY_URL = 'http://127.0.0.1:8766/v1/classify'
LABELS = ('water', 'medicine', 'other')
SCENES = ('clear', 'hazard', 'unknown')

class LocalInferenceError(ValueError):
    pass


def localhost_only(url: str, path='/v1/classify') -> str:
    p = urlparse(url)
    if p.scheme != 'http' or p.hostname not in ('127.0.0.1', 'localhost') or p.username or p.password or p.query or p.fragment or p.path != path or not p.port:
        raise LocalInferenceError('local vision endpoint must be a loopback HTTP URL at '+path)
    return url


def parse_model_json(text: str) -> dict:
    if type(text) is not str or len(text)>2000:
        raise LocalInferenceError('missing/excessive generated text')
    cleaned=re.sub(r'^```(?:json)?\s*|\s*```$', '',text.strip(),flags=re.I).strip()
    try:
        obj=json.loads(cleaned)
    except (ValueError,TypeError) as e:
        raise LocalInferenceError('VLM did not return strict JSON') from e
    if (type(obj) is not dict or set(obj) != {'supply','scene'}
            or obj['supply'] not in LABELS or obj['scene'] not in SCENES):
        raise LocalInferenceError('out-of-vocabulary or extra VLM fields')
    return obj


def validate_result(data: dict, model_id: str, image_sha: str, pass_id: int) -> dict:
    if (type(data) is not dict or data.get('model') != model_id
            or data.get('backend') != 'local_transformers'
            or data.get('real_inference') is not True
            or data.get('image_sha256') != image_sha
            or data.get('pass_id') != pass_id):
        raise LocalInferenceError('local response provenance/model/image mismatch')
    result = data.get('result')
    if type(result) is not dict or set(result)!= {'supply','scene'}:
        raise LocalInferenceError('bad classification schema')
    if result['supply'] not in LABELS or result['scene'] not in SCENES:
        raise LocalInferenceError('invalid classification value')
    return result


V36_HAZARD_THRESHOLD = 0.05    # the v3.6 rule's tau_h: the server flag --hazard-threshold must have been started with it
THRESHOLD_TOL = 1e-9


def check_hazard_threshold(call: dict, expected, *, require: bool = True) -> bool:
    """I-19 fix (FINDINGS #27): the decision's tau_h is the SERVER's hazard threshold (default 0.5!), reported in
    scores.hazard_threshold.  The client verifies that every model call was made under the configured threshold.
    A different value always raises; a missing record raises if `require` (live calls always carry it; only
    pre-I-19 saved runs lack the field, and the audit then reports `hazard_threshold_verified: False`).
    `expected=None` disables the check explicitly.  Returns True iff the call carried a matching threshold."""
    if expected is None:
        return False
    sc = (call or {}).get('scores') if isinstance(call, dict) else None
    thr = sc.get('hazard_threshold') if isinstance(sc, dict) else None
    if thr is None:
        if require:
            raise LocalInferenceError('model call does not record the server hazard threshold')
        return False
    if (isinstance(thr, bool) or not isinstance(thr, (int, float)) or not math.isfinite(thr)
            or abs(float(thr) - float(expected)) > THRESHOLD_TOL):
        raise LocalInferenceError(f'server hazard threshold {thr!r} != configured {expected!r}')
    return True


def require_valid_scores(call: dict) -> None:
    """I-19 fix (FINDINGS #26): every model call must carry a usable p(hazard); otherwise the inference is rejected
    (the mission aborts without a delivery) instead of the view silently counting as clear."""
    from .mission_memory import scores_valid
    if not scores_valid(call):
        raise LocalInferenceError('model call without a valid hazard score (finite, in [0,1])')


def _client_call(url: str, model: str, image_bytes: bytes, pass_id: int, *, timeout: int=120, transport=None) -> dict:
    localhost_only(url)
    if model not in ALLOWED_MODELS:
        raise LocalInferenceError('unapproved local model')
    image_sha = hashlib.sha256(image_bytes).hexdigest()
    payload={'model':model,'pass_id':pass_id, 'image_sha256':image_sha,
             'image_base64':base64.b64encode(image_bytes).decode('ascii')}
    if transport is None:
        request=urllib.request.Request(url,data=json.dumps(payload).encode('utf8'),
                                       headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(request,timeout=timeout) as f:
            response=json.loads(f.read(8192).decode('utf8'))
    else:
        response=transport(url,payload)
    validate_result(response,model,image_sha,pass_id)
    return response


# Pre-registered on the Gazebo development set (experiments/PREREGISTRATION_v33.md)
# BEFORE the 30-trial closed-loop test: true positives had min-of-passes
# p(requested) >= 0.569, negatives <= 0.019.  0.50 = requested label must hold a
# majority of the closed-set probability in BOTH passes.
MIN_CONFIDENCE = 0.50


def _confidence(response: dict, expected: str):
    scores = response.get('scores')
    if not isinstance(scores, dict):
        return None
    probs = scores.get('supply_probs')
    v = probs.get(expected) if isinstance(probs, dict) else None
    # I-23 findings F2/F3: a bool or a non-finite / out-of-range confidence is malformed (NaN passed `c < 0.5` as confident)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0.0 <= v <= 1.0:
        raise LocalInferenceError('malformed closed-set scores')
    return float(v)


def local_decision(expected: str, first: dict, second: dict, *, dual_model: bool=False,
                   min_confidence: float=MIN_CONFIDENCE) -> dict:
    if expected not in ('water','medicine'):
        raise LocalInferenceError('unsupported supply')
    for response in (first,second):
        if (response.get('backend') != 'local_transformers' or response.get('real_inference') is not True
                or response.get('model') not in ALLOWED_MODELS or type(response.get('result')) is not dict):
            raise LocalInferenceError('unverified local model result')
        if response['result'].get('supply') not in LABELS or response['result'].get('scene') not in SCENES:
            raise LocalInferenceError('unsupported model label')
    if dual_model and first['model'] == second['model']:
        raise LocalInferenceError('dual-model claim without distinct models')
    if first['image_sha256'] != second['image_sha256']:
        raise LocalInferenceError('two decisions are from different images')
    a,b=first['result'],second['result']
    confidence=[_confidence(r,expected) for r in (first,second)]
    if 'hazard' in (a['scene'],b['scene']):
        reason='visible_hazard_at_checkpoint'
    elif a['supply']!=expected or b['supply']!=expected:
        reason='local_vlm_disagree_or_wrong_supply'
    elif any(c is not None and c < min_confidence for c in confidence):
        reason='low_confidence_supply_match'
    else:
        reason='on_site_supply_confirmed'
    return {'allow':reason == 'on_site_supply_confirmed', 'reason':reason,
            'expected':expected,'first_supply':a['supply'],'second_supply':b['supply'],
            'first_confidence':confidence[0],'second_confidence':confidence[1],
            'min_confidence':min_confidence,
            'model_diversity':dual_model,
            'limitations':'Supply identity only. Unknown corridor != corridor proven safe. No cargo pickup.'}


JEV_ROLE_MODEL = 'Cloudflare/clef-flash'


def combine_with_jev(q_decision: dict, j: dict, expected: str, *, hazard_threshold: float = .35) -> dict:
    """I-13: the original plan's two-AI rule (rescuemind.checkpoint.decide_checkpoint), locally.

    Approve only when BOTH the Qwen checkpoint and the Jev-role model (Clef-Flash answering the original Jev
    request) approve.  Refusal reasons keep the mission's semantics: a hazard seen by EITHER model stops the
    robot without search; a wrong/missing supply seen by either allows the one-time recovery search; anything
    else is low confidence (stop).  Deterministic, so post-run audits can recompute it.
    """
    if j.get('model') != JEV_ROLE_MODEL or j.get('real_model') is not True:
        raise LocalInferenceError('unverified Jev-role result')
    jhaz = j['hazard_probability'] >= hazard_threshold or j['scene'] == 'hazard'
    jsupply_ok = j['supply'] == expected
    jconfident = j['supply_confidence'] >= .65 and j['supply_present_probability'] >= .80
    q = q_decision['reason']
    if q == 'visible_hazard_at_checkpoint' or jhaz:
        reason = 'visible_hazard_at_checkpoint'
    elif q == 'local_vlm_disagree_or_wrong_supply' or not jsupply_ok:
        reason = 'local_vlm_disagree_or_wrong_supply'
    elif q == 'low_confidence_supply_match' or not jconfident:
        reason = 'low_confidence_supply_match'
    else:
        reason = 'on_site_supply_confirmed'
    return {**q_decision, 'allow': reason == 'on_site_supply_confirmed', 'reason': reason, 'qwen_reason': q,
            'jev_role': {'model': JEV_ROLE_MODEL, 'supply': j['supply'], 'supply_confidence': j['supply_confidence'],
                         'supply_present_probability': j['supply_present_probability'],
                         'hazard_probability': j['hazard_probability'], 'scene': j['scene'],
                         'hazard_threshold': hazard_threshold, 'hazard': jhaz}}


def combine_with_look_around(front_decision: dict, peeks: list) -> dict:
    """I-14: after an approving front check the robot looks again from beside the station; a hazard seen from ANY
    side view turns the approval into a hazard refusal (no search).  Supply answers from side views are ignored
    (the supply may be out of view there).  Deterministic, so audits can recompute it."""
    sides = [p['side'] for p in peeks if p.get('hazard')]
    if not sides or not front_decision.get('allow'):
        return front_decision
    return {**front_decision, 'allow': False, 'reason': 'visible_hazard_at_checkpoint',
            'front_reason': front_decision['reason'], 'look_around_hazard_sides': sides}


def verify_station_local(image_path: str | Path, expected: str, *,
                         mode: str='single', primary_url: str=DEFAULT_PRIMARY_URL,
                         secondary_url: str=DEFAULT_SECONDARY_URL,
                         primary_model: str=PRIMARY_MODEL, secondary_model: str=SECONDARY_MODEL,
                         transport=None, jev_url: str | None = None, jev_hazard_threshold: float = .35,
                         jev_schema: str = 'jev', hazard_threshold: float | None = V36_HAZARD_THRESHOLD) -> dict:
    """Use only real local HTTP inference in production; injection is unit-test only."""
    if mode not in ('single','dual'):
        raise LocalInferenceError('mode must be single or dual')
    image=Path(image_path)
    if not image.is_file() or image.stat().st_size<300:
        raise LocalInferenceError('missing on-site ROS camera JPEG')
    from PIL import Image
    with Image.open(image) as im:
        im.verify()
    raw=image.read_bytes()
    first=_client_call(primary_url,primary_model,raw,1,transport=transport)
    second=_client_call(secondary_url if mode=='dual' else primary_url,
                        secondary_model if mode=='dual' else primary_model,raw,2,transport=transport)
    for call in (first,second):
        require_valid_scores(call)
        check_hazard_threshold(call,hazard_threshold)     # I-19 fix #27: never silently run under the server default 0.5
    decision=local_decision(expected,first,second,dual_model=mode=='dual')
    out={'checkpoint_type':'local_on_site_camera_supply_check',
         'image_sha256':hashlib.sha256(raw).hexdigest(),
         'backend':'LOCAL_ONLY_NO_CLOUD_API', 'mode':mode,
         'model_calls':{'first':first,'second':second}, 'decision':decision,
         'limitations':'The two prompts in single mode use the SAME model. Model confidence and physical safety are not established.'}
    if jev_url:
        # I-13: second, differently trained model in the original plan's Jev role (fail closed on any error)
        from .clef_local import infer as clef_infer
        try:
            jev_call=clef_infer(image, jev_url, schema=jev_schema)   # 'task' = the T2-evaluated task wording
        except Exception as exc:
            raise LocalInferenceError(f'Jev-role model failed: {exc}') from exc
        out['jev_call']=jev_call
        out['jev_hazard_threshold']=jev_hazard_threshold
        out['jev_schema']=jev_schema
        out['decision']=combine_with_jev(decision, jev_call, expected, hazard_threshold=jev_hazard_threshold)
        out['limitations']='Two differently trained local models (Qwen + Clef-Flash in the Jev role); not a safety certification.'
    return out


DEFAULT_DESCRIBE_URL = 'http://127.0.0.1:8765/v1/describe'


def describe_station_local(image_path: str | Path, *, url: str = DEFAULT_DESCRIBE_URL,
                           model: str = PRIMARY_MODEL, timeout: int = 60, transport=None) -> dict:
    """I-03: ask the local VLM for a one-sentence Japanese report of what it sees.

    Explanation only — the allow/deny decision never reads this text.
    """
    localhost_only(url, path='/v1/describe')
    raw = Path(image_path).read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    payload = {'model': model, 'image_sha256': sha, 'image_base64': base64.b64encode(raw).decode('ascii')}
    if transport is None:
        request = urllib.request.Request(url, data=json.dumps(payload).encode('utf8'),
                                         headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(request, timeout=timeout) as f:
            response = json.loads(f.read(16384).decode('utf8'))
    else:
        response = transport(url, payload)
    text = response.get('text_ja')
    if (response.get('model') != model or response.get('image_sha256') != sha or response.get('real_inference') is not True
            or not isinstance(text, str) or not text.strip() or len(text) > 120):
        raise LocalInferenceError('invalid local explanation response')
    return {'text_ja': text.strip(), 'image_sha256': sha, 'model': model,
            'purpose': 'explanation_only_not_decision'}
