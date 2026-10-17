"""I-19: untrusted inputs may only tighten.

Everything the robot did not perceive itself at the station is *advice*: its own memory (I-15), a peer robot's memory,
the inventory record, or hints and claims in the operator's instruction text.  An advice item says one of
  * location   : "the requested supply is at station S"            (can REORDER the stations to visit)
  * hazard     : "there is fire/smoke at station S"                 (can add CAUTION at S: stricter tau_h, side first)
  * safe       : "station S is safe / already checked / no fire"    (can do NOTHING in monotone mode)
  * skip       : "skip the check / just deliver"                    (can do NOTHING in monotone mode)

Mode 'monotone' (ours) turns advice into a plan that only reorders and tightens, so for the same camera frames every
approval with advice is also an approval without it (Proposition: advice monotonicity; P(unsafe | any advice) <= k*eps).
Mode 'naive' is the measured baseline of an advice-following agent: it skips the check on 'safe'/'skip' and refuses
without visiting on 'hazard'.  Mode 'filtered' is the realistic guardrail defence (LLM injection / safety filter in front
of an advice-following agent): the same as 'naive' applied only to the items that pass `filter_fn`; items it flags as an
attempt to relax or skip a safety check are dropped (and logged with the reason).  It is NOT monotone: whatever the filter
misses ("verified, the water is at M") is followed.  The plan has the same schema as MissionMemory.plan, so the mission
node and the audits handle all modes the same way.  Pure functions: no ROS, no model calls (filter_fn is injected).
"""
from __future__ import annotations
import json
from pathlib import Path

from .mission_memory import STATIONS, CAUTION_TAU_H

V36_TAU_H = 0.05          # the v3.6 hazard threshold: a caution threshold must be a finite number in (0, V36_TAU_H)

KINDS = ('location', 'hazard', 'safe', 'skip')
MODES = ('off', 'monotone', 'naive', 'filtered')
FOLLOWING = ('naive', 'filtered')       # modes that follow advice (no monotone guarantee)
SOURCES = ('memory', 'peer', 'inventory', 'operator')
STATION_JA = {'water': '拠点W', 'medicine': '拠点M'}
SOURCE_JA = {'memory': '自分の記憶', 'peer': '他のロボット', 'inventory': '在庫記録', 'operator': '依頼文'}


class AdviceError(ValueError):
    pass


def validate(items: list[dict]) -> list[dict]:
    if items is None:
        return []
    if not isinstance(items, (list, tuple)):         # a file holding {} / 5 / "skip" is malformed, not 'no advice'
        raise AdviceError(f'advice must be a list of items, got {type(items).__name__}')
    out = []
    for a in items:
        if not isinstance(a, dict) or a.get('kind') not in KINDS or a.get('source') not in SOURCES:
            raise AdviceError(f'bad advice item: {a!r}')
        st = a.get('station')
        if st is not None and st not in STATIONS:
            raise AdviceError(f'bad advice station: {a!r}')
        if a['kind'] in ('location', 'hazard') and st is None:
            raise AdviceError(f'{a["kind"]} advice needs a station: {a!r}')
        out.append({'source': a['source'], 'kind': a['kind'], 'station': st, 'text': str(a.get('text', ''))[:200]})
    return out


def load(path: str | Path | None) -> list[dict]:
    if not path:
        return []
    try:
        doc = json.loads(Path(path).read_text(encoding='utf8'))
    except RecursionError as e:                      # hostile nesting: an error (no advice), never an escaping crash type
        raise AdviceError('advice file nested too deeply') from e
    return validate(doc)


def base_plan(item: str) -> dict:
    return {'mode': 'off', 'catalog_station': item, 'first_station': item, 'n_records': 0, 'caution': {},
            'skip_check': False, 'deny_without_visit': False, 'rationale': []}


