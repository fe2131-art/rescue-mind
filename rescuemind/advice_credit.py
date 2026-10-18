"""I-24: advice credit -- a bounded price for advice over any number of missions (v2, after mock review R7).

Proposition 2 (I-19) caps what advice can do to SAFETY in one mission.  Its price (cost bound, supplement S10) is per
mission: a channel that sends wrong location advice, or hazard claims, at every mission (a peer's poisoned memory file, a
flooding operator account) costs the robot a wasted visit or a false refusal every time, without limit.

ACCOUNTS are input channels, never labels an item declares about itself (R7 CE-2: one file could otherwise spread its
claims over the four 'source' labels and quadruple its credit):
  'file'      every item of the advice file (peer / inventory / memory claims)
  'operator'  every item extracted from the instruction text
  'peer:<id>' a file item whose peer_id is listed in params['certified_peers'] (identities issued by the operator over an
              authenticated transport; free identities would multiply credit -- Sybil, Douceur 2002)
An item is ADMITTED to `advice.plan` only if its account's pool can pay the worst cost it can cause:
  * location pool (worst cost 1 visit, plus SCRUTINY_COST under scrutiny, plus 1 refusal if scrutiny can refuse there):
      settle, from the robot's own check at the advised station:
        - confirmed (both passes saw the requested supply): charge 0;
        - wrong supply / no supply / undecided: charge 1 (the visit was spent without a delivery) plus the scrutiny views;
        - refused ONLY by the scrutiny caution threshold (the base threshold would have approved): charge 1 more;
        - never checked (the mission ended earlier): nothing.
      There is NO refund for a confirmed reorder (R7 CE-1: with duplicated supply a true claim need not save a visit, so a
      refund could be farmed).  Credit RECOVERS by RHO_SHADOW per mission, at most once per account and mission, when a
      location claim of the account (applied or throttled) was confirmed by the robot's own check.
  * hazard pool (worst cost 1 false refusal): settle: the station was refused at the caution threshold but no view reached
      the base threshold -> charge 1; else 0.  Classified from the per-view scores (R7 CE-4: not from caution_refusals,
      which exist only under --caution-soft).  The pool regenerates by RHO per mission.
  * 'safe' / 'skip' items do nothing in monotone mode; they cost nothing and are only counted.

Why it is free in safety: credit only DROPS items; any subset of an advice set is an advice set, so the plan stays inside
Proposition 2 (`advice.plan` re-asserts the monotone invariant on what is admitted).

Proposition 3 (price over a horizon).  For every account and every adaptive advice sequence over m missions:
  (a) location price = wasted visits + scrutiny-view cost + scrutiny-caused false refusals, all caused by its applied
      location advice  <=  C_LOC + RHO_SHADOW * m;
  (b) false refusals caused by its hazard advice  <=  C_HAZ + RHO * m;
  (c) an account whose location claims are always confirmed and whose hazard claims never cause a caution-only refusal,
      without scrutiny, is never throttled (consistency).  Under scrutiny a confirmed claim also costs nothing.
Proof: admission reserves each admitted item's worst charge against credit that is never negative, so every charge is paid
from credit; credit is capped at C and grows only by RHO_SHADOW (location, once per mission) or RHO (hazard) per mission;
summing over missions telescopes.  Not priced (outside (a)/(b)): a truthful claim that steers the robot to a station that
really burns (a lost delivery; exposure is Proposition 2's domain), and missions that end before settlement.
Pure functions; the ledger is a JSON-able dict kept between missions (like MissionMemory).
"""
from __future__ import annotations
import json
import math
from pathlib import Path

C_LOC = 2.0            # initial / maximum location credit of an account, in visit-equivalents
C_HAZ = 1.0            # initial / maximum hazard credit, in false refusals
SCRUTINY_COST = 0.25   # visit-equivalents of the three scrutiny views a reorder forces (I-20 extra poses)
RHO = 0.05             # hazard credit regenerated per mission (provenance decay of an old false alarm)
RHO_SHADOW = 0.25      # location credit regained per mission in which a location claim of the account was confirmed
BASE_TAU_H = 0.05      # the v3.6 base hazard threshold (a view at or above it is a base-rule hazard)
WORST = {'location': 1.0, 'hazard': 1.0, 'safe': 0.0, 'skip': 0.0}
POOL = {'location': 'loc', 'hazard': 'haz'}
CHANNELS = ('file', 'operator')
VERSION = 'i24-v2'


