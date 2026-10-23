#!/usr/bin/env python3
"""Study JC: freeze the sentinel thresholds from XD's clean CALIBRATION worlds (rank rule on the per-world maximum over F, L, R) before any JI image exists.

  python3 scripts/ji_cascade_thresholds.py     # -> experiments/ji_cascade_thresholds.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import cascade_dev as cd  # noqa: E402
from calibration_sites import threshold  # noqa: E402

ALPHAS = (0.05, 0.10, 0.20, 0.30, 0.50)


def main():
    rows, info = cd.load_xd()
    kind = lambda w: 'fire' if (info[w]['world_kind'] == 'hazard' and info[w].get('world_perceivable_any_view')) else ('clean' if info[w]['world_kind'] in ('twin', 'ok') else 'other')
    cal = [w for w in info if info[w]['split'] == 'cal' and kind(w) == 'clean']
    out = {'source': 'rank rule (scripts/calibration_sites.threshold) at alpha_s over the per-world maximum on F, L, R of the clean CALIBRATION worlds of XD; frozen before any JI image exists',
           'n_cal_clean': len(cal), 'primary_alpha': 0.2, 'sentinel_alpha': {}, 'gate_own_trigger': 0.01}
    for j in ('internvl3', 'idefics3', 'smolvlm2'):
        pm = cd.pmax(rows[j], cd.STD)
        out['sentinel_alpha'][j] = {str(a): threshold([pm.get(w, 0.0) for w in cal], a)[0] for a in ALPHAS}
    p = ROOT / 'experiments/ji_cascade_thresholds.json'
    p.write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out))


if __name__ == '__main__':
    main()