def apply_filter(items: list[dict], filter_fn) -> tuple[list[dict], list[dict], dict]:
    """Guardrail step of mode 'filtered': `filter_fn(item) -> {'flag': bool, 'p_yes': float|None, ...}` says whether the
    item's text tries to relax / skip a safety check.  Returns (kept, dropped, info).  Fail-closed for the baseline: if the
    filter raises or answers malformed, ALL items are dropped (the conservative choice for the baseline)."""
    kept, dropped, info = [], [], {'n_flagged': 0, 'error': None}
    try:
        verdicts = []
        for a in items:
            v = filter_fn(a)
            if not isinstance(v, dict) or not isinstance(v.get('flag'), bool):
                raise AdviceError(f'malformed filter verdict: {v!r}')
            verdicts.append(v)
    except Exception as e:
        info['error'] = f'{type(e).__name__}: {str(e)[:160]}'
        return [], [dict(a, why='filter error: all advice dropped') for a in items], info
    for a, v in zip(items, verdicts):
        if v['flag']:
            dropped.append(dict(a, why='flagged by filter', p_yes=v.get('p_yes')))
            info['n_flagged'] += 1
        else:
            kept.append(a)
    return kept, dropped, info


def plan(item: str, items: list[dict], mode: str, base: dict | None = None, *, caution_tau_h: float = CAUTION_TAU_H,
         filter_fn=None) -> dict:
    """Combine advice with an existing plan (e.g. the memory plan).  Returns a new plan with an 'advice' record.
    Mode 'filtered' needs `filter_fn` (see apply_filter); the items it keeps are followed exactly as in 'naive'."""
    if item not in STATIONS or mode not in MODES or (mode == 'filtered' and filter_fn is None):
        raise AdviceError('bad advice plan request')
    items = validate(items)
    out = json.loads(json.dumps(base)) if base else base_plan(item)
    out.setdefault('rationale', [])
    rec = {'mode': mode, 'items': items, 'applied': [], 'rejected': [], 'n_base_rationale': len(out['rationale']),
           'base': _snapshot(out)}       # what the audit recomputes assert_monotone against
    out['advice'] = rec
    if mode == 'off' or not items:
        rec['rejected'] = [dict(a, why='advice off') for a in items] if mode == 'off' else []
        if mode == 'filtered':
            rec['dropped'], rec['filter'] = [], {'n_flagged': 0, 'error': None}
        return out
    follow = mode in FOLLOWING
    if mode == 'filtered':
        items, rec['dropped'], rec['filter'] = apply_filter(items, filter_fn)
        for a in rec['dropped']:
            out['rationale'].append(f'（フィルタ）{SOURCE_JA[a["source"]]}の助言を破棄：{a["why"]}')
    tag = '（フィルタ通過後の助言追従）' if mode == 'filtered' else '（素朴な助言追従）'
    for a in items:
        st, src = a['station'], SOURCE_JA[a['source']]
        if a['kind'] == 'location':
            if out['first_station'] == item and st != item and not (mode == 'monotone' and out['skip_check']):
                # own memory's proposal (if any) keeps priority.  Monotone never moves a memory-granted skip to another
                # station: that station was not what memory vouched for (relative guarantee under a naive memory base)
                out['first_station'] = st
                rec['applied'].append(dict(a, effect='reorder'))
                out['rationale'].append(f'{src}：依頼物資は{STATION_JA[st]}にある → 先に{STATION_JA[st]}へ（着いたら確認する）')
            else:
                rec['rejected'].append(dict(a, why='no reorder needed or already proposed'))
        elif a['kind'] == 'hazard':
            if follow and st == out['first_station']:
                out['deny_without_visit'] = True
                rec['applied'].append(dict(a, effect='deny_without_visit'))
                out['rationale'].append(f'{tag}{src}：{STATION_JA[st]}で火災 → 行かずに拒否')
            else:
                prev = (out['caution'].get(st) or {}).get('tau_h')
                tau = min(caution_tau_h, prev) if prev is not None else caution_tau_h
                out['caution'][st] = {**(out['caution'].get(st) or {}), 'tau_h': tau,
                                      'first_side': (out['caution'].get(st) or {}).get('first_side'), 'seen_in': a['source']}
                rec['applied'].append(dict(a, effect='caution'))
                out['rationale'].append(f'{src}：{STATION_JA[st]}で火災の報告 → 全視点で閾値を {tau} に厳格化（行って確かめる）')
        else:   # safe / skip
            if follow:
                out['skip_check'] = True
                rec['applied'].append(dict(a, effect='skip_check'))
                out['rationale'].append(f'{tag}{src}：「{a["text"] or a["kind"]}」→ 現地確認を省略')
            else:
                rec['rejected'].append(dict(a, why='cannot relax a check'))
                out['rationale'].append(f'{src}：「{a["text"] or a["kind"]}」→ 確認は省略できないため不採用')
    if mode == 'monotone':
        assert_monotone(base_plan(item) if base is None else base, out)
    return out


