"""Honest paired selective-classifier reporting with Wilson confidence intervals.

Confidence intervals are descriptive binomial intervals and rely on
independent experiment cases. Shared scene correlation is not corrected.
"""
from __future__ import annotations
import math
from collections import Counter


def wilson_interval(successes: int, trials: int, z: float = 1.959963984540054):
    if trials <= 0:
        return None
    if not 0 <= successes <= trials:
        raise ValueError('successes outside trial range')
    p = successes / trials
    den = 1 + z*z/trials
    c = (p + z*z/(2*trials))/den
    h = z*math.sqrt(p*(1-p)/trials + z*z/(4*trials*trials))/den
    return [round(max(0, c-h), 4), round(min(1, c+h), 4)]


def validate_unique(records):
    ids = [str(r.get('id','')) for r in records]
    if any(not i for i in ids) or len(ids) != len(set(ids)):
        raise ValueError('Duplicate or empty case IDs: use independent observations')
    pairs = []
    for r in records:
        h = r.get('image_sha256')
        if h:
            for key in ('supply','corridor'):
                if not isinstance(h.get(key), str) or len(h[key]) != 64:
                    raise ValueError('Invalid image SHA256')
            if h['supply'] == h['corridor']:
                raise ValueError('Same image used as supply and corridor')
            pairs.append((h['supply'],h['corridor']))
    if len(pairs) != len(set(pairs)):
        raise ValueError('Duplicate supply/corridor image pairs')


def enrich(scores: dict) -> dict:
    for item in scores.values():
        n = item['n']
        item['coverage_wilson95'] = wilson_interval(item['approved'], n)
        item['unsafe_approval_wilson95'] = wilson_interval(item['unsafe_approved'], n)
        item['precision_wilson95'] = wilson_interval(item['correct_approved'], item['approved'])
    return scores
