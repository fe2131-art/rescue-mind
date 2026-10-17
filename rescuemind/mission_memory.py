"""I-15 cross-mission experience memory: *memory proposes, perception disposes*.

The robot keeps what it SAW on earlier missions (never ground truth): per station, which supply both VLM passes
agreed on, and whether a fire/smoke was seen and from which view (front, left or right side).  On the next mission
the memory may

  * propose the first station to visit (supplies seen relocated last time -> go there first),
  * raise caution at a station where a hazard was seen recently (stricter hazard threshold on every view there, and
    look first from the side that revealed it),
  * report what changed since the last visit.

It may never remove or weaken a check (mode 'verified').  This is the safety-monotonicity invariant: with the same
camera frames, every approval issued with memory also passes every check that approval needs without memory.
`naive` is the baseline that trusts memory instead (skips the on-site check where the requested supply was seen
last time, refuses without visiting where a hazard was seen) -- it exists only to be measured against.
"""
from __future__ import annotations
import json
import math
import time
from pathlib import Path

STATIONS = ('water', 'medicine')
CAUTION_TAU_H = 0.01      # stricter p(fire/smoke) refusal threshold at a station with a recent hazard (v3.6: 0.05)
HORIZON = 3               # a hazard is "recent" if seen during the last HORIZON missions in memory
SIDE_JA = {'front': '正面', 'L': '左', 'R': '右'}
ITEM_JA = {'water': '飲料水', 'medicine': '医療物資', 'other': '依頼物資以外/空', 'uncertain': '不確か'}


def scores_valid(call) -> bool:
    """The call carries a usable p(hazard): a finite number in [0, 1] (not a bool).  Anything else is a broken view."""
    try:
        v = ((call or {}).get('scores') or {}).get('hazard_prob')
    except AttributeError:
        return False
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0.0 <= v <= 1.0


def _hazard_prob(call: dict) -> float:
    """p(hazard) of one model call.  FAIL-CLOSED (I-19 fix, FINDINGS #26): a missing, malformed, non-finite or
    out-of-range score counts as p = 1.0, i.e. as a hazard (consistent with adaptive_views._p)."""
    return float(call['scores']['hazard_prob']) if scores_valid(call) else 1.0


def hazard_prob(call: dict) -> float:
    return _hazard_prob(call)


def apply_memory_caution(decision: dict, first: dict, second: dict, tau_h: float | None) -> dict:
    """Stricter hazard threshold at a station with a remembered hazard.  Can only turn an approval into a hazard
    refusal (deterministic, so the run audit recomputes it)."""
    if tau_h is None or not decision.get('allow'):
        return decision
    p = max(_hazard_prob(first), _hazard_prob(second))
    if p < tau_h:
        return decision
    return {**decision, 'allow': False, 'reason': 'visible_hazard_at_checkpoint',
            'pre_caution_reason': decision['reason'], 'memory_caution_tau_h': tau_h}


def peek_hazard(reason: str, first: dict, second: dict, tau_h: float | None) -> bool:
    """A side view shows a hazard if the model said so, or (under memory caution) p(hazard) >= tau_h.
    FAIL-CLOSED: a side view whose hazard score is missing / invalid / non-finite (or whose inference failed) is a hazard,
    with or without a caution threshold -- a broken view never counts as clear."""
    if reason == 'visible_hazard_at_checkpoint':
        return True
    if not (scores_valid(first) and scores_valid(second)):
        return True
    return tau_h is not None and max(_hazard_prob(first), _hazard_prob(second)) >= tau_h


def _supply_seen(cp: dict) -> str:
    """The supply both passes named, if each put >= 0.5 on it.  (The decision's confidences are for the REQUESTED
    supply, so they cannot be used for what was actually seen.)"""
    calls = cp.get('model_calls') or {}
    labels = [((calls.get(k) or {}).get('result') or {}).get('supply') for k in ('first', 'second')]
    if labels[0] != labels[1] or labels[0] is None:
        return 'uncertain'
    for k in ('first', 'second'):
        probs = ((calls.get(k) or {}).get('scores') or {}).get('supply_probs')
        if probs is not None and float(probs.get(labels[0], 0.0)) < 0.5:
            return 'uncertain'
    return labels[0]