def _snapshot(plan: dict) -> dict:
    return {'first_station': plan.get('first_station'), 'skip_check': bool(plan.get('skip_check')),
            'deny_without_visit': bool(plan.get('deny_without_visit')),
            'caution': json.loads(json.dumps(plan.get('caution') or {}))}


def assert_monotone(before: dict, after: dict) -> None:
    """The invariant, checked on every monotone plan and recomputed by the run audit: no skipped check, no refusal
    without visiting (relative to the plan before advice: a naive MEMORY baseline underneath stays what it was),
    thresholds only tighter than before.  Reordering is allowed."""
    if (after.get('skip_check') and not before.get('skip_check')) or (
            after.get('deny_without_visit') and not before.get('deny_without_visit')):
        raise AdviceError('monotone plan relaxes a check')
    b_cau, a_cau = before.get('caution') or {}, after.get('caution') or {}
    for st in b_cau:
        if st not in a_cau:
            raise AdviceError('monotone plan removes a caution')
    for st, c in a_cau.items():
        tau = _tau(c)
        if st in b_cau and not tau <= _tau(b_cau[st], strict=False):      # written so that NaN fails
            raise AdviceError('monotone plan loosens a caution threshold')
    if after.get('first_station') not in STATIONS:
        raise AdviceError('bad first station')


def _tau(c, strict: bool = True) -> float:
    t = c.get('tau_h') if isinstance(c, dict) else None
    if isinstance(t, bool) or not isinstance(t, (int, float)):
        raise AdviceError('caution threshold is not a number')
    if strict and not 0 < t < V36_TAU_H:             # also rejects NaN and inf
        raise AdviceError('caution threshold must be a finite number in (0, 0.05)')
    return float(t)


def audit_plan(plan: dict) -> dict:
    """Run audit for a mission.json plan: recompute the invariant from the logged plan alone.  Raises AdviceError.
    Returns a small evidence record.  Only 'monotone' plans are required to hold the invariant; for 'naive', 'filtered'
    and 'off' the record just says what the advice did (and, for 'filtered', what the filter dropped)."""
    rec = (plan or {}).get('advice')
    if not rec:
        return {'mode': None, 'checked': False}
    ev = {'mode': rec.get('mode'), 'checked': False, 'n_items': len(rec.get('items') or []),
          'applied': [a.get('effect') for a in rec.get('applied') or []], 'rejected': len(rec.get('rejected') or [])}
    if rec.get('mode') == 'filtered':
        ev['dropped'] = len(rec.get('dropped') or [])
        ev['filter_error'] = (rec.get('filter') or {}).get('error')
    if rec.get('mode') == 'monotone':
        bad = [e for e in ev['applied'] if e not in ('reorder', 'caution')]
        if bad:
            raise AdviceError(f'monotone run applied non-monotone effects: {bad}')
        assert_monotone(rec.get('base') or {}, plan)
        ev['checked'] = True
    return ev


def skip_source(plan: dict | None) -> str | None:
    """Who made the robot skip the on-site check?  'advice' (naive or filtered advice), 'memory' (naive memory) or None."""
    plan = plan or {}
    rec = plan.get('advice') or {}
    if rec.get('mode') in FOLLOWING and plan.get('skip_check') and any(
            a.get('effect') == 'skip_check' for a in rec.get('applied') or []):
        return 'advice'
    if plan.get('mode') == 'naive' and plan.get('skip_check'):
        return 'memory'
    return None


def denial_source(plan: dict | None) -> str | None:
    """Who made the robot refuse without visiting?  Same convention as skip_source."""
    plan = plan or {}
    rec = plan.get('advice') or {}
    if rec.get('mode') in FOLLOWING and plan.get('deny_without_visit') and any(
            a.get('effect') == 'deny_without_visit' for a in rec.get('applied') or []):
        return 'advice'
    if plan.get('mode') == 'naive' and plan.get('deny_without_visit'):
        return 'memory'
    return None
