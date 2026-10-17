"""R5 #5: SOFT REFUSAL for caution-only refusals (flag --caution-soft, default off: v3.6 is unchanged).

A station can be refused for three different reasons at the hazard gate:
  * a real hazard : p(hazard) >= tau_h on the standard (v3.6) rule            -> the mission stops at once (always),
  * caution only : the standard rule approves the station, but memory / advice tightened its threshold to
                    tau_mem and tau_mem <= p(hazard) < tau_h (nothing else is wrong)
                                                                              -> with the flag: NO delivery from this
                    station, record 'caution_refusal', continue with the next candidate station of the k-station
                    search order, which gets its own full check (front, side views, its own caution);
  * anything else (wrong supply, low confidence) keeps its v3.6 behaviour.
Safety argument: a delivery still needs an approval of the full check at the station it is delivered from, and that
check is at least as strict as v3.6; the refused station is never delivered from.  What the flag changes is only that
a caution-only refusal no longer ends the mission (the denial-of-service lever of hazard advice, R5 H4b).
Pure functions: no ROS.
"""
from __future__ import annotations
from .mission_memory import hazard_prob, CAUTION_TAU_H

HAZARD = 'visible_hazard_at_checkpoint'
KIND = 'caution_only'


class CautionError(ValueError):
    pass


def front_caution_only(decision: dict | None) -> bool:
    """The front check was refused ONLY because memory / advice tightened the threshold: apply_memory_caution turns an
    approval into a hazard refusal and keeps the approving reason in 'pre_caution_reason'."""
    d = decision or {}
    return (d.get('allow') is False and d.get('reason') == HAZARD and d.get('pre_caution_reason') is not None
            and isinstance(d.get('memory_caution_tau_h'), float))


def classify_view(reason: str, first: dict, second: dict, tau_mem: float | None) -> str:
    """One side view: 'hazard' (the standard rule saw one: p >= tau_h), 'caution_only' (p >= tau_mem only) or 'clear'."""
    if reason == HAZARD:
        return 'hazard'
    if tau_mem is not None and max(hazard_prob(first), hazard_prob(second)) >= tau_mem:
        return 'caution_only'
    return 'clear'


def refusal_record(station: str, where: str, p_max: float, tau_mem: float, base_reason: str, continued: bool,
                   next_station: str | None) -> dict:
    return {'kind': KIND, 'station': station, 'where': where, 'p_max': round(float(p_max), 5), 'tau_mem': float(tau_mem),
            'base_reason': base_reason, 'continued': bool(continued), 'next_station': next_station}


def audit_caution_refusals(mission: dict) -> dict:
    """Run audit.  Soft refusals are legitimate ONLY under the flag and ONLY for caution-only refusals, and the refused
    station must not be the one delivered from.  A mission without any caution refusal passes trivially.  Raises CautionError."""
    recs = mission.get('caution_refusals') or []
    hops = [h for h in ((mission.get('recovery') or {}).get('hops') or []) if h.get('kind') == KIND]
    first_soft = (mission.get('recovery') or {}).get('first_kind') == KIND
    n_soft_hops = len(hops) + (1 if first_soft else 0)
    soft_flag = mission.get('caution_soft') is True
    if (n_soft_hops or recs) and not soft_flag:
        raise CautionError('soft refusal without --caution-soft')
    refused = []
    for r in recs:
        tau, p = r.get('tau_mem'), r.get('p_max')
        if r.get('kind') != KIND or not (isinstance(tau, float) and 0 < tau < 0.05) or not isinstance(p, (int, float)) or p < tau:
            raise CautionError(f'not a caution-only refusal: {r!r}')
        if r.get('base_reason') in (None, HAZARD):
            raise CautionError('a refusal whose standard rule already saw a hazard is not soft')
        refused.append(r['station'])
    if len(set(refused)) != len(refused):
        raise CautionError('a station was caution-refused twice')
    if n_soft_hops != sum(1 for r in recs if r.get('continued')):
        raise CautionError('soft hops and continued caution refusals disagree')
    if mission.get('checkpoint_station') in refused and ((mission.get('checkpoint') or {}).get('decision') or {}).get('allow'):
        raise CautionError('delivered from a caution-refused station')
    return {'n_caution_refusals': len(recs), 'n_continued': n_soft_hops, 'stations': refused,
            'soft_flag': soft_flag}
