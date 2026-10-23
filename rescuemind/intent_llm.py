"""I-04: instruction understanding with the on-board LLM (same local Qwen2.5-VL-3B).

The model answers two closed-set questions about the request (which supply, which
destination); answer-letter probabilities are read from one forward pass each, so
there is no free text to parse.  Decision (fail-closed):
  * supply  = argmax over {water, medicine, both, none}; accept only water/medicine with p >= 0.60
  * destination 'elsewhere' (argmax) -> reject; 'unstated' -> project default shelter B
`decide_intent_hybrid` adds the deterministic shelter-name guard from mission_policy
(an explicit 避難所A/C/…/shelter X is always refused, whatever the model says).
"""
from __future__ import annotations
import json
import urllib.request

from .local_vision import PRIMARY_MODEL, LocalInferenceError, localhost_only

DEFAULT_INTENT_URL = 'http://127.0.0.1:8765/v1/intent'
MIN_ITEM_P = 0.60


def query(text: str, *, url: str = DEFAULT_INTENT_URL, model: str = PRIMARY_MODEL, timeout: int = 60,
          transport=None) -> dict:
    localhost_only(url, path='/v1/intent')
    payload = {'model': model, 'text': text}
    if transport is None:
        req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode('utf8'),
                                     headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=timeout) as f:
            resp = json.loads(f.read(16384).decode('utf8'))
    else:
        resp = transport(url, payload)
    if resp.get('model') != model or resp.get('real_inference') is not True or resp.get('text') != text:
        raise LocalInferenceError('intent response provenance mismatch')
    ip, dp = resp.get('item_probs'), resp.get('dest_probs')
    if not (isinstance(ip, dict) and set(ip) == {'water', 'medicine', 'both', 'none'}
            and isinstance(dp, dict) and set(dp) == {'B', 'other', 'unstated'}):
        raise LocalInferenceError('intent response schema')
    return resp


def parse_instruction_llm(text: str, **kw) -> dict:
    r = query(text, **kw)
    ip, dp = r['item_probs'], r['dest_probs']
    item = max(ip, key=ip.get)
    dest = max(dp, key=dp.get)
    probs = {'item': ip, 'dest': dp}
    if item == 'both':
        return {'accept': False, 'item': None, 'reason': 'ambiguous_multiple_supplies', 'probs': probs}
    if item == 'none':
        return {'accept': False, 'item': None, 'reason': 'no_supported_supply', 'probs': probs}
    if ip[item] < MIN_ITEM_P:
        return {'accept': False, 'item': None, 'reason': 'low_llm_confidence', 'probs': probs}
    if dest == 'other':
        return {'accept': False, 'item': None, 'reason': 'unsupported_shelter', 'probs': probs}
    verify = r.get('verify_probs')
    if verify is not None:
        probs['verify'] = verify
        # i36: second, differently worded Yes/No question must agree with the first answer
        if not isinstance(verify.get(item), (int, float)) or verify[item] < 0.5:
            return {'accept': False, 'item': None, 'reason': 'llm_self_check_disagrees', 'probs': probs}
    return {'accept': True, 'item': item, 'shelter': 'B', 'reason': 'llm_intent_accepted', 'probs': probs}


# I-27 (study IF: a request text switched the parsed supply in 12/36 flip texts).  The requested supply is a COMMAND, not
# advice, so it cannot be 'tightened'; the safe response to a text that names both supplies, or whose other supply keeps
# real probability, is to ask the operator back before moving.  Default off (v3.6); rule fixed before its evaluation (IF2).
import re as _re
WATER_ANY = _re.compile(r'(飲料水|給水|水分|水(?!準|平|道)|飲み水|飲み物|ペットボトル|\bwater\b|\bdrinking\b|\bbottled\b)', _re.I)
MEDICINE_ANY = _re.compile(r'(医療|医薬|救急|応急|薬|包帯|絆創膏|ガーゼ|消毒|止血|first[- ]?aid|\bmedic|\bbandage|\bantiseptic)', _re.I)
CONFLICT_OTHER_P = 0.05


