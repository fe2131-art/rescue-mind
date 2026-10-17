"""I-24: advice credit -- a bounded price for advice over any number of missions.

Proposition 2 (I-19) caps what advice can do to SAFETY in one mission.  Its price (cost bound, supplement S10) is per
mission: a source that sends wrong location advice, or hazard claims, at every mission (a peer's poisoned memory file, a
flooding operator account) costs the robot a wasted visit or a false refusal every time, without limit.

Advice credit closes that.  Each advice source (memory, peer, inventory, operator; a peer id if peers authenticate) holds
credit in two pools, and an item is ADMITTED to `advice.plan` only if its pool can pay for the worst cost it can cause:

  * location pool: an applied reorder can waste at most one visit (the advised station does not hold the supply).
      settle: the robot's own check at the advised station found the requested supply -> the advice saved >= 1 visit
      against the inventory order, refund REFUND_LOC (capped); found the wrong / no supply, or could not decide -> debit 1
      (the visit was spent); the station was never checked (mission ended earlier) -> nothing.  Scrutiny views forced by the reorder are charged SCRUTINY_COST.
  * hazard pool: a caution can cause a false refusal (a station refused only at the caution threshold).
      settle: refused at the caution threshold but not at the base threshold -> debit 1; otherwise nothing.  No refund
      for a "confirmed" hazard (the robot would have refused anyway, so it saved nothing and a refund could be farmed by
      reporting visible fires); instead the pool REGENERATES by RHO per mission (provenance decay).
  * 'safe' / 'skip' items do nothing in monotone mode (advice.plan rejects them); they cost nothing and are only counted.

Why it is free in safety: credit only DROPS items, and any subset of an advice set is itself an advice set, so the plan
stays inside Proposition 2 (`advice.plan` re-asserts the monotone invariant on what is admitted).

Proposition 3 (price over a horizon).  For any source and any adaptive sequence of advice over m missions:
  (a) wasted visits caused by its location advice  <=  C_LOC + REFUND_LOC * (visits its advice saved) + RHO_SHADOW * m
      so the NET price in visits is at most C_LOC + RHO_SHADOW * m when REFUND_LOC <= 1 (RHO_SHADOW = 0: at most C_LOC,
      but a source that was throttled once never recovers; RHO_SHADOW trades that consistency against robustness);
  (b) false refusals caused by its hazard advice   <=  C_HAZ + RHO * m;
  (c) a source whose location advice is always confirmed and whose hazard advice never causes a caution-only refusal is
      never throttled (consistency).
(with scrutiny, (a) counts the scrutiny views as SCRUTINY_COST visits each time and the worst cost of a reorder is
1 + SCRUTINY_COST.)  Proof sketch: admission needs credit >= the item's worst cost, every debit is at most what was reserved, and credit is
never negative; summing debits over missions telescopes against C + refunds (+ regeneration).  Items of the same source in
one mission are admitted greedily while their summed worst cost fits the credit.

Pure functions; the ledger is a JSON-able dict kept between missions (like MissionMemory).
"""
from __future__ import annotations
import json
import math
from pathlib import Path

C_LOC = 2.0            # initial / maximum location credit of a source, in wasted visits
C_HAZ = 1.0            # initial / maximum hazard credit, in false refusals
REFUND_LOC = 1.0       # credit back for a confirmed reorder (it saved at least one visit)
SCRUTINY_COST = 0.25   # visit-equivalents of the three scrutiny views a reorder forces (I-20 extra poses)
RHO = 0.05             # hazard credit regenerated per mission (provenance decay of an old false alarm)
RHO_SHADOW = 0.25      # location credit back when a THROTTLED claim is confirmed by the robot's own search (no cost paid)
WORST = {'location': 1.0, 'hazard': 1.0, 'safe': 0.0, 'skip': 0.0}
POOL = {'location': 'loc', 'hazard': 'haz'}
VERSION = 'i24-v1'


class CreditError(ValueError):
    pass


