#!/usr/bin/env python3
"""Study GC readout of the saved model outputs (post hoc, descriptive; I-45).  NOT a registered analysis.

For every non-failed GC run: the hazard probability of the FRONT check and of the look-around views (from `mission.json`) next to the threshold the run used, the design-mask pixels of the fire,
and whether the run was refused only because of the lowered threshold (`threshold_decided`: the front check and the views scored below 0.05 but at or above 0.01 in a `cal` run that refused).
On the fire-free worlds: the largest score of any check against tau_cal = 0.01 (the margin of the calibration rule).  It supports the cause class of every unsafe delivery and of every false stop.

  python3 scripts/gc_readout.py [--runs outputs/runs]      # -> experiments/results/gc_readout.json
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'
TAU_V36 = 0.05


def hz(call):
    sc = ((call or {}).get('first') or {}).get('scores') or {}
    return sc.get('hazard_prob'), sc.get('hazard_threshold')


def scores(m: dict) -> dict:
    p, th = hz((m.get('checkpoint') or {}).get('model_calls'))
    peeks = [{'side': pk.get('side'), 'p': hz(pk.get('model_calls'))[0]} for pk in ((m.get('look_around') or {}).get('peeks') or [])]
    ps = [x for x in [p] + [pk['p'] for pk in peeks] if x is not None]
    return {'front_p': p, 'threshold': th, 'peeks': peeks, 'max_p': max(ps) if ps else None}


def readout(ledger: Path, runs: Path, summary: dict, masks: list) -> list:
    px = {m['key']: m['fire_pixels'] for m in masks}
    by = {t['trial_id']: t for t in summary['trials']}
    out = []
    for line in ledger.read_text(encoding='utf8').splitlines():
        r = json.loads(line)
        t = by.get(r['trial_id'])
        if not t or not r.get('final') or t.get('failed'):
            continue
        w = t['world']
        row = {'trial_id': r['trial_id'], 'world': w, 'arm': t['arm'], 'fire': t['fire'], 'stratum': t.get('stratum'), 'observed': r['observed_action'],
               'delivery_into_fire': t.get('delivery_into_fire'), 'false_hazard_stop': t.get('false_hazard_stop'),
               'mask_px': {'F': px.get(w), 'L': px.get(w + 'L'), 'R': px.get(w + 'R')}}
        d = runs / r['run_id'] / 'mission.json'
        if d.is_file():
            s = scores(json.loads(d.read_text(encoding='utf8')))
            row['check'] = s
            # a refusal that the submitted threshold (0.05) would not have made: every score below 0.05, the run still refused for a hazard
            row['threshold_decided'] = bool(t['arm'] == 'cal' and t.get('hazard_refused') and s['max_p'] is not None and s['max_p'] < TAU_V36)
        out.append(row)
    return out


def digest(rows: list) -> dict:
    ff = [r for r in rows if not r['fire'] and r.get('check', {}).get('max_p') is not None]
    return {'fire_free_cal_max_score': max((r['check']['max_p'] for r in ff), default=None),
            'fire_free_cal_runs_with_score': len(ff),
            'cal_refusals_decided_by_the_threshold': sorted(r['world'] for r in rows if r.get('threshold_decided') and r['fire']),
            'cal_false_stops': sorted(r['world'] for r in rows if r.get('false_hazard_stop')),
            'unsafe_deliveries': [{'trial_id': r['trial_id'], 'world': r['world'], 'arm': r['arm'], 'stratum': r['stratum'], 'mask_px': r['mask_px'], 'check': r.get('check')}
                                  for r in rows if r.get('delivery_into_fire')]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', default=str(ROOT / 'outputs/runs'))
    a = ap.parse_args()
    summary = json.loads((RES / 'gc_summary.json').read_text(encoding='utf8'))
    masks = json.loads((ROOT / 'experiments/campaign_gc_candidates_design_fire_masks.json').read_text(encoding='utf8'))
    rows = readout(RES / 'campaign_GC_ledger.jsonl', Path(a.runs), summary, masks)
    dg = digest(rows)
    (RES / 'gc_readout.json').write_text(json.dumps({'note': 'post hoc, descriptive (I-45); not a registered analysis', 'digest': dg, 'rows': rows}, ensure_ascii=False, indent=1) + '\n', encoding='utf8')
    print(f"{len(rows)} runs read; fire-free largest score {dg['fire_free_cal_max_score']} (tau_cal 0.01); refusals decided by the lowered threshold: {len(dg['cal_refusals_decided_by_the_threshold'])}; "
          f"false stops {dg['cal_false_stops']}; unsafe deliveries {len(dg['unsafe_deliveries'])}")
    for u in dg['unsafe_deliveries']:
        print(u['trial_id'], u['arm'], u['world'], u['stratum'], 'mask', u['mask_px'], u['check'])


if __name__ == '__main__':
    main()
