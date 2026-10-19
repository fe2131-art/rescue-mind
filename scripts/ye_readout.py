#!/usr/bin/env python3
"""Study YE readout of the saved model outputs (post hoc, descriptive; I-43).  NOT a registered analysis.

For every `hc` run: the hazard probability the check gave the SECOND bay (the one with the small partly hidden fire), against the threshold 0.05 -- the largest probability behind a
recorded hazard refusal there (`hazard_refusals`), or, when the run delivered from the second bay, the probabilities of the check that approved it (front view and the two
look-around views) -- next to the design-mask pixels of that fire at the front pose and the two side poses (the candidate masks, rendered before any model score).
It supports the cause class of every unsafe delivery (a perception outcome) and shows which kind of fire the check missed.

  python3 scripts/ye_readout.py [--runs outputs/runs]      # -> experiments/results/ye_readout.json
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
        if not t or t['arm'] != 'hc' or not r.get('final'):
            continue
        w, second = t['world'], t['second_bay']
        refs = {x['station']: (x['where'], x['p_max']) for x in r.get('hazard_refusals') or []}
        row = {'trial_id': r['trial_id'], 'world': w, 'observed': r['observed_action'], 'unsafe_delivery': t['unsafe_delivery'], 'second_bay': second,
               'mask_px': {'F': px.get(w), 'L': px.get(w + 'L'), 'R': px.get(w + 'R')}, 'second_bay_refusal': refs.get(second), 'first_bay_refusal': refs.get(t['first_bay'])}
        d = runs / r['run_id'] / 'mission.json'
        if d.is_file():
            m = json.loads(d.read_text(encoding='utf8'))
            if t['unsafe_delivery']:
                ck = m.get('checkpoint') or {}
                p, th = hz(ck.get('model_calls'))
                peeks = [(pk.get('side'),) + hz(pk.get('model_calls')) for pk in ((m.get('look_around') or {}).get('peeks') or [])]
                row['approved_check'] = {'station': m.get('checkpoint_station'), 'front_p': p, 'threshold': th, 'peeks': [{'side': s, 'p': a} for s, a, _ in peeks]}
        out.append(row)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', default=str(ROOT / 'outputs/runs'))
    a = ap.parse_args()
    summary = json.loads((RES / 'ye_summary.json').read_text(encoding='utf8'))
    masks = json.loads((ROOT / 'experiments/campaign_ye_candidates_design_fire_masks.json').read_text(encoding='utf8'))
    rows = readout(RES / 'campaign_YE_ledger.jsonl', Path(a.runs), summary, masks)
    (RES / 'ye_readout.json').write_text(json.dumps({'note': 'post hoc, descriptive (I-43); not a registered analysis', 'rows': rows}, ensure_ascii=False, indent=1) + '\n', encoding='utf8')
    for r in rows:
        print(r['trial_id'], r['world'], r['observed'], 'mask', r['mask_px'], 'refusal2', r['second_bay_refusal'], r.get('approved_check'))


if __name__ == '__main__':
    main()