class CreditError(ValueError):
    pass


def new_ledger(*, c_loc: float = C_LOC, c_haz: float = C_HAZ, scrutiny_cost: float = SCRUTINY_COST, rho: float = RHO,
               rho_shadow: float = RHO_SHADOW, certified_peers: tuple = ()) -> dict:
    for v in (c_loc, c_haz, scrutiny_cost, rho, rho_shadow):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            raise CreditError('credit parameters must be finite numbers >= 0')
    return {'version': VERSION, 'params': {'c_loc': float(c_loc), 'c_haz': float(c_haz),
                                           'scrutiny_cost': float(scrutiny_cost), 'rho': float(rho),
                                           'rho_shadow': float(rho_shadow),
                                           'certified_peers': sorted(str(x) for x in certified_peers)},
            'missions': 0, 'sources': {}, 'history': []}


def account_of(raw_item: dict, channel: str, ledger: dict) -> str:
    """The accounting identity of one RAW item (before advice.validate, which drops peer_id)."""
    if channel not in CHANNELS:
        raise CreditError(f'unknown advice channel {channel!r}')
    pid = raw_item.get('peer_id') if isinstance(raw_item, dict) else None
    if channel == 'file' and isinstance(pid, str) and pid in (ledger['params'].get('certified_peers') or ()):
        return f'peer:{pid}'
    return channel


def _account(ledger: dict, key: str) -> dict:
    p = ledger['params']
    return ledger['sources'].setdefault(key, {'loc': p['c_loc'], 'haz': p['c_haz'], 'debit_loc': 0.0, 'debit_haz': 0.0,
                                              'recovered_loc': 0.0, 'confirmed_loc': 0, 'relax_attempts': 0,
                                              'n_admitted': 0, 'n_throttled': 0})


def worst_cost(ledger: dict, kind: str, scrutiny: bool = False) -> float:
    """The most one applied item can be charged in `settle`."""
    if kind not in WORST:
        raise CreditError(f'unknown advice kind {kind!r}')
    if kind == 'location' and scrutiny:
        return WORST[kind] + ledger['params']['scrutiny_cost'] + 1.0     # + a refusal caused by the scrutiny caution
    return WORST[kind]


def admit(ledger: dict, items: list[dict], accounts: list[str], *, scrutiny: bool = False):
    """Split validated items into (admitted, throttled).  `accounts[i]` is the account of items[i].  Admitted items are
    those whose summed worst cost per (account, pool) fits the credit; throttled ones carry 'account' and a reason."""
    _check(ledger)
    if len(accounts) != len(items or []):
        raise CreditError('one account per advice item')
    admitted, throttled, reserved = [], [], {}
    for a, key in zip(items or [], accounts):
        kind = a.get('kind')
        w = worst_cost(ledger, kind, scrutiny)
        acc = _account(ledger, key)
        if kind in ('safe', 'skip'):
            admitted.append(a)              # inert in monotone mode; admitted so the report still says it was rejected
            continue
        pool = POOL[kind]
        r = reserved.get((key, pool), 0.0) + w
        if r <= acc[pool] + 1e-9:
            reserved[(key, pool)] = r
            admitted.append(a)
        else:
            throttled.append(dict(a, account=key, why=f'credit exhausted ({pool} {acc[pool]:.2f} < {r:.2f})'))
    return admitted, throttled


def _content(a: dict) -> tuple:
    return tuple(a.get(k) for k in ('source', 'kind', 'station', 'text'))


def _accounts_for(rec: dict, entries: list[dict]) -> list[str]:
    """Map the applied / rejected entries of advice.plan back to the accounts of the received items (by content, each
    received item used once)."""
    pool = [(_content(a), k) for a, k in zip(rec.get('items') or [], rec.get('accounts') or [])]
    for t in rec.get('throttled') or []:                     # throttled items are not among the acted ones
        for i, (c, k) in enumerate(pool):
            if c == _content(t) and k == t.get('account'):
                pool.pop(i)
                break
    out = []
    for e in entries:
        for i, (c, k) in enumerate(pool):
            if c == _content(e):
                out.append(k)
                pool.pop(i)
                break
        else:
            raise CreditError('an acted advice item that was not received')
    return out


