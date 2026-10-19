#!/usr/bin/env python3
"""Study Y readout of the saved model outputs (post hoc, descriptive; I-42).  NOT a registered analysis.

The registered Y claims say WHAT happened; the cause taxonomy of the preregistration needs WHY for every run that was not as designed.
For each Y-s run it reads the hazard probability of the first check at the station the robot reached first (the steered station for an
advice arm) from the run record, against the threshold in force (0.05; 0.01 under scrutiny), and the largest probability behind a recorded
refusal (`hazard_refusals` / `caution_refusals`, `p_max`).

  python3 scripts/y_readout.py [--runs outputs/runs]      # -> experiments/results/y_readout.json
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'


def hz(call):
    sc = ((call or {}).get('first') or {}).get('scores') or {}
    return sc.get('hazard_prob'), sc.get('hazard_threshold')


def readout(ledger, runs, summary):
    by = {t['trial_id']: t for t in summary['trials']}
    out = []
    for line in ledger.read_text(encoding='utf8').splitlines():
        r = json.loads(line)
        t = by.get(r['trial_id'])
        if not t or t['cell'] != 'Y-s' or not r.get('final'):
            continue
        row = {'trial_id': r['trial_id'], 'world': r['world'], 'arm': r['config'], 'condition': r['condition'], 'expected': r['expected_action'],
               'observed': r['observed_action'], 'as_designed': t['as_designed'], 'unsafe_delivery': t['unsafe_delivery'], 'run_id': r['run_id'],
               'hazard_refusals': [(x['station'], x['where'], x['p_max']) for x in r.get('hazard_refusals') or []],
               'caution_refusals': [(x['station'], x['where'], x['p_max'], x.get('tau_mem')) for x in r.get('caution_refusals') or []]}
        d = runs / r['run_id'] / 'mission.json'
        if d.is_file():
            m = json.loads(d.read_text(encoding='utf8'))
            p, th = hz((m.get('checkpoint') or {}).get('model_calls'))
            row.update({'last_check_station': m.get('checkpoint_station'), 'last_check_hazard_prob': p, 'last_check_threshold': th, 'have_record': True})
        else:
            row['have_record'] = False
        out.append(row)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', default=str(ROOT / 'outputs/runs'))
    a = ap.parse_args()
    summary = json.loads((RES / 'y_summary.json').read_text(encoding='utf8'))
    rows = readout(RES / 'campaign_Y_ledger.jsonl', Path(a.runs), summary)
    (RES / 'y_readout.json').write_text(json.dumps({'note': 'post hoc, descriptive (I-42); not a registered analysis', 'rows': rows}, ensure_ascii=False, indent=1) + '\n', encoding='utf8')
    for r in rows:
        if not r['as_designed'] or r['arm'] == 'scrutiny_hc':
            print(r['trial_id'], r['world'], r['arm'], r['expected'], '->', r['observed'], 'haz', r['hazard_refusals'], 'caut', r['caution_refusals'],
                  'last', r.get('last_check_station'), r.get('last_check_hazard_prob'), r.get('last_check_threshold'))


if __name__ == '__main__':
    main()
