#!/usr/bin/env python3
"""Recompute the I-14 pilot numbers: look-around hazard probability for each denial in
experiments/results/i14_pilot_ledger.jsonl (read from outputs/runs/<run_id>/mission.json,
which is git-ignored, so this works only on the machine that ran the pilot), and the
I-01 dead-reckoning error range from experiments/results/i01_drift/{baseline,sphere_wheels}.json."""
import json, pathlib
R = pathlib.Path(__file__).resolve().parents[1]

def peek_p(run):
    m = json.load(open(R/'outputs/runs'/run/'mission.json'))
    return [max(c['scores']['hazard_prob'] for c in pk['model_calls'].values() if 'scores' in c)
            for pk in m.get('look_around', {}).get('peeks', [])]

ps = []
for l in open(R/'experiments/results/i14_pilot_ledger.jsonl'):
    d = json.loads(l)
    if str(d.get('observed_action', '')).startswith('DENY_HAZARD'):
        try: p = peek_p(d['run_id'])
        except FileNotFoundError: print(d['trial_id'], d['run_id'], 'run output missing'); continue
        print(d['trial_id'], d.get('world'), d['observed_action'], 'side p =', p)
        ps.append(max(p))
if ps: print(f'I-14 deciding side-view hazard p (max per denial): n={len(ps)} range {min(ps):.2f}-{max(ps):.2f}')

for v in ('baseline', 'sphere_wheels'):
    j = json.load(open(R/f'experiments/results/i01_drift/{v}.json'))
    e = [r['pos_error_m'] for r in j['patterns']['medicine_route']]
    print(f'I-01 {v} medicine_route pos_error_m: {e} (min {min(e)}, max {max(e)})')