def _front_hazard(cp: dict) -> bool:
    calls = cp.get('model_calls') or {}
    if any(((c or {}).get('result') or {}).get('scene') == 'hazard' for c in calls.values() if isinstance(c, dict)):
        return True
    tau = cp.get('memory_caution_tau_h')
    return tau is not None and max(_hazard_prob(calls.get('first')), _hazard_prob(calls.get('second'))) >= tau


def observations(mission: dict, tag: str) -> list[dict]:
    """What the robot itself observed at each station during one mission (from mission.json; no ground truth)."""
    out = []

    def add(station, cp, peeks=()):
        if not isinstance(cp, dict) or cp.get('memory_trusted') or 'decision' not in cp:
            return
        views = (['front'] if _front_hazard(cp) else []) + [p['side'] for p in peeks if p.get('hazard')]
        calls = cp.get('model_calls') or {}
        out.append({'tag': tag, 'station': station, 'supply': _supply_seen(cp),
                    'hazard': bool(views), 'hazard_views': views,
                    'hazard_prob_max': round(max([_hazard_prob(calls.get('first')), _hazard_prob(calls.get('second'))]
                                                 + [max(_hazard_prob(p['model_calls'].get('first')),
                                                        _hazard_prob(p['model_calls'].get('second'))) for p in peeks]), 4),
                    'views_checked': ['front'] + [p['side'] for p in peeks]})

    rec = mission.get('recovery') or {}
    if rec:
        # a caution-only refusal from a side view (R5 #5, --caution-soft) leaves that station's side views in its checkpoint
        peeks = lambda cp: ((cp or {}).get('look_around') or {}).get('peeks') or []
        add(rec.get('first_station'), rec.get('first_checkpoint'), peeks(rec.get('first_checkpoint')))
        for h in rec.get('hops') or []:          # I-21: every station of a k-station search is a fresh observation
            add(h.get('station'), h.get('checkpoint'), peeks(h.get('checkpoint')))
    station = mission.get('checkpoint_station')
    if station:
        add(station, mission.get('checkpoint'), ((mission.get('look_around') or {}).get('peeks') or []))
    return out