def settle(ledger: dict, plan: dict, visits: list[dict], *, mission_id: str | None = None) -> dict:
    """After a mission: charge each account for what its APPLIED advice did, from the robot's own checks.
    visits: one record per station checked, in order: {'station', 'supply_match': True|False|None, 'refused': bool,
    'refused_base': bool, 'scrutiny_views': int} (refused and not refused_base = a caution-only refusal)."""
    _check(ledger)
    p = ledger['params']
    rec = (plan or {}).get('advice') or {}
    by_station = {}
    for v in visits or []:
        if v.get('station') is not None and v['station'] not in by_station:
            by_station[v['station']] = v
    out = {'mission': mission_id, 'mode': rec.get('mode'), 'charges': []}
    if 'accounts' not in rec:              # a plan made without credit: nothing to settle
        ledger['missions'] += 1
        ledger['history'].append(out)
        return out
    applied, rejected = rec.get('applied') or [], rec.get('rejected') or []
    acc_applied, acc_rejected = _accounts_for(rec, applied), None
    confirmed = set()
    for a, key in zip(applied, acc_applied):
        acc = _account(ledger, key)
        acc['n_admitted'] += 1
        st, eff, v = a.get('station'), a.get('effect'), by_station.get(a.get('station'))
        if eff == 'reorder':
            ch = 0.0
            if v is not None:
                if v.get('supply_match') is True:
                    confirmed.add(key)
                    acc['confirmed_loc'] += 1
                else:                       # wrong supply, or undecided: the visit was spent without a delivery
                    ch += 1.0
                    if a.get('scrutiny'):
                        ch += p['scrutiny_cost'] * min(3, max(0, int(v.get('scrutiny_views') or 0))) / 3.0
                if a.get('scrutiny') and v.get('refused') and not v.get('refused_base'):
                    ch += 1.0               # the scrutiny caution alone refused a station the base rule would approve
            _charge(acc, 'loc', ch)
            out['charges'].append({'account': key, 'pool': 'loc', 'station': st, 'charge': round(ch, 4)})
        elif eff == 'caution':
            ch = 1.0 if (v is not None and v.get('refused') and not v.get('refused_base')) else 0.0
            _charge(acc, 'haz', ch)
            out['charges'].append({'account': key, 'pool': 'haz', 'station': st, 'charge': ch})
    if rejected:
        acc_rejected = _accounts_for(dict(rec, throttled=(rec.get('throttled') or []) + [
            dict(a, account=k) for a, k in zip(applied, acc_applied)]), rejected)
        for a, key in zip(rejected, acc_rejected):
            if a.get('kind') in ('safe', 'skip'):
                _account(ledger, key)['relax_attempts'] += 1
    for a in rec.get('throttled') or []:
        key = a.get('account')
        acc = _account(ledger, key)
        acc['n_throttled'] += 1
        v = by_station.get(a.get('station'))
        if a.get('kind') == 'location' and v is not None and v.get('supply_match') is True:
            confirmed.add(key)              # shadow check: the robot's own search confirmed a throttled claim
    for key in sorted(confirmed):           # recovery: at most RHO_SHADOW per account and mission
        acc = _account(ledger, key)
        back = min(p['c_loc'], acc['loc'] + p['rho_shadow']) - acc['loc']
        acc['loc'] += back
        acc['recovered_loc'] += back
        if back:
            out['charges'].append({'account': key, 'pool': 'loc', 'charge': -round(back, 4), 'recovery': True})
    ledger['missions'] += 1
    for acc in ledger['sources'].values():  # provenance decay: an old false alarm is slowly forgiven
        acc['haz'] = min(p['c_haz'], acc['haz'] + p['rho'])
        for pool in ('loc', 'haz'):         # no float drift: 4 x 0.25 of credit is exactly 1
            acc[pool] = round(acc[pool], 9)
    ledger['history'].append(out)
    return out


def _charge(acc: dict, pool: str, ch: float) -> None:
    acc[pool] = max(0.0, acc[pool] - ch)    # never below zero: admission reserved at least the charge
    acc['debit_' + pool] += ch