def new_ledger(*, c_loc: float = C_LOC, c_haz: float = C_HAZ, refund_loc: float = REFUND_LOC,
               scrutiny_cost: float = SCRUTINY_COST, rho: float = RHO, rho_shadow: float = RHO_SHADOW,
               certified_peers: tuple = ()) -> dict:
    for v in (c_loc, c_haz, refund_loc, scrutiny_cost, rho, rho_shadow):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            raise CreditError('credit parameters must be finite numbers >= 0')
    return {'version': VERSION, 'params': {'c_loc': float(c_loc), 'c_haz': float(c_haz), 'refund_loc': float(refund_loc),
                                           'scrutiny_cost': float(scrutiny_cost), 'rho': float(rho),
                                           'rho_shadow': float(rho_shadow),
                                           'certified_peers': sorted(str(x) for x in certified_peers)},
            'missions': 0, 'sources': {}, 'history': []}


def source_key(item: dict, ledger: dict | None = None) -> str:
    """The accounting identity: the channel (memory, peer, inventory, operator).  A peer gets its own account only if its
    id is listed in the ledger's params['certified_peers'] (identities issued by the operator); free identities would let
    one attacker multiply its credit by inventing names (Sybil; Douceur 2002), so every uncertified peer shares 'peer'."""
    pid = item.get('peer_id') if item.get('source') == 'peer' else None
    certified = ((ledger or {}).get('params') or {}).get('certified_peers') or ()
    return f"peer:{pid}" if isinstance(pid, str) and pid in certified else str(item.get('source'))


def _account(ledger: dict, key: str) -> dict:
    p = ledger['params']
    return ledger['sources'].setdefault(key, {'loc': p['c_loc'], 'haz': p['c_haz'], 'debit_loc': 0.0, 'debit_haz': 0.0,
                                              'refund_loc': 0.0, 'saved_visits': 0, 'relax_attempts': 0,
                                              'n_admitted': 0, 'n_throttled': 0})


def worst_cost(ledger: dict, kind: str, scrutiny: bool = False) -> float:
    """The most one applied item can be charged in `settle` (a reorder under scrutiny also pays for the extra views)."""
    if kind not in WORST:
        raise CreditError(f'unknown advice kind {kind!r}')
    return WORST[kind] + (ledger['params']['scrutiny_cost'] if (kind == 'location' and scrutiny) else 0.0)


def admit(ledger: dict, items: list[dict], *, scrutiny: bool = False) -> tuple[list[dict], list[dict]]:
    """Split validated advice items into (admitted, throttled).  Does not change credit (reservation is implicit: the
    admitted worst cost of each source and pool fits its credit).  Fail-closed: a corrupt ledger raises."""
    _check(ledger)
    admitted, throttled = [], []
    reserved: dict[tuple, float] = {}
    for a in items or []:
        kind = a.get('kind')
        key = source_key(a, ledger)
        acc = _account(ledger, key)
        w = worst_cost(ledger, kind, scrutiny)
        if kind in ('safe', 'skip'):
            admitted.append(a)          # inert in monotone mode; admitted so the report still says it was rejected
            continue
        pool = POOL[kind]
        r = reserved.get((key, pool), 0.0) + w
        if r <= acc[pool] + 1e-9:
            reserved[(key, pool)] = r
            admitted.append(a)
        else:
            throttled.append(dict(a, why=f'credit exhausted ({pool} {acc[pool]:.2f} < {r:.2f})'))
    return admitted, throttled


