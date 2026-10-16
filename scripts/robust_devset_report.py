#!/usr/bin/env python3
"""I-05: compare checkpoint variants on dev v1 (48) + dev v2 (128, randomised) offline.

ALLOW iff both passes: argmax == requested supply, p(requested) >= tau_s, p(hazard) < tau_h.
Expected ALLOW iff truth supply == requested AND no fire in view.
Reports errors per condition and the safety margins (closest negatives / positives).
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'


def load(tag_v1, tag_v2):
    rows = []
    for tag, ds in ((tag_v1, 'v1'), (tag_v2, 'v2')):
        for r in json.loads((RES / f'devset_{tag}.json').read_text())['records']:
            r['dataset'] = ds
            r.setdefault('truth_hazard_visible', False)
            rows.append(r)
    return rows


def decide(r, tau_s, tau_h):
    st = r['station']
    for p in (r['passes']['1'], r['passes']['2']):
        sc = p['scores']
        if max(sc['supply_probs'], key=sc['supply_probs'].get) != st or sc['supply_probs'][st] < tau_s:
            return False
        if sc['hazard_prob'] >= tau_h:
            return False
    return True


def condition(r):
    if r['truth_hazard_visible']:
        return 'fire_in_view'
    if r.get('distractor_at'):
        return 'distractor'
    return f"{r['dataset']}:{r.get('lighting', 'default')}"


def evaluate(rows, tau_s, tau_h):
    fa = fd = ok = 0
    errs = []
    for r in rows:
        should = r['truth_supply'] == r['station'] and not r['truth_hazard_visible']
        got = decide(r, tau_s, tau_h)
        ok += got == should
        fa += got and not should
        fd += should and not got
        if got != should:
            errs.append((condition(r), r['image'], 'FALSE_APPROVAL' if got else 'false_denial'))
    return {'tau_s': tau_s, 'tau_h': tau_h, 'n': len(rows), 'correct': ok, 'false_approval': fa,
            'false_denial': fd, 'errors': errs}


def margins(rows):
    pos_s = [min(r['passes'][k]['scores']['supply_probs'][r['station']] for k in '12')
             for r in rows if r['truth_supply'] == r['station']]
    neg_s = [min(r['passes'][k]['scores']['supply_probs'][r['station']] for k in '12')
             for r in rows if r['truth_supply'] != r['station']]
    haz = [max(r['passes'][k]['scores']['hazard_prob'] for k in '12') for r in rows if r['truth_hazard_visible']]
    nohaz = [max(r['passes'][k]['scores']['hazard_prob'] for k in '12') for r in rows if not r['truth_hazard_visible']]
    return {'positive_min_p_requested': round(min(pos_s), 3), 'negative_max_p_requested': round(max(neg_s), 3),
            'fire_hazard_p_min': round(min(haz), 3) if haz else None, 'fire_hazard_p_all': sorted(round(h, 3) for h in haz),
            'no_fire_hazard_p_max': round(max(nohaz), 3)}


def main():
    variants = {'M0_v33': ('qwen3b_scored', 'v2_M0_qwen3b_scored'), 'M1_v34': ('v1_M1_v34', 'v2_M1_v34')}
    out = {}
    for name, (t1, t2) in variants.items():
        if not (RES / f'devset_{t2}.json').is_file():
            continue
        rows = load(t1, t2)
        grid = [evaluate(rows, ts, th) for ts in (0.3, 0.4, 0.5) for th in (0.2, 0.3, 0.5)]
        out[name] = {'margins': margins(rows), 'grid': [{k: v for k, v in g.items() if k != 'errors'} for g in grid],
                     'errors_at_0.5_0.5': evaluate(rows, 0.5, 0.5)['errors']}
        print(name, json.dumps(out[name]['margins'], ensure_ascii=False))
        for g in grid:
            print('   tau_s', g['tau_s'], 'tau_h', g['tau_h'], 'correct', g['correct'], '/', g['n'],
                  'FA', g['false_approval'], 'FD', g['false_denial'])
    (RES / 'i05_robustness_summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')


if __name__ == '__main__':
    sys.exit(main())
