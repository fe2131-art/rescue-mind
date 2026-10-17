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
without visiting on 'hazard'.  The plan has the same schema as MissionMemory.plan, so the mission node and the audits
handle both the same way.  Pure functions: no ROS, no model calls.
"""
from __future__ import annotations
import json
from pathlib import Path

from .mission_memory import STATIONS, CAUTION_TAU_H

KINDS = ('location', 'hazard', 'safe', 'skip')
SOURCES = ('memory', 'peer', 'inventory', 'operator')
STATION_JA = {'water': '拠点W', 'medicine': '拠点M'}
SOURCE_JA = {'memory': '自分の記憶', 'peer': '他のロボット', 'inventory': '在庫記録', 'operator': '依頼文'}


class AdviceError(ValueError):
    pass


def validate(items: list[dict]) -> list[dict]:
    out = []
    for a in items or []:
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
    return validate(json.loads(Path(path).read_text(encoding='utf8')))


def base_plan(item: str) -> dict:
    return {'mode': 'off', 'catalog_station': item, 'first_station': item, 'n_records': 0, 'caution': {},
            'skip_check': False, 'deny_without_visit': False, 'rationale': []}


def plan(item: str, items: list[dict], mode: str, base: dict | None = None, *, caution_tau_h: float = CAUTION_TAU_H) -> dict:
    """Combine advice with an existing plan (e.g. the memory plan).  Returns a new plan with an 'advice' record."""
    if item not in STATIONS or mode not in ('off', 'monotone', 'naive'):
        raise AdviceError('bad advice plan request')
    items = validate(items)
    out = json.loads(json.dumps(base)) if base else base_plan(item)
    out.setdefault('rationale', [])
    rec = {'mode': mode, 'items': items, 'applied': [], 'rejected': [], 'n_base_rationale': len(out['rationale']),
           'base': _snapshot(out)}       # what the audit recomputes assert_monotone against
    out['advice'] = rec
    if mode == 'off' or not items:
        rec['rejected'] = [dict(a, why='advice off') for a in items] if mode == 'off' else []
        return out
    for a in items:
        st, src = a['station'], SOURCE_JA[a['source']]
        if a['kind'] == 'location':
            if out['first_station'] == item and st != item:      # own memory's proposal (if any) keeps priority
                out['first_station'] = st
                rec['applied'].append(dict(a, effect='reorder'))
                out['rationale'].append(f'{src}：依頼物資は{STATION_JA[st]}にある → 先に{STATION_JA[st]}へ（着いたら確認する）')
            else:
                rec['rejected'].append(dict(a, why='no reorder needed or already proposed'))
        elif a['kind'] == 'hazard':
            if mode == 'naive' and st == out['first_station']:
                out['deny_without_visit'] = True
                rec['applied'].append(dict(a, effect='deny_without_visit'))
                out['rationale'].append(f'（素朴な助言追従）{src}：{STATION_JA[st]}で火災 → 行かずに拒否')
            else:
                prev = (out['caution'].get(st) or {}).get('tau_h')
                tau = min(caution_tau_h, prev) if prev is not None else caution_tau_h
                out['caution'][st] = {**(out['caution'].get(st) or {}), 'tau_h': tau,
                                      'first_side': (out['caution'].get(st) or {}).get('first_side'), 'seen_in': a['source']}
                rec['applied'].append(dict(a, effect='caution'))
                out['rationale'].append(f'{src}：{STATION_JA[st]}で火災の報告 → 全視点で閾値を {tau} に厳格化（行って確かめる）')
        else:   # safe / skip
            if mode == 'naive':
                out['skip_check'] = True
                rec['applied'].append(dict(a, effect='skip_check'))
                out['rationale'].append(f'（素朴な助言追従）{src}：「{a["text"] or a["kind"]}」→ 現地確認を省略')
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
    for st, c in (after.get('caution') or {}).items():
        b = (before.get('caution') or {}).get(st)
        if b is not None and float(c['tau_h']) > float(b['tau_h']):
            raise AdviceError('monotone plan loosens a caution threshold')
    if after.get('first_station') not in STATIONS:
        raise AdviceError('bad first station')


def audit_plan(plan: dict) -> dict:
    """Run audit for a mission.json plan: recompute the invariant from the logged plan alone.  Raises AdviceError.
    Returns a small evidence record.  Only 'monotone' plans are required to hold the invariant; for 'naive' and 'off'
    the record just says what the advice did."""
    rec = (plan or {}).get('advice')
    if not rec:
        return {'mode': None, 'checked': False}
    ev = {'mode': rec.get('mode'), 'checked': False, 'n_items': len(rec.get('items') or []),
          'applied': [a.get('effect') for a in rec.get('applied') or []], 'rejected': len(rec.get('rejected') or [])}
    if rec.get('mode') == 'monotone':
        bad = [e for e in ev['applied'] if e not in ('reorder', 'caution')]
        if bad:
            raise AdviceError(f'monotone run applied non-monotone effects: {bad}')
        assert_monotone(rec.get('base') or {}, plan)
        ev['checked'] = True
    return ev


def skip_source(plan: dict | None) -> str | None:
    """Who made the robot skip the on-site check?  'advice' (naive advice), 'memory' (naive memory) or None."""
    plan = plan or {}
    rec = plan.get('advice') or {}
    if rec.get('mode') == 'naive' and plan.get('skip_check') and any(
            a.get('effect') == 'skip_check' for a in rec.get('applied') or []):
        return 'advice'
    if plan.get('mode') == 'naive' and plan.get('skip_check'):
        return 'memory'
    return None


def denial_source(plan: dict | None) -> str | None:
    """Who made the robot refuse without visiting?  Same convention as skip_source."""
    plan = plan or {}
    rec = plan.get('advice') or {}
    if rec.get('mode') == 'naive' and plan.get('deny_without_visit') and any(
            a.get('effect') == 'deny_without_visit' for a in rec.get('applied') or []):
        return 'advice'
    if plan.get('mode') == 'naive' and plan.get('deny_without_visit'):
        return 'memory'
    return None
