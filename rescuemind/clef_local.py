"""I-13: the original plan's Jev checkpoint, answered locally by Cloudflare Clef-Flash (Jev/SystemOne-compatible).

The request is exactly rescuemind.jev.build_request (supply choice, visible-supply noul, hazard noul, scene
choice); only the Box question is omitted because the local model does not provide boxes.  The parsed result
has the same fields as rescuemind.jev.parse_response, so rescuemind.checkpoint.decide_checkpoint-style rules
apply unchanged.
"""
from __future__ import annotations
import json
import urllib.request
from math import isfinite
from pathlib import Path

from . import jev

MODEL_ID = 'Cloudflare/clef-flash'
DEFAULT_URL = 'http://127.0.0.1:8767/v1/systemone'


def build_request(image_bytes: bytes) -> dict:
    req = jev.build_request(image_bytes, 'jpeg', include_box=False)
    req['model'] = MODEL_ID
    return req


def build_request_task(image_bytes: bytes) -> dict:
    """I-13 (fairness check): the same decision asked in the words of THIS task (supply platform, any fire or
    smoke) instead of the original Jev request, whose hazard/scene questions are about a corridor/passage."""
    import base64, uuid
    ref = str(uuid.uuid4())
    return {
        'model': MODEL_ID,
        'state': {'camera': ref, 'task': 'A rescue robot stopped in front of a grey emergency supply platform and '
                                          'must decide whether the requested supply is on it and whether it is safe.'},
        'assets': {ref: {'type': 'image', 'format': 'jpeg', 'data_base64': base64.b64encode(image_bytes).decode('ascii')}},
        'questions': {
            'supply': {'type': 'choice', 'instructions': 'What is placed on top of the grey platform in `camera`?',
                       'criteria': {'water': 'Drinking water: plastic water bottles with caps',
                                    'medicine': 'A first-aid kit: a box marked with a red cross',
                                    'other': 'Nothing, or some other object'}},
            'visible_supply': {'type': 'noul', 'instructions': 'Is a water bottle pack or a first-aid kit clearly visible '
                                                               'on top of the platform in `camera`?'},
            'hazard': {'type': 'noul', 'instructions': 'Is there any fire, flame or smoke anywhere in `camera`, even if it '
                                                       'is small, partly hidden behind objects, or cut off at the edge?'},
            'scene': {'type': 'choice', 'instructions': 'Is the area around the platform in `camera` safe?',
                      'criteria': {'clear': 'No fire, smoke or danger is visible', 'hazard': 'Fire, flame or smoke is visible',
                                   'unknown': 'Cannot tell'}},
        },
    }


def parse(payload: dict) -> dict:
    if payload.get('model') != MODEL_ID or payload.get('real_inference') is not True:
        raise ValueError('not a local Clef-Flash result')
    a = payload['answers']
    supply, scene, hazard, visible = a['supply'], a['scene'], a['hazard'], a['visible_supply']
    if (supply.get('type'), scene.get('type'), hazard.get('type'), visible.get('type')) != ('choice', 'choice', 'noul', 'noul'):
        raise ValueError('invalid Clef answer types')
    if supply['choice'] not in ('water', 'medicine', 'other') or scene['choice'] not in ('clear', 'hazard', 'unknown'):
        raise ValueError('out-of-vocabulary Clef decision')
    vals = (float(supply['confidence']), float(visible['noul']), float(hazard['noul']))
    if not all(isfinite(v) and 0 <= v <= 1 for v in vals):
        raise ValueError('invalid Clef probability')
    return {'real_model': True, 'model': MODEL_ID, 'supply': supply['choice'], 'supply_confidence': vals[0],
            'supply_probabilities': supply.get('probabilities'), 'supply_present_probability': vals[1],
            'hazard_probability': vals[2], 'scene': scene['choice'], 'scene_probabilities': scene.get('probabilities'),
            'latency_s': (payload.get('usage') or {}).get('latency_s')}


def infer(image_path: str | Path, url: str = DEFAULT_URL, timeout: float = 120.0, schema: str = 'jev') -> dict:
    if not url.startswith('http://127.0.0.1:'):
        raise ValueError('local Clef must be on the loopback interface')
    builder = build_request if schema == 'jev' else build_request_task
    body = json.dumps(builder(jev.prepare_image(image_path))).encode()
    req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as f:
        return parse(json.load(f))


def jev_role_allows(j: dict, expected: str, *, confidence: float = .65, presence: float = .80,
                    hazard: float = .35) -> tuple[bool, str]:
    """The Jev half of rescuemind.checkpoint.decide_checkpoint, with the original thresholds."""
    if j['supply_confidence'] < confidence or j['supply_present_probability'] < presence:
        return False, 'insufficient_jev_evidence'
    if j['hazard_probability'] >= hazard or j['scene'] == 'hazard':
        return False, 'visible_hazard_at_checkpoint'
    if j['supply'] != expected:
        return False, 'models_disagree_or_wrong_supply'
    return True, 'on_site_supply_confirmed'
