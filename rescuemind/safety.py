"""Conservative dual-model decision fusion; does not replace Nav2 costmaps."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any
from math import isfinite

ALLOWED_SUPPLIES = ("water", "medicine")
ALLOWED_SCENES = ("clear", "hazard", "unknown")

@dataclass(frozen=True)
class Decision:
    allow: bool
    reason: str
    expected: str
    jev_supply: str
    qwen_supply: str
    jev_scene: str
    qwen_scene: str
    jev_confidence: float
    jev_hazard_probability: float
    jev_supply_presence: float

    def to_dict(self):
        return asdict(self)


def decide(expected: str, jev: dict[str, Any] | None, qwen: dict[str, Any] | None,
           min_jev_confidence: float = 0.65, max_hazard_prob: float = 0.20, min_presence: float = 0.80) -> Decision:
    """Fail closed. Jev MUST be present. Heuristic thresholds need validation.

    This is not probability calibration or a safety certification.
    In particular, a camera image cannot identify a hazard's 3D map coordinates.
    """
    if expected not in ALLOWED_SUPPLIES:
        raise ValueError("unexpected supply")
    jev = jev or {}
    qwen = qwen or {}
    js = str(jev.get("supply", "unknown"))
    qs = str(qwen.get("supply", "unknown"))
    jscene = str(jev.get("scene", "unknown"))
    qscene = str(qwen.get("scene", "unknown"))
    jconf = float(jev.get("supply_confidence", 0.0))
    hazard = float(jev.get("hazard_probability", 1.0))
    presence = float(jev.get("supply_present_probability", 0.0))
    reason = "approved"
    if not jev or not qwen:
        reason = "missing_model_result"
    elif not jev.get("real_model", False) or not qwen.get("real_model", False):
        reason = "mock_results_not_authorized"
    elif not all(isfinite(x) for x in (jconf, hazard, presence)) or jconf < min_jev_confidence or not (0 <= jconf <= 1) or not (0 <= hazard <= 1):
        reason = "jev_low_confidence_or_invalid"
    elif not (0 <= presence <= 1) or presence < min_presence:
        reason = "jev_supply_not_confirmed"
    elif js != expected or qs != expected:
        reason = "supply_mismatch_or_disagreement"
    elif jscene != "clear" or qscene != "clear" or hazard > max_hazard_prob:
        reason = "hazard_or_uncertain_scene"
    return Decision(reason == "approved", reason, expected, js, qs, jscene, qscene, jconf, hazard, presence)
