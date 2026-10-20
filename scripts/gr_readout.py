#!/usr/bin/env python3
"""Study GR readout of the saved model outputs (post hoc, descriptive; I-44).  NOT a registered analysis.

For every `v36` fire-world run: the hazard probability of the FRONT check and of the two look-around views (from `mission.json`) against the threshold 0.05, next to the design-mask pixels of that fire (candidate masks, rendered before any
model score).  A refusal that came from a side view is a catch the front-only arm would have missed.  It supports the cause class of every miss (a perception outcome).

  python3 scripts/gr_readout.py [--runs outputs/runs]      # -> experiments/results/gr_readout.json
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


def readout(ledger, runs, summary, masks):
    px = {m['key']: m['fire_pixels'] for m in masks}
    by = {t['trial_id']: t for t in summary['trials']}
    out = []
    for line in ledger.read_text(encoding='utf8').splitlines():
        r = json.loads(line)
        t = by.get(r['trial_id'])
        if not t or t['arm'] != 'v36' or not t['fire'] or not r.get('final'):
            continue
        w = t['world']
        row = {'trial_id': r['trial_id'], 'world': w, 'stratum': t.get('stratum'), 'observed': r['observed_action'], 'delivery_into_fire': t['delivery_into_fire'],
               'mask_px': {'F': px.get(w), 'L': px.get(w + 'L'), 'R': px.get(w + 'R')}}
        d = runs / r['run_id'] / 'mission.json'
        if d.is_file():
            m = json.loads(d.read_text(encoding='utf8'))
            p, th = hz((m.get('checkpoint') or {}).get('model_calls'))
            peeks = [{'side': pk.get('side'), 'p': hz(pk.get('model_calls'))[0]} for pk in ((m.get('look_around') or {}).get('peeks') or [])]
            row['check'] = {'front_p': p, 'threshold': th, 'peeks': peeks}
            row['caught_by_side_view'] = bool(not t['delivery_into_fire'] and p is not None and th is not None and p < th)    # the front check approved (p below tau_h), the run still refused
        out.append(row)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', default=str(ROOT / 'outputs/runs'))
    a = ap.parse_args()
    summary = json.loads((RES / 'gr_summary.json').read_text(encoding='utf8'))
    masks = json.loads((ROOT / 'experiments/campaign_gr_candidates_design_fire_masks.json').read_text(encoding='utf8'))
    rows = readout(RES / 'campaign_GR_ledger.jsonl', Path(a.runs), summary, masks)
    (RES / 'gr_readout.json').write_text(json.dumps({'note': 'post hoc, descriptive (I-44); not a registered analysis', 'rows': rows}, ensure_ascii=False, indent=1) + '\n', encoding='utf8')
    n_side = sum(bool(r.get('caught_by_side_view')) for r in rows)
    print(f'{len(rows)} v36 fire runs; {sum(r["delivery_into_fire"] for r in rows)} misses; {n_side} refused after the front check had approved (caught by a side view)')
    for r in rows:
        if r['delivery_into_fire']:
            print(r['trial_id'], r['world'], r['stratum'], 'mask', r['mask_px'], r.get('check'))


if __name__ == '__main__':
    main()
