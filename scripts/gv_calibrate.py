#!/usr/bin/env python3
"""Study GV: calibrate the hazard threshold for the 0.8 m look-around by running the real mission with those views on 100 fire-free depot worlds with the threshold off (I-58).

  python3 scripts/gv_calibrate.py [--runs outputs/runs]    # reads campaign_GVK_ledger.jsonl -> experiments/results/gv_calibration.json (+ experiments/gv_site_cal.json unless the stop rule applies)

Per fire-free calibration world the score is the largest hazard probability over the views the mission checked (front and both side poses; with tau_h = 1.0 the look-around always runs).
tau_cal = the split-conformal rank rule at alpha = 2% (scripts/calibration_sites.py: the ceil(0.98 (m + 1))-th smallest score; the maximum when that rank exceeds m), rounded up to the next thousandth.
Stop rule (registered): if tau_cal >= 0.05 the calibration says "loosen" and the cal arm would be no more sensitive than the default; GV is then NOT run and "at alpha = 2% the depot cannot be calibrated below the default" is the result.
Calibration runs that failed for infrastructure reasons are excluded and listed; fewer than 90 usable worlds stops the calibration (the rank rule would not give alpha = 2%).
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

RES = ROOT / 'experiments/results'
ALPHA = 0.02
DEFAULT_TAU = 0.05
MIN_WORLDS = 90


def view_scores(mission: dict) -> dict:
    sc = (((mission.get('checkpoint') or {}).get('model_calls') or {}).get('first') or {}).get('scores') or {}
    out = {'F': sc.get('hazard_prob')}
    for pk in ((mission.get('look_around') or {}).get('peeks') or []):
        out[pk.get('side')] = (((pk.get('model_calls') or {}).get('first') or {}).get('scores') or {}).get('hazard_prob')
    return out


def calibrate(ledger_rows: list, runs: Path) -> dict:
    last = {}
    for r in ledger_rows:
        if r.get('final', True):
            last[r['trial_id']] = r
    worlds, failed = {}, []
    for tid, r in sorted(last.items()):
        if r.get('observed_action') == 'FAILED' or not r.get('run_id'):
            failed.append(tid)
            continue
        f = runs / r['run_id'] / 'mission.json'
        if not f.is_file():
            failed.append(tid)
            continue
        v = view_scores(json.loads(f.read_text(encoding='utf8')))
        ps = [x for x in v.values() if x is not None]
        if v.get('F') is None or len(ps) < 3:           # the front score and both side views must exist (the look-around ran)
            failed.append(tid)
            continue
        worlds[tid] = {'views': v, 'score': max(ps), 'item': r.get('expected_supply'), 'observed': r.get('observed_action')}
    scores = [w['score'] for w in worlds.values()]
    out = {'registered': 'experiments/PREREGISTRATION_GV.md (Section 1)', 'alpha': ALPHA, 'm': len(scores), 'failed_or_incomplete': failed, 'worlds': worlds}
    if len(scores) < MIN_WORLDS:
        return {**out, 'tau_raw': None, 'tau_cal': None, 'stop': True, 'stop_reason': f'fewer than {MIN_WORLDS} usable calibration worlds'}
    tau, bound = threshold(scores, ALPHA)
    cfg = math.ceil(tau * 1000 - 1e-9) / 1000
    srt = sorted(scores)
    out.update({'tau_raw': tau, 'tau_cal': cfg, 'guaranteed_false_stop_bound': round(bound, 4), 'largest_scores': srt[-5:], 'median_score': srt[len(srt) // 2],
                'by_item_max': {it: max((w['score'] for w in worlds.values() if w['item'] == it), default=None) for it in ('water', 'medicine')},
                'stop': cfg >= DEFAULT_TAU, 'stop_reason': 'tau_cal >= 0.05: the depot cannot be calibrated below the default at alpha = 2%' if cfg >= DEFAULT_TAU else None})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--runs', default=str(ROOT / 'outputs/runs'))
    a = ap.parse_args(argv)
    rows = [json.loads(x) for x in (RES / 'campaign_GVK_ledger.jsonl').read_text(encoding='utf8').splitlines() if x.strip()]
    out = calibrate(rows, Path(a.runs))
    (RES / 'gv_calibration.json').write_text(json.dumps(out, indent=1) + '\n', encoding='utf8')
    if not out['stop']:
        (ROOT / 'experiments/gv_site_cal.json').write_text(json.dumps({'schema': 'rescuemind-site-1', 'hazard_threshold': out['tau_cal'], 'hazard_prompt': 'h36', 'hazard_views': 'tiles'}) + '\n', encoding='utf8')
    print(json.dumps({k: v for k, v in out.items() if k != 'worlds'}, indent=1))
    raise SystemExit(2 if out['stop'] else 0)


if __name__ == '__main__':
    main()