class MissionMemory:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.records = []
        if self.path.is_file():
            self.records = [json.loads(x) for x in self.path.read_text(encoding='utf8').splitlines() if x.strip()]

    # ---------------------------------------------------------------- read
    def tags(self) -> list[str]:
        seen = []
        for r in self.records:
            if r['tag'] not in seen:
                seen.append(r['tag'])
        return seen

    def last(self, station: str) -> dict | None:
        obs = [r for r in self.records if r['station'] == station]
        return obs[-1] if obs else None

    def plan(self, item: str, mode: str = 'verified', *, horizon: int = HORIZON, caution_tau_h: float = CAUTION_TAU_H,
             stations=None) -> dict:
        """Mission plan proposed by memory for the requested `item` (catalog station = the inventory's first station for
        the item; in the two-station arena the item's own station).  `stations` (rescuemind.stations.StationSet,
        default the arena) generalises to k stations: plan['order'] is the candidate order (a permutation of ALL
        stations: memory may reorder, never skip) and plan['first_station'] is its head."""
        from .stations import StationSet
        ss = stations or StationSet.legacy()
        if item not in ('water', 'medicine') or mode not in ('off', 'verified', 'naive'):
            raise ValueError('bad memory plan request')
        base_order = ss.default_order(item)
        cat = base_order[0]
        out = {'mode': mode, 'catalog_station': cat, 'first_station': cat, 'n_records': len(self.records),
               'caution': {}, 'skip_check': False, 'deny_without_visit': False, 'rationale': []}
        if not ss.is_legacy():
            out['order'] = list(base_order)
        if mode == 'off' or not self.records:
            return out
        here = self.last(cat)
        if here and here['supply'] not in (item, 'uncertain'):
            seen = {s: (self.last(s) or {}).get('supply') for s in base_order}
            found = [s for s in base_order if s != cat and seen[s] == item]
            if found:
                # stations where the item was seen come first, then the unknown ones, then those seen holding something else
                rank = lambda s: 0 if seen[s] == item else (2 if seen[s] not in (None, 'uncertain') else 1)
                order = sorted(base_order, key=lambda s: (rank(s), base_order.index(s)))
                out['first_station'] = order[0]
                if 'order' in out:
                    out['order'] = order
                out['rationale'].append(f'前回、{ITEM_JA[item]}は拠点「{order[0]}」で確認（定位置には{ITEM_JA[here["supply"]]}）→ 先に「{order[0]}」へ')
        if mode == 'verified':
            recent = set(self.tags()[-horizon:])
            for s in ss.ids:
                hz = [r for r in self.records if r['station'] == s and r['tag'] in recent and r['hazard']]
                if hz:
                    sides = [v for v in hz[-1]['hazard_views'] if v in ('L', 'R')]
                    out['caution'][s] = {'tau_h': caution_tau_h, 'first_side': sides[0] if sides else None,
                                         'seen_in': hz[-1]['tag']}
                    out['rationale'].append(f'拠点「{s}」で最近 火・煙を観測（{"・".join(SIDE_JA[v] for v in hz[-1]["hazard_views"])}）'
                                            f'→ 全視点で危険の閾値を {caution_tau_h} に厳格化'
                                            + (f'、{SIDE_JA[sides[0]]}から先に見る' if sides else ''))
        else:   # naive: trust memory (baseline only)
            o = self.last(out['first_station'])
            if o and o['hazard']:
                out['deny_without_visit'] = True
                out['rationale'].append('（素朴な記憶）前回この拠点で火・煙 → 行かずに拒否')
            elif o and o['supply'] == item:
                out['skip_check'] = True
                out['rationale'].append('（素朴な記憶）前回この拠点で依頼物資を確認 → 現地確認を省略')
        return out

    # ---------------------------------------------------------------- write
    def changes(self, new_obs: list[dict]) -> list[dict]:
        """Differences between what was just seen and the previous memory of the same station (operator report)."""
        out = []
        for o in new_obs:
            prev = self.last(o['station'])
            if prev is None:
                continue
            if prev['supply'] != o['supply'] and 'uncertain' not in (prev['supply'], o['supply']):
                out.append({'station': o['station'], 'kind': 'supply_changed', 'before': prev['supply'], 'now': o['supply'],
                            'text_ja': f'拠点「{o["station"]}」の物資が前回（{ITEM_JA[prev["supply"]]}）から変化（{ITEM_JA[o["supply"]]}）'})
            if prev['hazard'] and not o['hazard']:
                out.append({'station': o['station'], 'kind': 'hazard_not_seen_now', 'before': prev['hazard_views'],
                            'now': o['views_checked'],
                            'text_ja': f'拠点「{o["station"]}」：前回の火・煙は今回 {len(o["views_checked"])} 視点から見えず（鎮火の可能性）'})
            if o['hazard'] and not prev['hazard']:
                out.append({'station': o['station'], 'kind': 'hazard_new', 'now': o['hazard_views'],
                            'text_ja': f'拠点「{o["station"]}」：前回なかった火・煙を新たに観測'})
        return out

    def append_mission(self, mission: dict, tag: str) -> dict:
        obs = observations(mission, tag)
        diff = self.changes(obs)
        if obs:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open('a', encoding='utf8') as f:
                for o in obs:
                    f.write(json.dumps({**o, 'written_unix': round(time.time(), 3)}, ensure_ascii=False) + '\n')
            self.records += obs
        return {'observations': obs, 'changes': diff}
