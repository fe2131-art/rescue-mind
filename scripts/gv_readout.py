#!/usr/bin/env python3
"""Study GV readout of the saved model outputs (post hoc, descriptive; I-59).  NOT a registered analysis.

The readout of GC/GD (`scripts/gc_readout.py`) for the three GV arms: for every non-failed run the hazard probability of the front check and of the look-around views next to the threshold the run used,
whether a `wcal` refusal was decided by the lowered threshold alone (every score below 0.05), the margin of the calibration on the fire-free worlds (largest `wcal` / `wide` score against tau_cal and
against the calibration worlds' own largest score), and per fire world the largest view score of each arm (does the 0.8 m geometry raise the score of the fire, and by how much, against the 0.4 m views of `v36`).

  python3 scripts/gv_readout.py [--runs outputs/runs]      # -> experiments/results/gv_readout.json
"""
from __future__ import annotations
import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import gc_readout as gcr  # noqa: E402

RES = ROOT / 'experiments/results'


def decided(rows: list) -> list:
    """`wcal` fire-world refusals that the submitted threshold would not have made (every score below 0.05)."""
    for r in rows:
        s = (r.get('check') or {}).get('max_p')
        r['threshold_decided'] = bool(r['arm'] == 'wcal' and r['fire'] and r['observed'] and r['observed'].startswith('DENY_HAZARD') and s is not None and s < gcr.TAU_V36)
    return sorted(r['world'] for r in rows if r['threshold_decided'])


def margin(rows: list, calib: dict) -> dict:
    """Fire-free runs against the calibration: counts at or above tau_cal (a `wcal` run there is a false stop) and above the calibration maximum."""
    tau = calib.get('tau_cal')
    cal_max = max((w['score'] for w in (calib.get('worlds') or {}).values()), default=None)
    out = {'tau_cal': tau, 'calibration_max_score': cal_max, 'm_calibration': calib.get('m')}
    for arm in ('wcal', 'wide'):
        s = [r['check']['max_p'] for r in rows if not r['fire'] and r['arm'] == arm and (r.get('check') or {}).get('max_p') is not None]
        out[arm] = {'n': len(s), 'max_score': max(s, default=None), 'above_tau_cal': sum(x >= tau for x in s) if tau is not None else None,
                    'above_calibration_max': sum(x > cal_max for x in s) if cal_max is not None else None}
    return out


def by_world(rows: list) -> dict:
    """Per fire world the largest view score of each arm and whether that arm delivered into the fire."""
    out = {}
    for r in rows:
        if r['fire'] and (r.get('check') or {}).get('max_p') is not None:
            out.setdefault(r['world'], {})[r['arm']] = {'max_p': r['check']['max_p'], 'front_p': r['check']['front_p'], 'unsafe': bool(r['delivery_into_fire'])}
    return out


def geometry(per_world: dict) -> dict:
    """Did the 0.8 m views score the fire higher than the 0.4 m views (`wide` against `v36`, same threshold)?  Counts and the median ratio of the two largest view scores."""
    pairs = [(a['v36']['max_p'], a['wide']['max_p']) for a in per_world.values() if 'v36' in a and 'wide' in a]
    ratio = [w / v for v, w in pairs if v > 0]
    return {'n_pairs': len(pairs), 'wide_higher': sum(w > v for v, w in pairs), 'wide_lower': sum(w < v for v, w in pairs),
            'median_ratio_wide_over_v36': round(statistics.median(ratio), 2) if ratio else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', default=str(ROOT / 'outputs/runs'))
    a = ap.parse_args()
    summary = json.loads((RES / 'gv_summary.json').read_text(encoding='utf8'))
    masks = json.loads((ROOT / 'experiments/campaign_gv_candidates_design_fire_masks.json').read_text(encoding='utf8'))
    calib = json.loads((RES / 'gv_calibration.json').read_text(encoding='utf8'))
    rows = gcr.readout(RES / 'campaign_GV_ledger.jsonl', Path(a.runs), summary, masks)
    td = decided(rows)
    dg = gcr.digest(rows)
    mg, pw = margin(rows, calib), by_world(rows)
    ge = geometry(pw)
    (RES / 'gv_readout.json').write_text(json.dumps({'note': 'post hoc, descriptive (I-59); not a registered analysis', 'digest': {**dg, 'wcal_refusals_decided_by_the_threshold': td},
                                                     'margin': mg, 'geometry': ge, 'per_world': pw, 'rows': rows}, ensure_ascii=False, indent=1) + '\n', encoding='utf8')
    print(f"{len(rows)} runs read; wcal refusals decided by the threshold alone: {len(td)}; unsafe deliveries {len(dg['unsafe_deliveries'])}")
    print('margin', json.dumps(mg))
    print('geometry', json.dumps(ge))
    for u in dg['unsafe_deliveries']:
        print(u['trial_id'], u['arm'], u['world'], u['stratum'], 'mask', u['mask_px'], u['check'])


if __name__ == '__main__':
    main()
