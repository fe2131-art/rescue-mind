#!/usr/bin/env python3
"""Offline decision analysis of saved dev-set responses (no model calls).

Decision rule under test (same as rescuemind.local_vision.local_decision):
ALLOW iff both passes name the requested supply, each with probability >= tau
(scored method only), and neither pass flags a hazard.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def decide(rec, tau):
    station = rec['station']
    for k in ('1', '2'):
        p = rec['passes'][k]
        if 'error' in p:
            return False
        if p['scene'] == 'hazard' or p['supply'] != station:
            return False
        sc = p.get('scores')
        if sc and sc['supply_probs'][station] < tau:
            return False
    return True


def table(path, taus):
    d = json.loads(Path(path).read_text())
    recs = d['records']
    rows = []
    for tau in taus:
        tp = fp = tn = fn = 0
        for r in recs:
            should = r['truth_supply'] == r['station']
            got = decide(r, tau)
            tp += should and got; fn += should and not got
            fp += (not should) and got; tn += (not should) and not got
        rows.append({'tau': tau, 'allow_correct': tp, 'false_denial': fn, 'false_approval': fp,
                     'deny_correct': tn, 'n': len(recs),
                     'decision_accuracy': round((tp + tn) / len(recs), 3)})
    lat = [p['latency_s'] for r in recs for p in r['passes'].values()]
    errs = sum('error' in p for r in recs for p in r['passes'].values())
    return {'tag': d['tag'], 'model': d['model'], 'parse_or_http_errors': errs,
            'mean_latency_per_pass_s': round(sum(lat) / len(lat), 3), 'rows': rows}


if __name__ == '__main__':
    out = []
    for tag in sys.argv[1:] or ['qwen3b_json_baseline', 'qwen3b_scored', 'smolvlm2_scored']:
        f = ROOT / 'experiments/results' / f'devset_{tag}.json'
        if f.is_file():
            out.append(table(f, [0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95]))
    dest = ROOT / 'experiments/results/devset_summary.json'
    dest.write_text(json.dumps(out, indent=1) + '\n')
    for t in out:
        print(t['tag'], 'errors', t['parse_or_http_errors'], 'latency/pass', t['mean_latency_per_pass_s'])
        for r in t['rows']:
            print('   ', r)
