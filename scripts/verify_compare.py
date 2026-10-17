#!/usr/bin/env python3
"""make verify: compare a fresh z3 run with the committed record (experiments/results/smt_advice_proof.json).
Same query names and the same verdicts (unsat / sat, proved) are required; timings are reported, not compared.
  python3 scripts/verify_compare.py <fresh.json>"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verdicts(d):
    return {p['name']: (p['result'], p.get('proved')) for p in d['proofs']}


def main():
    ref = json.loads((ROOT / 'experiments/results/smt_advice_proof.json').read_text())
    new = json.loads(Path(sys.argv[1]).read_text())
    a, b = verdicts(ref), verdicts(new)
    diff = sorted(n for n in set(a) | set(b) if a.get(n) != b.get(n))
    n_unsat = sum(1 for v in b.values() if v[0] == 'unsat')
    print(f"queries {len(b)} (committed {len(a)}), unsat {n_unsat}, solver {new['seconds_total']:.1f} s, z3 {new['env']['z3']}")
    print(f"differential cases {new.get('differential_total_cases')}, code mutants {new.get('code_mutants') and len(new['code_mutants'])}")
    if diff:
        print('VERDICTS DIFFER from the committed record:')
        for n in diff:
            print(f'  {n}: committed {a.get(n)} now {b.get(n)}')
        sys.exit(1)
    print('VERIFY_OK: every verdict equals the committed record')


if __name__ == '__main__':
    main()
