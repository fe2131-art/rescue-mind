"""I-20: suspicion-triggered extra views (pure functions, shared by the mission node, the run audit and study W).

A station that passed the front check and the two standard side views (+-0.4 m) is still *suspicious* if any of those
views put p(hazard) >= tau_sus (0.005: the 90th percentile of fire-free development views; it covers 17 of the 23 visible
development fires missed at tau_h = 0.05).  The robot then looks from two wider side poses and from closer to the
station; a hazard in any extra view revokes the approval.  Extra views can only add refusals.
"""
from __future__ import annotations
import math


def _p(call) -> float:
    """p(hazard) of one call; missing / malformed / non-finite / out of [0, 1] -> 1.0 (fail-closed, as mission_memory)."""
    from .mission_memory import _hazard_prob
    return _hazard_prob(call)


def suspicion(checkpoint: dict, peeks: list) -> float:
    """Largest p(hazard) over the front check (both passes) and the side views (both passes)."""
    calls = (checkpoint or {}).get('model_calls') or {}
    ps = [_p(calls.get('first')), _p(calls.get('second'))]
    for pk in peeks or []:
        mc = pk.get('model_calls') or {}
        ps += [_p(mc.get('first')), _p(mc.get('second'))]
    return round(max(ps), 4)


def extra_points(waypoint, center, offset: float, near: float):
    """[(side, (x, y))] for L2, R2 (offset beside the waypoint, perpendicular to the view line) and N (near, on it)."""
    wx, wy = waypoint[:2]
    cx, cy = center[:2]
    n = math.hypot(cx - wx, cy - wy) or 1.0
    ux, uy = (cx - wx) / n, (cy - wy) / n
    vx, vy = -uy, ux
    return [('L2', (round(wx - offset * vx, 3), round(wy - offset * vy, 3))),
            ('R2', (round(wx + offset * vx, 3), round(wy + offset * vy, 3))),
            ('N', (round(wx + near * ux, 3), round(wy + near * uy, 3)))]


def required(checkpoint: dict, peeks_standard: list, tau_sus: float) -> bool:
    """Audit: were extra views required by the rule?"""
    return suspicion(checkpoint, peeks_standard) >= tau_sus
