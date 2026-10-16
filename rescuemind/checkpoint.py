"""On-site AI supply validation for the second leg of a simulated robot mission.

Jev 1.14.0 is mandatory; Qwen must agree. This checks supply identity ONLY.
It does not classify the corridor as clear or prove physical pickup.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from hashlib import sha256
from math import isfinite
from pathlib import Path
from typing import Callable

from . import jev, qwen35


@dataclass(frozen=True)
class CheckpointDecision:
    allow: bool
    reason: str
    expected: str
    jev_supply: str
    qwen_supply: str
    jev_confidence: float
    jev_presence: float
    jev_hazard: float | None
    jev_scene: str
    qwen_scene: str

    def to_dict(self):
        return asdict(self)


def decide_checkpoint(expected: str, j: dict | None, q: dict | None,
                      confidence_threshold: float = .65, presence_threshold: float = .80,
                      hazard_threshold: float = .35) -> CheckpointDecision:
    if expected not in ('water', 'medicine'):
        raise ValueError('unsupported supply')
    j, q = j or {}, q or {}
    try:
        conf = float(j.get('supply_confidence', -1))
        presence = float(j.get('supply_present_probability', -1))
    except (TypeError, ValueError):
        conf = presence = -1
    try:
        hazard = float(j.get('hazard_probability', float('nan')))
    except (TypeError, ValueError):
        hazard = float('nan')
    if not (isfinite(hazard) and 0 <= hazard <= 1):
        hazard = None  # Avoid non-standard JSON NaN/Infinity in failure evidence
    jscene = str(j.get('scene', 'unknown'))
    qscene = str(q.get('scene', 'unknown'))
    js = str(j.get('supply', 'unknown'))
    qs = str(q.get('supply', 'unknown'))
    if not j or not q:
        reason = 'missing_model_result'
    elif j.get('real_model') is not True or q.get('real_model') is not True:
        reason = 'unverified_model_provenance'
    elif j.get('model') != jev.MODEL_ID:
        reason = 'incorrect_jev_checkpoint'
    elif q.get('model') not in ('qwen3.8-omni-flash', qwen35.DEFAULT_MODEL, qwen35.DEFAULT_MODEL.split('/')[-1]):
        reason = 'incorrect_qwen_checkpoint'
    elif not (isfinite(conf) and isfinite(presence) and 0 <= conf <= 1 and 0 <= presence <= 1):
        reason = 'invalid_probability'
    elif conf < confidence_threshold or presence < presence_threshold:
        reason = 'insufficient_jev_evidence'
    elif not (hazard is not None and jscene in ('clear', 'hazard', 'unknown') and qscene in ('clear', 'hazard', 'unknown')):
        reason = 'missing_or_invalid_hazard_observation'
    elif hazard >= hazard_threshold or jscene == 'hazard' or qscene == 'hazard':
        reason = 'visible_hazard_at_checkpoint'
    elif js != expected or qs != expected:
        reason = 'models_disagree_or_wrong_supply'
    else:
        reason = 'on_site_supply_confirmed'
    return CheckpointDecision(reason == 'on_site_supply_confirmed', reason, expected, js, qs, conf, presence,
                              hazard, jscene, qscene)


def verify_station(image_path: str | Path, expected: str, *, qwen_model: str, endpoint: str,
                   jev_client: Callable | None = None, qwen_client: Callable | None = None) -> dict:
    """Real API calls unless explicit injection for OFFLINE TESTS only.

    No fake response in production; failures are raised and caller must stop.
    Must be invoked only on a fresh ROS camera frame captured at the station.
    """
    image = Path(image_path)
    if not image.is_file() or image.stat().st_size < 300:
        raise ValueError('on-site camera frame missing or empty')
    jev_client = jev_client or jev.infer_checkpoint
    qwen_client = qwen_client or qwen35.infer
    j = jev_client(image)
    q = qwen_client(image, model=qwen_model, endpoint=endpoint)
    dec = decide_checkpoint(expected, j, q)
    return {'checkpoint_type': 'on_site_camera_supply_check',
            'image_sha256': sha256(image.read_bytes()).hexdigest(),
            'model_calls': {'jev': j, 'qwen': q},
            'decision': dec.to_dict(),
            'limitations': 'Visible hazard triggers denial. An unknown or apparently clear shelf view cannot prove path safety. No physical pickup.'}