def plan_with_credit(ledger: dict, item: str, items: list[dict], mode: str, base: dict | None = None, *,
                     channels: list[str] | None = None, **kw) -> dict:
    """advice.plan on the admitted items only.  `channels[i]` ('file' / 'operator') is where items[i] came from (default:
    all 'file').  The throttled items and every item's account are recorded in the plan's advice record.  Credit applies to
    monotone mode only (the baselines follow advice by definition)."""
    from . import advice
    if mode != 'monotone':
        return advice.plan(item, items, mode, base, **kw)
    raw = list(items or [])
    channels = list(channels) if channels is not None else ['file'] * len(raw)
    if len(channels) != len(raw):
        raise CreditError('one channel per advice item')
    accounts = [account_of(a, c, ledger) for a, c in zip(raw, channels)]
    items = advice.validate(raw, kw.get('stations'))
    kept, throttled = admit(ledger, items, accounts, scrutiny=bool(kw.get('scrutiny')))
    out = advice.plan(item, kept, mode, base, **kw)
    out['advice']['items'] = items
    out['advice']['accounts'] = accounts
    out['advice']['throttled'] = throttled
    out['advice']['credit'] = {k: {'loc': round(v['loc'], 4), 'haz': round(v['haz'], 4)}
                               for k, v in ledger['sources'].items()}
    for a in throttled:
        out['rationale'].append(f'{advice.SOURCE_JA.get(a["source"], a["source"])}の助言は信用を使い切ったため不採用'
                                f'（過去の誤りの分。安全は変わらない）')
    return out


def audit_credit(plan: dict) -> dict:
    """Run audit: every item received is applied, rejected or throttled, exactly once, and every throttled item carries a
    credit reason and a known account.  Raises CreditError."""
    rec = (plan or {}).get('advice') or {}
    if 'throttled' not in rec:
        return {'checked': False}
    key = lambda a: json.dumps({k: a.get(k) for k in ('source', 'kind', 'station', 'text')}, sort_keys=True)
    received = sorted(key(a) for a in rec.get('items') or [])
    accounted = sorted(key(a) for a in (rec.get('applied') or []) + (rec.get('rejected') or []) + rec['throttled'])
    if received != accounted:
        raise CreditError('throttled + acted advice does not add up to the advice received')
    if len(rec.get('accounts') or []) != len(rec.get('items') or []):
        raise CreditError('advice record without one account per item')
    for a in rec['throttled']:
        if not str(a.get('why', '')).startswith('credit exhausted') or a.get('account') not in rec['accounts']:
            raise CreditError('a throttled item without a credit reason or a known account')
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


def _view_p(calls: dict | None) -> float | None:
    """max p(hazard) over the two passes of one view; None if a score is missing or invalid (= a hazard, fail closed)."""
    from .mission_memory import scores_valid, hazard_prob
    calls = calls or {}
    f, s = calls.get('first'), calls.get('second')
    if not (scores_valid(f) and scores_valid(s)):
        return None
    return max(hazard_prob(f), hazard_prob(s))


def classify_station(cp: dict | None, base_tau_h: float = BASE_TAU_H) -> tuple[bool, bool]:
    """(refused for a hazard, refused at the base threshold too) from the per-view scores of one station's checkpoint.
    A station refused for a hazard where every view stays below the base threshold was refused by the caution alone."""
    cp = cp or {}
    d = cp.get('decision') or {}
    refused = d.get('allow') is False and 'supply' not in str(d.get('reason', ''))
    if not refused:
        return False, False
    ps = [_view_p(cp.get('model_calls'))]
    ps += [_view_p(pk.get('model_calls')) for pk in ((cp.get('look_around') or {}).get('peeks') or [])]
    base = any(p is None or p >= base_tau_h for p in ps)
    if not any(p is not None for p in ps) and 'pre_caution_reason' not in d:
        base = True                          # no scores at all: count as a base-rule refusal (never charged)
    return True, base


def visits_from_mission(m: dict, base_tau_h: float = BASE_TAU_H) -> list[dict]:
    """The settlement input, rebuilt from mission.json alone (the robot's own checks, in visiting order):
    recovery.first_station / first_checkpoint, each recovery hop, then the final checkpoint."""
    out = []

    def add(st, cp):
        if st is None or cp is None:
            return
        refused, base = classify_station(cp, base_tau_h)
        peeks = ((cp.get('look_around') or {}).get('peeks') or [])
        out.append({'station': st, 'supply_match': _supply_match(cp), 'refused': refused, 'refused_base': base,
                    'scrutiny_views': len({p.get('side') for p in peeks} & {'L2', 'R2', 'N'})})
    rec = m.get('recovery') or {}
    add(rec.get('first_station'), rec.get('first_checkpoint'))
    for h in rec.get('hops') or []:
        add(h.get('station'), h.get('checkpoint'))
    cp = m.get('checkpoint')
    if isinstance(cp, dict) and 'look_around' not in cp and m.get('look_around'):
        cp = dict(cp, look_around=m['look_around'])
    add(m.get('checkpoint_station'), cp)
    return out
