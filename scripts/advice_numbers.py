#!/usr/bin/env python3
"""I-23 / I-24 numbers for the README, the explanatory PDF and the consistency check (single source: the result files).

  smt_facts()     <- experiments/results/smt_advice_proof.json   (z3 proofs, differential test, injected bugs)
  credit_facts()  <- experiments/results/advice_credit_horizon.json  (descriptive 100-mission model of the advice credit; not registered)
  pending_studies() -> {'IF': bool, 'B': bool}  (True = summary file exists)

Every function returns None when its file is missing, so a document says 'pending' instead of inventing a number.
"""
from __future__ import annotations
import json
from pathlib import Path

RES = Path(__file__).resolve().parents[1] / 'experiments/results'


def _load(name):
    f = RES / name
    try:
        return json.loads(f.read_text(encoding='utf8')) if f.is_file() else None
    except ValueError:
        return None


def smt_facts():
    d = _load('smt_advice_proof.json')
    if not d:
        return None
    proofs = d['proofs']
    diff = d['differential']
    mut = d['code_mutants']
    nec = d.get('necessity', [])
    return {
        'unsat': sum(p['result'] == 'unsat' for p in proofs),
        'queries': len(proofs),
        'cases': d['differential_total_cases'],
        'groups': len(diff), 'per_group': diff['plan']['n'],
        'disagreements': sum(v.get('disagreements', 0) for v in diff.values()),
        'mutants': len(mut),
        'caught': sum(1 for m in mut if m['detect_differential']['detected'] or m['detect_property']['detected']),
        'necessity_relaxing': sum(1 for n in nec if n['result'] == 'sat'),
        'necessity_tighten_unsat': any(n['result'] == 'unsat' and n['interface'].startswith('tighten-only') for n in nec),
        'unsafe_rate': next((n['counterexample']['unsafe_rate'] for n in nec if n['result'] == 'sat' and n.get('counterexample')), None),
        'eps_any': next((n['counterexample']['eps_any'] for n in nec if n['result'] == 'sat' and n.get('counterexample')), None),
        'z3': d['env']['z3'],
    }


def credit_facts():
    c = _load('advice_credit_horizon.json')
    if not c:
        return None
    r = c['runs']
    last = lambda k: r[k]['series'][-1]
    p = c['params']
    return {
        'liar_no': last('k4/liar/monotone')['extra_s'], 'liar_yes': last('k4/liar/credit')['extra_s'],
        'adaptive_yes': last('k4/farmer/credit')['extra_s'],
        'honest_no': -last('k4/honest/monotone')['extra_s'], 'honest_yes': -last('k4/honest/credit')['extra_s'],
        'flood_no': last('k4/flooder_real/monotone')['false_refusals'], 'flood_yes': last('k4/flooder_real/credit')['false_refusals'],
        'flood_delta': c['delta_real'],
        'noisy_keep': 100 * last('k4/noisy/credit')['extra_s'] / last('k4/noisy/monotone')['extra_s'],
        'missions': len(r['k4/liar/credit']['series']),
        'unsafe_equal': all(v.get('unsafe') == r[k.replace('/credit', '/monotone')].get('unsafe')
                            for k, v in r.items() if k.endswith('/credit')),
        'k4': {src: {'extra_s': (last(f'k4/{src}/monotone')['extra_s'], last(f'k4/{src}/credit')['extra_s']),
                     'false_refusals': (last(f'k4/{src}/monotone')['false_refusals'], last(f'k4/{src}/credit')['false_refusals'])}
               for src in ('honest', 'noisy', 'liar', 'farmer', 'flooder', 'flooder_real')},
        'c_loc': p['c_loc'], 'c_haz': p['c_haz'], 'rho': p['rho'], 'rho_shadow': p['rho_shadow'],
    }


def pending_studies():
    return {k: (RES / f).is_file() for k, f in (('IF', 'if_summary.json'), ('B', 'b_summary.json'))}
