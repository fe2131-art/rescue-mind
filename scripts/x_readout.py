#!/usr/bin/env python3
"""Study X-s readout of the saved model outputs (post hoc, descriptive; I-41).  NOT a registered analysis.

The registered X-s endpoints say WHAT happened in each steering run (refused / delivered).  This reads WHY from the run records:
the hazard probability of the front view and of each look-around peek at the steered station, against the threshold in force.
Needed for the cause taxonomy of the preregistration (a perception outcome, a navigation stall, an infrastructure fault, other):
a refusal is a perception outcome only if the record shows the check scoring the picture, not a threshold that sits at the noise floor.

  python3 scripts/x_readout.py [--runs outputs/runs]      # -> experiments/results/x_readout.json
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'
MAIN = Path(__file__).resolve().parents[1]
for p in Path(__file__).resolve().parents:
    if p.name == 'worktrees' and p.parent.name == '.claude':
        MAIN = p.parents[1]
        break


def hz(call):
    """hazard_prob and threshold of the first pass of a model_calls record (the second pass is the same scene, same score)."""
    sc = ((call or {}).get('first') or {}).get('scores') or {}
    return sc.get('hazard_prob'), sc.get('hazard_threshold')


def run_dir(runs, rid):
    for base in (runs, MAIN / 'outputs/runs'):
        if (base / rid / 'mission.json').is_file():
            return base / rid
    return None


def readout(ledger, runs):
    arms = {t['trial_id']: t['arm'] for t in json.loads((RES / 'x_summary.json').read_text(encoding='utf8'))['trials']}
    out = []
    for line in ledger.read_text(encoding='utf8').splitlines():
        r = json.loads(line)
        if r.get('condition') not in ('steer_fire', 'steer_clean') or not r.get('final'):
            continue
        d = run_dir(runs, r['run_id'])
        row = {'trial_id': r['trial_id'], 'world': r['world'], 'arm': arms.get(r['trial_id']),
               'condition': r['condition'], 'observed': r['observed_action'], 'run_id': r['run_id'], 'have_record': d is not None}
        if d is not None:
            m = json.loads((d / 'mission.json').read_text(encoding='utf8'))
            ck = m.get('checkpoint') or {}
            p, th = hz(ck.get('model_calls'))
            peeks = [(pk.get('side'),) + hz(pk.get('model_calls')) for pk in ((m.get('look_around') or {}).get('peeks') or [])]
            row.update({'front_hazard_prob': p, 'front_threshold': th, 'peeks': [{'side': s, 'hazard_prob': a, 'threshold': b} for s, a, b in peeks],
                        'tau_h_caution': ((m.get('memory') or {}).get('caution') or {}).get(m.get('checkpoint_station'), {}).get('tau_h'),
                        'station': m.get('checkpoint_station')})
            seen = [x for x in [p] + [a for _, a, _ in peeks] if x is not None]
            row['max_view_hazard_prob'] = max(seen) if seen else None
        out.append(row)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', default=str(ROOT / 'outputs/runs'))
    a = ap.parse_args()
    rows = readout(RES / 'campaign_X_ledger.jsonl', Path(a.runs))
    res = {'note': 'post hoc, descriptive (I-41); not a registered analysis', 'rows': rows}
    (RES / 'x_readout.json').write_text(json.dumps(res, ensure_ascii=False, indent=1) + '\n', encoding='utf8')
    for r in rows:
        print(r['trial_id'], r['condition'], r['arm'], r['world'], 'front', r.get('front_hazard_prob'), 'th', r.get('front_threshold'),
              'peeks', [(p['side'], p['hazard_prob']) for p in r.get('peeks', [])], '->', r['observed'])


if __name__ == '__main__':
    main()
