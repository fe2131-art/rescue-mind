#!/usr/bin/env python3
"""Overlap of the missed visible fires of the first checker (Qwen3.5-9B, v3.6 = h36 wording + tiles, tau_h 0.05)
and the second model (Clef-Flash, task wording) on the DEVELOPMENT sets DH + DH2 (no test data).

A fire is 'missed' by a checker if that checker would APPROVE the view (the same rules as scripts/i13_select.py:
Qwen: q_allows at tau_h 0.05; Clef: j_allows at hazard threshold 0.05).  Also reported: a hazard-question-only variant
(Qwen hazard_prob >= 0.05 in either pass; Clef hazard_probability >= 0.05).
Output: experiments/results/jev_overlap.json
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from i13_select import load, q_allows, j_allows  # noqa: E402

RES = ROOT / 'experiments/results'
TAU = 0.05


def wilson(k, n, z=1.959964):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def summarize(pairs):
    """pairs: list of (qwen_missed, clef_missed) over visible fires."""
    both = sum(a and b for a, b in pairs)
    q_only = sum(a and not b for a, b in pairs)
    c_only = sum(b and not a for a, b in pairs)
    neither = sum(not a and not b for a, b in pairs)
    qm = both + q_only
    cm = both + c_only
    lo, hi = wilson(both, qm) if qm else (float('nan'),) * 2
    return {'n_fires': len(pairs), 'both_miss': both, 'qwen_only_miss': q_only, 'clef_only_miss': c_only, 'neither_miss': neither,
            'qwen_miss': qm, 'clef_miss': cm, 'p_clef_miss_given_qwen_miss': both / qm if qm else None,
            'p_clef_miss_given_qwen_miss_wilson': [lo, hi],
            'jaccard': both / (both + q_only + c_only) if (both + q_only + c_only) else None}


def main():
    pairs, pairs_h = [], []
    for s in ('dh', 'dh2'):
        q = load(f'{s}_i11_h36_tiles')
        c = load(f'{s}_clef2')
        for key, r in q.items():
            if r.get('hazard_visibility') != 'visible':
                continue
            cr = c[key]
            pairs.append((q_allows(r, TAU), j_allows(cr, TAU)))
            qh = all('error' not in r['passes'][k] and r['passes'][k]['scores']['hazard_prob'] < TAU for k in '12')
            ch = 'hazard_probability' in (cr.get('clef') or {}) and cr['clef']['hazard_probability'] < TAU
            pairs_h.append((qh, ch))
    out = {'definition': __doc__, 'tau_h': TAU, 'full_rule': summarize(pairs), 'hazard_question_only': summarize(pairs_h)}
    (RES / 'jev_overlap.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps({k: v for k, v in out.items() if k != 'definition'}, indent=1))


if __name__ == '__main__':
    main()
