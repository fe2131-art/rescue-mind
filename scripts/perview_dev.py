#!/usr/bin/env python3
"""I-91 development check (no GPU, no claim): would a per-view union rule with a right-view threshold add fire catches to the GL arm (front + left at tau 0.028)?

  python3 scripts/perview_dev.py        # experiments/results/perview_dev.json
Data already on disk: the 100 fire-free GVK worlds (per-view 0.8 m scores, gv_calibration.json) and the 39 GD fire worlds seen from 0.8 m (GVD readout).  Rule examined: flag if F >= 0.05 or L >= 0.028 or R >= tR.
For each tR: clean worlds flagged (of 100, by the union) and fire worlds caught ONLY by R (F < 0.05, L < 0.028, R >= tR).
"""
import json
from pathlib import Path

RES = Path(__file__).resolve().parents[1] / 'experiments/results'


def main():
    c = json.loads((RES / 'gv_calibration.json').read_text())['worlds']
    g = json.loads((RES / 'gvd_readout.json').read_text())['worlds']
    out = {'clean_n': len(c), 'fire_n': len(g), 'rows': []}
    for tR in (0.05, 0.0706, 0.1, 0.2):
        flag = lambda v: v['F'] >= 0.05 or v['L'] >= 0.028 or v['R'] >= tR
        out['rows'].append({'tau_R': tR, 'clean_flagged': sum(flag(w['views']) for w in c.values()),
                            'clean_flagged_without_R': sum(w['views']['F'] >= 0.05 or w['views']['L'] >= 0.028 for w in c.values()),
                            'fire_only_R': sum(1 for w in g.values() if w['views']['F'] < 0.05 and w['views']['L'] < 0.028 and w['views']['R'] >= tR)})
    out['fire_below_FL_rule'] = sum(1 for w in g.values() if w['views']['F'] < 0.05 and w['views']['L'] < 0.028)
    out['clean_R_top5'] = sorted(w['views']['R'] for w in c.values())[-5:]
    (RES / 'perview_dev.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out))


if __name__ == '__main__':
    main()