def settle(ledger: dict, plan: dict, visits: list[dict], *, mission_id: str | None = None) -> dict:
    """After a mission: charge / refund each source for what its APPLIED advice did, from the robot's own checks.

    plan   : the mission plan returned by advice.plan (its 'advice' record lists applied items with their effect).
    visits : one record per station checked, in order: {'station', 'supply_match': True|False|None,
             'refused': bool, 'refused_base': bool, 'scrutiny_views': int}.  'refused_base' says the check would have
             refused at the base threshold too; refused and not refused_base = a caution-only refusal.
    Returns the settlement record (also appended to ledger['history'])."""
    _check(ledger)
    p = ledger['params']
    rec = (plan or {}).get('advice') or {}
    by_station = {}
    for v in visits or []:
        st = v.get('station')
        if st is not None and st not in by_station:
            by_station[st] = v
    out = {'mission': mission_id, 'mode': rec.get('mode'), 'charges': []}
    for a in rec.get('applied') or []:
        key, st, eff = source_key(a, ledger), a.get('station'), a.get('effect')
        acc = _account(ledger, key)
        acc['n_admitted'] += 1
        v = by_station.get(st)
        if eff == 'reorder':
            if v is None:                         # never checked (the mission ended earlier): no visit was spent
                ch = 0.0
            elif v.get('supply_match') is True:
                ch = -p['refund_loc']
                acc['saved_visits'] += 1
            else:                                 # wrong supply, or undecided: the visit was spent without a delivery
                ch = 1.0
            if v is not None and a.get('scrutiny'):
                ch += p['scrutiny_cost'] * min(3, max(0, int(v.get('scrutiny_views') or 0))) / 3.0
            _charge(acc, 'loc', ch, p['c_loc'])
            out['charges'].append({'source': key, 'pool': 'loc', 'station': st, 'charge': round(ch, 4)})
        elif eff == 'caution':
            ch = 1.0 if (v is not None and v.get('refused') and not v.get('refused_base')) else 0.0
            _charge(acc, 'haz', ch, p['c_haz'])
            out['charges'].append({'source': key, 'pool': 'haz', 'station': st, 'charge': ch})
    for a in rec.get('rejected') or []:
        if a.get('kind') in ('safe', 'skip'):
            _account(ledger, source_key(a, ledger))['relax_attempts'] += 1
    shadowed = set()
    for a in rec.get('throttled') or []:
        key = source_key(a, ledger)
        acc = _account(ledger, key)
        acc['n_throttled'] += 1
        v = by_station.get(a.get('station'))
        # shadow check: a throttled location claim that the robot's own search confirmed earns a little credit back
        # (at most once per source and mission), so a mostly-right source is not locked out for ever
        if a.get('kind') == 'location' and key not in shadowed and v is not None and v.get('supply_match') is True:
            shadowed.add(key)
            back = min(p['c_loc'], acc['loc'] + p['rho_shadow']) - acc['loc']
            acc['loc'] += back
            acc['shadow_refund_loc'] = acc.get('shadow_refund_loc', 0.0) + back
            out['charges'].append({'source': key, 'pool': 'loc', 'station': a.get('station'), 'charge': -round(back, 4),
                                   'shadow': True})
    ledger['missions'] += 1
    for acc in ledger['sources'].values():            # provenance decay: an old false alarm is slowly forgiven
        acc['haz'] = min(p['c_haz'], acc['haz'] + p['rho'])
        for pool in ('loc', 'haz'):                   # no float drift: 10 x 0.1 of credit is exactly 1 visit
            acc[pool] = round(acc[pool], 9)
    ledger['history'].append(out)
    return out


def _charge(acc: dict, pool: str, ch: float, cap: float) -> None:
    if ch >= 0:
        acc[pool] = max(0.0, acc[pool] - ch)          # cannot go below zero: admission reserved at most the credit
        acc['debit_' + pool] += ch
    else:
        acc[pool] = min(cap, acc[pool] - ch)
        acc['refund_' + pool] = acc.get('refund_' + pool, 0.0) - ch


def plan_with_credit(ledger: dict, item: str, items: list[dict], mode: str, base: dict | None = None, **kw) -> dict:
    """advice.plan on the admitted items only; the throttled ones are recorded in the plan's advice record and in its
    rationale.  Credit applies to monotone mode only (the baselines follow advice by definition)."""
    from . import advice
    if mode != 'monotone':
        return advice.plan(item, items, mode, base, **kw)
    items = advice.validate(items, kw.get('stations'))
    kept, throttled = admit(ledger, items, scrutiny=bool(kw.get('scrutiny')))
    out = advice.plan(item, kept, mode, base, **kw)
    out['advice']['items'] = items
    out['advice']['throttled'] = throttled
    out['advice']['credit'] = {k: {'loc': round(v['loc'], 4), 'haz': round(v['haz'], 4)}
                               for k, v in ledger['sources'].items()}
    for a in throttled:
        out['rationale'].append(f'{advice.SOURCE_JA.get(a["source"], a["source"])}の助言は信用を使い切ったため不採用'
                                f'（過去の誤りの分。安全は変わらない）')
    return out


