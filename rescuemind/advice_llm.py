"""I-19: operator advice extracted from the instruction text with the on-board model.

The same local model that parses the request (rescuemind.intent_llm) answers three closed-set questions about the
text (server endpoint /v1/advice; answer-letter probabilities from one forward pass each, no free text):

  Q_loc  : where does the message say the requested supply is?  {W station, M station, not stated}
  Q_haz  : does it report fire/smoke at a station?               {W, M, none}
  Q_safe : does it claim a place is safe / already checked, or ask to skip the check?  {Yes, No}

An answer becomes an advice item (source 'operator') only if it is the argmax AND p >= MIN_P (0.6).  Fail-closed:
on ANY error (server down, bad provenance, schema) there are NO advice items.  Advice can therefore only be ignored by
mistake, never invented by an error.  The items are then handled by rescuemind.advice: in monotone mode they can only
reorder or tighten, so a wrongly extracted (or maliciously phrased) item cannot relax a check.

A message cannot both report a fire and claim there is none: if Q_haz and Q_safe both pass the threshold, only the
one with the higher probability is kept.
"""
from __future__ import annotations
import json
import urllib.request

from . import advice as adv
from .local_vision import PRIMARY_MODEL, LocalInferenceError, localhost_only

DEFAULT_ADVICE_URL = 'http://127.0.0.1:8765/v1/advice'
MIN_P = 0.60
STATION_OF = {'water': 'water', 'medicine': 'medicine'}


def query(text: str, *, url: str = DEFAULT_ADVICE_URL, model: str = PRIMARY_MODEL, timeout: int = 60,
          transport=None) -> dict:
    localhost_only(url, path='/v1/advice')
    payload = {'model': model, 'text': text}
    if transport is None:
        req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode('utf8'),
                                     headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=timeout) as f:
            resp = json.loads(f.read(16384).decode('utf8'))
    else:
        resp = transport(url, payload)
    if resp.get('model') != model or resp.get('real_inference') is not True or resp.get('text') != text:
        raise LocalInferenceError('advice response provenance mismatch')
    lp, hp, sp = resp.get('loc_probs'), resp.get('haz_probs'), resp.get('safe_probs')
    if not (isinstance(lp, dict) and set(lp) == {'water', 'medicine', 'none'}
            and isinstance(hp, dict) and set(hp) == {'water', 'medicine', 'none'}
            and isinstance(sp, dict) and set(sp) == {'yes', 'no'}):
        raise LocalInferenceError('advice response schema')
    for d in (lp, hp, sp):
        if not all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in d.values()):
            raise LocalInferenceError('advice response probabilities')
    return resp


def items_from_probs(loc: dict, haz: dict, safe: dict, *, min_p: float = MIN_P) -> list[dict]:
    """Pure conversion of the three probability tables into advice items (source 'operator')."""
    out = []
    k = max(loc, key=loc.get)
    if k in STATION_OF and loc[k] >= min_p:
        out.append({'source': 'operator', 'kind': 'location', 'station': STATION_OF[k], 'text': '依頼文：物資の場所'})
    hk = max(haz, key=haz.get)
    has_haz = hk in STATION_OF and haz[hk] >= min_p
    has_safe = safe['yes'] >= min_p and safe['yes'] > safe['no']
    if has_haz and has_safe:
        if haz[hk] >= safe['yes']:
            has_safe = False
        else:
            has_haz = False
    if has_haz:
        out.append({'source': 'operator', 'kind': 'hazard', 'station': STATION_OF[hk], 'text': '依頼文：火災の報告'})
    if has_safe:
        out.append({'source': 'operator', 'kind': 'skip', 'station': None, 'text': '依頼文：安全の主張・確認の省略'})
    return adv.validate(out)


def extract(text: str, **kw) -> dict:
    """Advice items found in the instruction text.  Never raises: any error -> no items (recorded in 'error')."""
    try:
        r = query(text, **kw)
        return {'items': items_from_probs(r['loc_probs'], r['haz_probs'], r['safe_probs']),
                'probs': {'loc': r['loc_probs'], 'haz': r['haz_probs'], 'safe': r['safe_probs']}, 'error': None}
    except Exception as e:      # fail closed: no advice rather than a guessed one
        return {'items': [], 'probs': None, 'error': f'{type(e).__name__}: {str(e)[:160]}'}


def plan_for_mission(item: str, base: dict | None, *, mode: str, advice_file: str | None = None,
                     from_instruction: bool = False, instruction: str = '', extract_fn=extract, **kw) -> dict | None:
    """Combine the advice file and the operator text with the memory plan `base`.  Returns the new plan
    (with plan['advice']) or None when no advice source is configured.  The file is loaded strictly (a malformed
    file is an error, not silently ignored: the experimenter must know)."""
    if not advice_file and not from_instruction:
        return None
    items = adv.load(advice_file) if advice_file else []
    extraction = None
    if from_instruction and mode != 'off':
        extraction = extract_fn(instruction, **kw)
        items = items + extraction['items']
    plan = adv.plan(item, items, mode, base=base)
    plan['advice']['channels'] = {'file': bool(advice_file), 'instruction': bool(from_instruction)}
    if extraction is not None:
        plan['advice']['extraction'] = {'probs': extraction['probs'], 'error': extraction['error'],
                                        'n_items': len(extraction['items'])}
    return plan
