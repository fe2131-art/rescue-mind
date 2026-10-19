"""I-42: CONTINUE AFTER A HAZARD REFUSAL (flag --hazard-continue, default off: v3.6 is unchanged).

v3.6 ends the mission at the first real hazard ("no search into a possible danger").  With duplicate supplies this turns a
truthful tip into a lost delivery: advice moves the burning bay to the front, the check refuses it, and the clean bay that the
no-advice robot would have used is never visited (study X-s: tighten-only gave up 2 deliveries, scrutiny 5).

With the flag, a REAL hazard (the standard v3.6 rule, p(hazard) >= tau_h on valid scores; not a caution-only refusal, which is
--caution-soft) at the front or at a side view marks the station as refused, writes it to memory like any observation, and the
robot goes on to the next candidate of the k-station order, which gets its own full check.
What does not change (this is why Proposition 2 stays as it is):
  * a delivery still needs an approving full check at the station it is delivered from, and that check is the v3.6 check
    (tightened, never loosened, by advice);
  * the refused station is never delivered from;
  * the visited stations are a prefix of the candidate order, at most k.
What changes is exposure: every further visit is another chance of a missed fire (epsilon per station), also for a robot without
advice that carries the flag.  A broken view (invalid score) never continues: it fails closed as before.
Pure functions: no ROS.
"""
from __future__ import annotations
from .mission_memory import hazard_prob, scores_valid

HAZARD = 'visible_hazard_at_checkpoint'
KIND = 'hazard'


class HazardContinueError(ValueError):
    pass


def real_front_hazard(decision: dict | None, first: dict | None, second: dict | None) -> bool:
    """The front check refused because the STANDARD rule saw a hazard: a refusal for the hazard reason that is not the memory /
    advice caution turning an approval into a refusal (that one keeps 'pre_caution_reason'), on valid scores."""
    d = decision or {}
    return (d.get('allow') is False and d.get('reason') == HAZARD and d.get('pre_caution_reason') is None
            and scores_valid(first) and scores_valid(second))


def real_side_hazard(reason: str, first: dict | None, second: dict | None, tau_mem: float | None) -> bool:
    """One side view is a REAL hazard (not caution-only, not broken): hazard reason, valid scores, and the standard
    threshold (tau_h = 0.05) was reached by the stronger of the two readings."""
    from .caution_soft import classify_view
    return (reason == HAZARD and scores_valid(first) and scores_valid(second)
            and classify_view(reason, first or {}, second or {}, tau_mem) == 'hazard')


def refusal_record(station: str, where: str, p_max: float, continued: bool, next_station: str | None) -> dict:
    return {'kind': KIND, 'station': station, 'where': where, 'p_max': round(float(p_max), 5),
            'continued': bool(continued), 'next_station': next_station}


def audit_hazard_refusals(mission: dict) -> dict:
    """Run audit.  A hazard hop is legitimate ONLY under the flag, the refused station is not the one delivered from, and the
    recorded refusals agree with the hops.  A mission without any hazard hop passes trivially.  Raises HazardContinueError."""
    rec = mission.get('recovery') or {}
    hops = [h for h in (rec.get('hops') or []) if h.get('kind') == KIND]
    first_hz = rec.get('first_kind') == KIND
    n_hz = len(hops) + (1 if first_hz else 0)
    recs = mission.get('hazard_refusals') or []
    flag = mission.get('hazard_continue') is True
    if (n_hz or recs) and not flag:
        raise HazardContinueError('hazard hop without --hazard-continue')
    refused = [r.get('station') for r in recs]
    if len(set(refused)) != len(refused):
        raise HazardContinueError('a station was hazard-refused twice')
    for r in recs:
        # whether p_max reached the standard threshold is recomputed from the saved model outputs (recovery_evidence)
        if r.get('kind') != KIND or not isinstance(r.get('p_max'), (int, float)):
            raise HazardContinueError(f'not a real hazard refusal: {r!r}')
    if n_hz != sum(1 for r in recs if r.get('continued')):
        raise HazardContinueError('hazard hops and continued hazard refusals disagree')
    if mission.get('checkpoint_station') in refused and ((mission.get('checkpoint') or {}).get('decision') or {}).get('allow'):
        raise HazardContinueError('delivered from a hazard-refused station')
    return {'n_hazard_refusals': len(recs), 'n_continued': n_hz, 'stations': refused, 'flag': flag}