def audit_credit(plan: dict) -> dict:
    """Run audit: the admitted items are exactly items minus throttled, so the monotone audit of advice.plan covers
    everything that acted.  Raises CreditError."""
    rec = (plan or {}).get('advice') or {}
    if 'throttled' not in rec:
        return {'checked': False}
    key = lambda a: json.dumps({k: a.get(k) for k in ('source', 'kind', 'station', 'text', 'peer_id')}, sort_keys=True)
    received = sorted(key(a) for a in rec.get('items') or [])
    accounted = sorted(key(a) for a in (rec.get('applied') or []) + (rec.get('rejected') or []) + rec['throttled'])
    if received != accounted:               # every item received is applied, rejected or throttled, exactly once
        raise CreditError('throttled + acted advice does not add up to the advice received')
    if any(not str(a.get('why', '')).startswith('credit exhausted') for a in rec['throttled']):
        raise CreditError('a throttled item without a credit reason')
    return {'checked': True, 'n_throttled': len(rec['throttled'])}


def _check(ledger: dict) -> None:
    if not isinstance(ledger, dict) or ledger.get('version') != VERSION or not isinstance(ledger.get('sources'), dict):
        raise CreditError('bad advice-credit ledger')
    for acc in ledger['sources'].values():
        for pool in ('loc', 'haz'):
            v = acc.get(pool)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
                raise CreditError('corrupt credit value')


def load(path: str | Path | None, **params) -> dict:
    """A missing file is a fresh ledger; a corrupt one raises (the robot then runs without advice, never with
    unlimited credit)."""
    if not path or not Path(path).is_file():
        return new_ledger(**params)
    led = json.loads(Path(path).read_text(encoding='utf8'))
    _check(led)
    return led


def save(ledger: dict, path: str | Path) -> None:
    _check(ledger)
    Path(path).write_text(json.dumps(ledger, ensure_ascii=False, indent=1) + '\n', encoding='utf8')


def _supply_match(cp: dict | None) -> bool | None:
    """True: both passes saw the requested supply; False: both agree on another one / nothing; None: undecided."""
    d = (cp or {}).get('decision') or {}
    exp, a, b = d.get('expected'), d.get('first_supply'), d.get('second_supply')
    if exp is None or a is None or a != b:
        return None
    return a == exp


def visits_from_mission(m: dict) -> list[dict]:
    """The settlement input, rebuilt from mission.json alone (the robot's own checks, in visiting order):
    recovery.first_station / first_checkpoint, each recovery hop, then the final checkpoint.  A station listed in
    'caution_refusals' was refused at the caution threshold only (refused, not refused_base)."""
    caution_only = {r.get('station') for r in m.get('caution_refusals') or []}
    out = []

    def add(st, cp):
        if st is None or cp is None:
            return
        d = cp.get('decision') or {}
        refused = d.get('allow') is False and 'supply' not in str(d.get('reason', ''))
        peeks = ((cp.get('look_around') or {}).get('peeks') or [])
        out.append({'station': st, 'supply_match': _supply_match(cp), 'refused': bool(refused or st in caution_only),
                    'refused_base': bool(refused and st not in caution_only),
                    'scrutiny_views': len({p.get('side') for p in peeks} & {'L2', 'R2', 'N'})})
    rec = m.get('recovery') or {}
    add(rec.get('first_station'), rec.get('first_checkpoint'))
    for h in rec.get('hops') or []:
        add(h.get('station'), h.get('checkpoint'))
    cp = m.get('checkpoint')
    if cp is not None and isinstance(cp, dict) and 'look_around' not in cp and m.get('look_around'):
        cp = dict(cp, look_around=m['look_around'])
    add(m.get('checkpoint_station'), cp)
    return out
