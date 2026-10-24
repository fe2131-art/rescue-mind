#!/usr/bin/env python3
"""Does the particle-smoke flag of the fire world change the closed-loop miss rate?  (I-119; POST HOC on the registered campaigns GM and JK; no new runs.)

  python3 scripts/smoke_strata.py     # -> experiments/results/smoke_strata.json
GM's worlds carry `depot.particle_smoke` (a smoke plume rises from the fire in about half of the fire worlds, drawn at random by the generator).  For the arms v36 and left (GM) and adapt (JK) on the same 100 fire worlds,
deliveries into fire are counted by smoke stratum.  The scouts' round 4 pointed at haze or smoke density as the environment factor not yet varied (SmokeBench: smoke volume matters more than contrast); this uses the one
smoke factor the worlds already vary.  Exact Fisher test (two-sided) smoke against no smoke, per arm; descriptive, no claim.
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.jk_analysis import last_rows  # noqa: E402

RES = ROOT / 'experiments/results'
DELIVERED = ('ALLOW', 'ALLOW_AFTER_SEARCH')


def fisher_two_sided(a, b, c, d):
    n1, n2, k = a + b, c + d, a + c
    tot = n1 + n2
    prob = lambda x: math.comb(n1, x) * math.comb(n2, k - x) / math.comb(tot, k)
    p0 = prob(a)
    return round(min(1.0, sum(prob(x) for x in range(max(0, k - n2), min(n1, k) + 1) if prob(x) <= p0 + 1e-12)), 4)


def main():
    gm = json.loads((ROOT / 'experiments/campaign_gm_protocol.json').read_text())
    jk = json.loads((ROOT / 'experiments/campaign_jk_protocol.json').read_text())
    gm_rows, jk_rows = last_rows(RES / 'campaign_GM_ledger.jsonl'), last_rows(RES / 'campaign_JK_ledger.jsonl')
    rec = {}
    for proto, rows in ((gm, gm_rows), (jk, jk_rows)):
        for t in proto['trials']:
            if t['condition'] != 'fire_hidden':
                continue
            r = rows.get(t['id'])
            if not r or r.get('observed_action') == 'FAILED':
                continue
            smoke = bool((t['world_spec'].get('depot') or {}).get('particle_smoke'))
            rec.setdefault(t['config'], {})[t['world']] = (smoke, r.get('observed_action') in DELIVERED)
    out = {'post_hoc': True, 'arms': {}}
    for arm, d in rec.items():
        s = [v[1] for v in d.values() if v[0]]
        n = [v[1] for v in d.values() if not v[0]]
        out['arms'][arm] = {'smoke': {'n': len(s), 'unsafe': sum(s)}, 'no_smoke': {'n': len(n), 'unsafe': sum(n)},
                            'fisher_two_sided_p': fisher_two_sided(sum(s), len(s) - sum(s), sum(n), len(n) - sum(n)) if s and n else None}
    (RES / 'smoke_strata.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out))


if __name__ == '__main__':
    main()
