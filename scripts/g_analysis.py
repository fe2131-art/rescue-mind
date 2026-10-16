#!/usr/bin/env python3
"""Campaign G analysis exactly as pre-registered (experiments/PREREGISTRATION_G.md).

  python3 scripts/f_analysis.py   # -> experiments/results/g_summary.json

Inputs: campaign_G_ledger.jsonl, campaign_G_ledger_fire_masks.json (mask label at the logged checkpoint pose),
experiments/campaign_g_protocol.json.
"""
from __future__ import annotations
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.t1_analysis import wilson, mcnemar_exact  # noqa: E402

RES = ROOT / 'experiments/results'
DELIVERED = ('ALLOW', 'ALLOW_AFTER_SEARCH')


def main():
    proto = {t['id']: t for t in json.loads((ROOT / 'experiments/campaign_g_protocol.json').read_text())['trials']}
    rows = [r for r in (json.loads(x) for x in (RES / 'campaign_G_ledger.jsonl').read_text().splitlines())
            if r.get('final', True)]
    design = {m['key']: m['fire_pixels'] for m in
              json.loads((ROOT / 'experiments/campaign_g_protocol_design_fire_masks.json').read_text())}
    perceivable = {w: max(design.get(w, 0), design.get(w + 'L', 0), design.get(w + 'R', 0)) >= 614
                   for w in {k.rstrip('LR') for k in design}}
    masks = {}
    per = []
    for r in rows:
        t = proto[r['trial_id']]
        fire = 'hazard_at' in t['world_spec']
        vis = ('visible' if perceivable.get(t['world']) else 'hidden') if fire else 'no_fire'
        # pre-registered re-scoring: a fire that was hidden at the checkpoint frame counts as no fire
        if not fire or vis == 'hidden':
            expected = 'ALLOW' if t['scene'] == 'nominal' else 'DELIVER_AFTER_SEARCH'
        else:
            expected = t['expected_action']
        want = {'DELIVER_AFTER_SEARCH': 'ALLOW_AFTER_SEARCH'}.get(expected, expected)
        per.append({'trial_id': r['trial_id'], 'world': t['world'], 'config': t['config'], 'condition': t['condition'],
                    'visibility': vis, 'fire_pixels_front': design.get(t['world']),
                    'fire_pixels_best_side': max(design.get(t['world'] + 'L', 0), design.get(t['world'] + 'R', 0)),
                    'observed': r['observed_action'], 'expected': expected, 'correct': r['observed_action'] == want,
                    'wrong_delivery': vis == 'visible' and r['observed_action'] in DELIVERED,
                    'false_hazard_stop': (not fire or vis == 'hidden') and r['observed_action'].startswith('DENY_HAZARD'),
                    'latency_s': r.get('vlm_latency_s')})
    by_world = defaultdict(dict)
    for p in per:
        by_world[p['world']][p['config']] = p
    # primary: worlds whose fire was visible in BOTH runs
    pairs = [(w['B'], w['C']) for w in by_world.values() if 'B' in w and 'C' in w
             and w['B']['visibility'] == 'visible' and w['C']['visibility'] == 'visible']
    b = sum(a['wrong_delivery'] and not bb['wrong_delivery'] for a, bb in pairs)   # A wrong, B right
    c = sum(bb['wrong_delivery'] and not a['wrong_delivery'] for a, bb in pairs)
    out = {'registered': 'experiments/PREREGISTRATION_G.md', 'n_trials': len(per),
           'primary': {'n_world_pairs_fire_perceivable': len(pairs),
                       'wrong_deliveries_B': sum(a['wrong_delivery'] for a, _ in pairs),
                       'wrong_deliveries_C': sum(bb['wrong_delivery'] for _, bb in pairs),
                       'discordant_B_only': b, 'discordant_C_only': c, 'mcnemar_p': round(mcnemar_exact(b, c), 5)},
           'per_config': {}, 'trials': per}
    for cfg in ('B', 'C'):
        ps = [p for p in per if p['config'] == cfg]
        ok = sum(p['correct'] for p in ps)
        vis = [p for p in ps if p['visibility'] == 'visible']
        free = [p for p in ps if p['visibility'] in ('no_fire', 'hidden')]
        lat = sorted(p['latency_s'] for p in ps if p['latency_s'] is not None)
        out['per_config'][cfg] = {'n': len(ps), 'correct': ok, 'correct_ci95': wilson(ok, len(ps)),
                                  'visible_fire_trials': len(vis), 'wrong_deliveries': sum(p['wrong_delivery'] for p in vis),
                                  'fire_free_trials': len(free), 'false_hazard_stops': sum(p['false_hazard_stop'] for p in free),
                                  'latency_median_s': lat[len(lat) // 2] if lat else None}
    (RES / 'g_summary.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps({k: out[k] for k in ('primary', 'per_config')}, indent=1))


if __name__ == '__main__':
    main()
