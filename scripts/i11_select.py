#!/usr/bin/env python3
"""I-11: choose the hazard-question variant on DEVELOPMENT data only (rule fixed before any result).

  python3 scripts/i11_select.py      # reads experiments/results/devset_{dh,v1,v2}_i11_<variant>.json

Variants: hazard prompt {h35, h36} x views {full, tiles}; thresholds tau_h in {0.05, 0.10, 0.20}.
Selection rule (written before the runs, docs/IMPROVEMENT_LOG.md I-11):
  1. zero hazard alarms on every fire-free development image (dev v1 + v2 + DH),
  2. then the highest hazard recall on DH images with a visible fire,
  3. then fewer model calls (full < tiles), then the higher threshold.
The baseline h35/full/0.05 is v3.5.  T2 (held-out) is registered with the winner before it is rendered.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'
VARIANTS = [(p, v) for p in ('h35', 'h36') for v in ('full', 'tiles')]
TAUS = (0.05, 0.10, 0.20)


def hz(r):
    return max(r['passes'][k]['scores']['hazard_prob'] for k in '12' if 'scores' in r['passes'][k])


def load(prefix, p, v):
    f = RES / f'devset_{prefix}_i11_{p}_{v}.json'
    return json.loads(f.read_text())['records'] if f.is_file() else None


def main():
    table = []
    for p, v in VARIANTS:
        dh, d1, d2 = load('dh', p, v), load('v1', p, v), load('v2', p, v)
        if dh is None or d1 is None or d2 is None:
            continue
        free = [r for r in dh if r['hazard_visibility'] == 'hidden'] + \
               [r for r in d1 + d2 if not r.get('truth_hazard_visible')]
        fire = [r for r in dh if r['hazard_visibility'] == 'visible']
        lat = [r['passes'][k]['latency_s'] for r in dh for k in '12']
        for t in TAUS:
            table.append({'prompt': p, 'views': v, 'tau_h': t,
                          'false_alarms': sum(hz(r) >= t for r in free), 'n_fire_free': len(free),
                          'recall': sum(hz(r) >= t for r in fire), 'n_fire': len(fire),
                          'max_fire_free_p': round(max(hz(r) for r in free), 4),
                          'mean_latency_per_pass_s': round(sum(lat) / len(lat), 3)})
    ok = [r for r in table if r['false_alarms'] == 0]
    ok.sort(key=lambda r: (-r['recall'], r['views'] == 'tiles', -r['tau_h']))
    out = {'rule': __doc__, 'table': table, 'selected': ok[0] if ok else None}
    (RES / 'i11_selection.json').write_text(json.dumps(out, indent=1) + '\n')
    for r in table:
        print(f"{r['prompt']} {r['views']:5s} tau_h={r['tau_h']:.2f}  alarms {r['false_alarms']}/{r['n_fire_free']}  "
              f"recall {r['recall']}/{r['n_fire']}  max free p {r['max_fire_free_p']}  {r['mean_latency_per_pass_s']} s/pass")
    print('SELECTED', out['selected'])


if __name__ == '__main__':
    main()