def supply_conflict(text: str, probs: dict | None = None, item: str | None = None) -> str | None:
    """Why the request must be confirmed before acting, or None: both supplies named in the text (lexical), or the
    model gives the other supply p >= CONFLICT_OTHER_P."""
    if WATER_ANY.search(text or '') and MEDICINE_ANY.search(text or ''):
        return 'both_supplies_named'
    ip = (probs or {}).get('item') or {}
    other = {'water': 'medicine', 'medicine': 'water'}.get(item)
    if other and isinstance(ip.get(other), (int, float)) and ip[other] >= CONFLICT_OTHER_P:
        return 'other_supply_probable'
    return None


# I-102 (study IG: 4 of 136 fresh texts named a destination the mission does not know and were read as requests for shelter B, because the shelter rule
# only refuses the names it lists).  The mission has ONE destination, shelter B: a text that names another place is a request the robot cannot serve,
# so it is sent back to the operator.  A text that names shelter B itself is not touched (the shelter may be a gymnasium), and one that names no place at all stays valid.
# Default off (v3.6); the rule was written from the principle "a named place other than B", before the fresh set of study IH exists.
PLACE_JA = r'(?:公民館|市役所|区役所|役場|消防署|警察署|小学校|中学校|高校|学校|大学|体育館|病院|診療所|クリニック|医院|救護所|駅|公園|空港|自宅|お宅|実家|会館|ホール|センター|ホテル|旅館|寺|神社|教会|保育園|幼稚園|テント|仮設|倉庫|工場|校庭|広場|港|避難場所|集会所|町内会|本部|コンビニ|スーパー|ショッピング|老人ホーム|福祉|施設)'
ORIENT_JA = r'(?:[東西南北]側?|第[一二三四五六七八九十0-9０-９]+|[0-9０-９]+番(?:目)?|[一二三四五六七八九十]つ目|別の|他の|ほかの|もう一つの|もう1つの|隣の|となりの|新しい|大きい|奥の|向こうの|反対側の)\s*の?\s*(?:避難所|シェルター|避難場所)'
NUMBERED_JA = r'(?:避難所|シェルター|避難場所)\s*(?:第?[0-9０-９一二三四五六七八九十]+)'
PLACE_EN = r'\b(?:city hall|town hall|community (?:center|centre|hall)|school|gym(?:nasium)?|hospital|clinic|station|airport|park|church|temple|hotel|warehouse|home|house|library|stadium|office|(?:north|south|east|west)(?:ern)? shelter|(?:the )?(?:other|another|second|third|new) shelter|shelter (?:[0-9]+|one|two|three))\b'
_DEST_OTHER = _re.compile('|'.join([PLACE_JA, ORIENT_JA, NUMBERED_JA, PLACE_EN]), _re.I)
_SHELTER_B = _re.compile(r"(?:避難所|シェルター|shelter)\s*[BＢ]|\b[BＢ]\s*(?:の)?\s*(?:避難所|shelter)", _re.I)


def names_other_destination(text: str) -> str | None:
    """The first place or shelter named other than B, or None.  A text that names shelter B is exempt from the place-noun list (not from numbered / oriented other shelters)."""
    t = text or ''
    if _SHELTER_B.search(t):
        m = _re.search('|'.join([ORIENT_JA, NUMBERED_JA]), t, _re.I)
        return m.group(0) if m else None
    m = _DEST_OTHER.search(t)
    return m.group(0) if m else None


def decide_intent_hybrid(text: str, conflict_check: bool = False, destination_check: bool = False, **kw) -> dict:
    from .mission_policy import UNSUPPORTED
    from .intent import parse_shelter
    if UNSUPPORTED.search(text) or parse_shelter(text) != 'B':
        return {'accept': False, 'item': None, 'reason': 'unsupported_shelter', 'rule': 'explicit_shelter_name'}
    if destination_check and (why := names_other_destination(text)):
        return {'accept': False, 'item': None, 'reason': 'unsupported_shelter', 'rule': 'named_other_destination', 'named': why}
    out = parse_instruction_llm(text, **kw)
    if conflict_check and out.get('accept'):
        why = supply_conflict(text, out.get('probs'), out.get('item'))
        if why:
            return dict(out, accept=False, item=None, reason='conflicting_supply_ask_back', conflict=why,
                        parsed_item=out.get('item'))
    return out
