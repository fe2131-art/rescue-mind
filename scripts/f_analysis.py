#!/usr/bin/env python3
"""Campaign F analysis exactly as pre-registered (experiments/PREREGISTRATION_F.md).

  python3 scripts/f_analysis.py   # -> experiments/results/f_summary.json

Inputs: campaign_F_ledger.jsonl, campaign_F_ledger_fire_masks.json (mask label at the logged checkpoint pose),
experiments/campaign_f_protocol.json.
"""
from __future__ import annotations
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.t1_analysis import wilson, mcnemar_exact  # noqa: E402

RES = ROOT / 'experiments/results'
DELIVERED = ('ALLOW', 'ALLOW_AFTER_SEARCH')


def main():
    proto = {t['id']: t for t in json.loads((ROOT / 'experiments/campaign_f_protocol.json').read_text())['trials']}
    rows = [r for r in (json.loads(x) for x in (RES / 'campaign_F_ledger.jsonl').read_text().splitlines())
            if r.get('final', True)]
    masks = {m['key']: m for m in json.loads((RES / 'campaign_F_ledger_fire_masks.json').read_text())}
    per = []
    for r in rows:
        t = proto[r['trial_id']]
        fire = 'hazard_at' in t['world_spec']
        vis = masks.get(r['trial_id'], {}).get('visibility', 'not_checked') if fire else 'no_fire'
        # pre-registered re-scoring: a fire that was hidden at the checkpoint frame counts as no fire
        if not fire or vis == 'hidden':
            expected = 'ALLOW' if t['scene'] == 'nominal' else 'DELIVER_AFTER_SEARCH'
        else:
            expected = t['expected_action']
        want = {'DELIVER_AFTER_SEARCH': 'ALLOW_AFTER_SEARCH'}.get(expected, expected)
        per.append({'trial_id': r['trial_id'], 'world': t['world'], 'config': t['config'], 'condition': t['condition'],
                    'visibility': vis, 'fire_pixels': masks.get(r['trial_id'], {}).get('fire_pixels'),
                    'observed': r['observed_action'], 'expected': expected, 'correct': r['observed_action'] == want,
                    'wrong_delivery': vis == 'visible' and r['observed_action'] in DELIVERED,
                    'false_hazard_stop': (not fire or vis == 'hidden') and r['observed_action'].startswith('DENY_HAZARD'),
                    'latency_s': r.get('vlm_latency_s')})
    by_world = defaultdict(dict)
    for p in per:
        by_world[p['world']][p['config']] = p
    # primary: worlds whose fire was visible in BOTH runs
    pairs = [(w['A'], w['B']) for w in by_world.values() if 'A' in w and 'B' in w
             and w['A']['visibility'] == 'visible' and w['B']['visibility'] == 'visible']
    b = sum(a['wrong_delivery'] and not bb['wrong_delivery'] for a, bb in pairs)   # A wrong, B right
    c = sum(bb['wrong_delivery'] and not a['wrong_delivery'] for a, bb in pairs)
    out = {'registered': 'experiments/PREREGISTRATION_F.md', 'n_trials': len(per),
           'primary': {'n_world_pairs_fire_visible_both': len(pairs),
                       'wrong_deliveries_A': sum(a['wrong_delivery'] for a, _ in pairs),
                       'wrong_deliveries_B': sum(bb['wrong_delivery'] for _, bb in pairs),
                       'discordant_A_only': b, 'discordant_B_only': c, 'mcnemar_p': round(mcnemar_exact(b, c), 5)},
           'per_config': {}, 'trials': per}
    for cfg in ('A', 'B'):
        ps = [p for p in per if p['config'] == cfg]
        ok = sum(p['correct'] for p in ps)
        vis = [p for p in ps if p['visibility'] == 'visible']
        free = [p for p in ps if p['visibility'] in ('no_fire', 'hidden')]
        lat = sorted(p['latency_s'] for p in ps if p['latency_s'] is not None)
        out['per_config'][cfg] = {'n': len(ps), 'correct': ok, 'correct_ci95': wilson(ok, len(ps)),
                                  'visible_fire_trials': len(vis), 'wrong_deliveries': sum(p['wrong_delivery'] for p in vis),
                                  'fire_free_trials': len(free), 'false_hazard_stops': sum(p['false_hazard_stop'] for p in free),
                                  'latency_median_s': statistics.median(lat) if lat else None}
    (RES / 'f_summary.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps({k: out[k] for k in ('primary', 'per_config')}, indent=1))


if __name__ == '__main__':
    main()
