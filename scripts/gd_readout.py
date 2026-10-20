#!/usr/bin/env python3
"""Study GD readout of the saved model outputs (post hoc, descriptive; I-53).  NOT a registered analysis.

The same readout as GC (`scripts/gc_readout.py`) at the depot: for every non-failed GD run the hazard probability of the front check and of the look-around views next to the threshold the run used,
the design-mask pixels, and whether a `cal` refusal was decided by the lowered threshold alone.  On the fire-free worlds it adds the margin of the calibration: the largest score of any `cal` run
against tau_cal (`experiments/results/gd_calibration.json`) and against the calibration worlds' own largest score, i.e. whether the 24 fresh clean worlds stayed inside the calibration tail.

  python3 scripts/gd_readout.py [--runs outputs/runs]      # -> experiments/results/gd_readout.json
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import gc_readout as gcr  # noqa: E402

RES = ROOT / 'experiments/results'


def margin(rows: list, calib: dict) -> dict:
    """Fire-free `cal` and `v36` runs against the calibration: counts above tau_cal and above the calibration maximum (a run above tau_cal is a false stop for `cal`)."""
    tau = calib.get('tau_cal')
    cal_max = max((w['score'] for w in (calib.get('worlds') or {}).values()), default=None)
    ff = [r for r in rows if not r['fire'] and (r.get('check') or {}).get('max_p') is not None]
    out = {'tau_cal': tau, 'calibration_max_score': cal_max, 'm_calibration': calib.get('m')}
    for arm in ('cal', 'v36'):
        s = [r['check']['max_p'] for r in ff if r['arm'] == arm]
        out[arm] = {'n': len(s), 'max_score': max(s, default=None),
                    'above_tau_cal': sum(x >= tau for x in s) if tau is not None else None,
                    'above_calibration_max': sum(x > cal_max for x in s) if cal_max is not None else None}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', default=str(ROOT / 'outputs/runs'))
    a = ap.parse_args()
    summary = json.loads((RES / 'gd_summary.json').read_text(encoding='utf8'))
    masks = json.loads((ROOT / 'experiments/campaign_gd_candidates_design_fire_masks.json').read_text(encoding='utf8'))
    calib = json.loads((RES / 'gd_calibration.json').read_text(encoding='utf8'))
    rows = gcr.readout(RES / 'campaign_GD_ledger.jsonl', Path(a.runs), summary, masks)
    dg = gcr.digest(rows)
    mg = margin(rows, calib)
    (RES / 'gd_readout.json').write_text(json.dumps({'note': 'post hoc, descriptive (I-53); not a registered analysis', 'digest': dg, 'margin': mg, 'rows': rows}, ensure_ascii=False, indent=1) + '\n', encoding='utf8')
    print(f"{len(rows)} runs read; cal refusals decided by the lowered threshold: {len(dg['cal_refusals_decided_by_the_threshold'])}; false stops {dg['cal_false_stops']}; unsafe deliveries {len(dg['unsafe_deliveries'])}")
    print('margin', json.dumps(mg))
    for u in dg['unsafe_deliveries']:
        print(u['trial_id'], u['arm'], u['world'], u['stratum'], 'mask', u['mask_px'], u['check'])


if __name__ == '__main__':
    main()
