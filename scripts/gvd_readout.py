#!/usr/bin/env python3
"""Development pass GVD (I-70): do the 0.8 m views score GD's fire worlds above a front + left threshold?  Development data, not a claim.

  python3 scripts/gvd_readout.py [--runs outputs/runs]   # campaign_GVD_ledger.jsonl + gv_calibration.json + campaign_GD_ledger.jsonl -> experiments/results/gvd_readout.json

Threshold tau_FL: the rank rule at alpha = 2% (scripts/calibration_sites.py) over the per-world maximum of the FRONT and LEFT 0.8 m scores of the 100 fire-free GVK worlds (already seen when this was written,
disclosed), rounded up to the next thousandth.  Per GD fire world the GVD score is max(front, left 0.8 m).  Decision rule written before the results (IMPROVEMENT_LOG I-70): a registered left-only study
is worth running only if at most 3 of the GD fire worlds (7.5%) score below tau_FL; the score for the 10 worlds where GD delivered into the fire is reported separately.
"""
from __future__ import annotations
import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.calibration_sites import threshold  # noqa: E402
from scripts.gv_calibrate import view_scores  # noqa: E402

RES = ROOT / 'experiments/results'
GO_MAX_MISSES = 3


def last_rows(path: Path) -> dict:
    out = {}
    for x in path.read_text(encoding='utf8').splitlines():
        if x.strip():
            r = json.loads(x)
            if r.get('final', True):
                out[r['trial_id']] = r
    return out


def readout(runs: Path) -> dict:
    cal = json.loads((RES / 'gv_calibration.json').read_text())
    fl = [max(w['views']['F'], w['views']['L']) for w in cal['worlds'].values() if w['views'].get('F') is not None and w['views'].get('L') is not None]
    tau_raw, bound = threshold(fl, 0.02)
    tau = math.ceil(tau_raw * 1000 - 1e-9) / 1000
    gd = last_rows(RES / 'campaign_GD_ledger.jsonl')
    unsafe = {}                                    # GD world -> arms that delivered into the fire
    for r in gd.values():
        if r.get('condition') == 'fire_hidden' and r.get('delivered'):
            unsafe.setdefault(r['world'], []).append(r['config'])
    worlds, failed = {}, []
    for tid, r in sorted(last_rows(RES / 'campaign_GVD_ledger.jsonl').items()):
        f = runs / str(r.get('run_id')) / 'mission.json'
        if r.get('observed_action') == 'FAILED' or not f.is_file():
            failed.append(tid)
            continue
        v = view_scores(json.loads(f.read_text(encoding='utf8')))
        if v.get('F') is None or v.get('L') is None:
            failed.append(tid)
            continue
        worlds[r['world']] = {'views': v, 'score_FL': max(v['F'], v['L']), 'item': r.get('expected_supply'), 'gd_unsafe_arms': unsafe.get(r['world'], [])}
    below = sorted(w for w, d in worlds.items() if d['score_FL'] < tau)
    u_below = sorted(w for w in below if worlds[w]['gd_unsafe_arms'])
    return {'tau_FL': tau, 'tau_FL_raw': tau_raw, 'cal_m': len(fl), 'cal_FL_largest': sorted(fl)[-5:], 'n_worlds': len(worlds), 'failed': failed,
            'below_tau': below, 'n_below': len(below), 'go_rule_max_below': GO_MAX_MISSES, 'go': len(below) <= GO_MAX_MISSES and not failed,
            'gd_unsafe_worlds': sorted(unsafe), 'gd_unsafe_below_tau': u_below, 'worlds': worlds}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--runs', default=str(ROOT / 'outputs/runs'))
    a = ap.parse_args(argv)
    out = readout(Path(a.runs))
    (RES / 'gvd_readout.json').write_text(json.dumps(out, indent=1) + '\n', encoding='utf8')
    print(json.dumps({k: v for k, v in out.items() if k != 'worlds'}, indent=1))


if __name__ == '__main__':
    main()
