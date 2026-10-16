#!/usr/bin/env python3
"""Campaign E: build the closed-loop protocol with a freshly randomised world per trial, BEFORE running it.

60 trials (seed 'E-2026'). Each trial gets its own continuous lighting, moved/rotated supplies and,
depending on the stratum, a fire or a distractor (box seen in development; crate and cone are new):
  nominal (20)  -> ALLOW                     12 plain; 4 cone, 2 crate, 2 box next to the supply on the requested platform
  swapped (16)  -> DELIVER_AFTER_SEARCH      12 plain; 2 box, 2 crate next to the (wrong) supply on the requested platform
  empty (12)    -> DENY                      6 plain; 4 crate, 2 box alone on the requested platform
  fire (8)      -> DENY_HAZARD               nominal scene, fire behind the requested station
  fire-after-search (4) -> DENY_HAZARD_AFTER_SEARCH
                                             swapped scene, fire behind the OTHER station (recovery must still stop)
Instructions reuse campaign D's phrasing pool (disjoint from the I-04 held-out set).
"""
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind.robust_scenes import platform_side_offset, random_lighting  # noqa: E402
from scripts.make_protocol_v34 import POOL  # noqa: E402

SEED = 'E-2026'
OTHER = {'water': 'medicine', 'medicine': 'water'}
PROP = {'water': 'sealed_water_bottles', 'medicine': 'first_aid_case'}


def build(seed: str = SEED):
    rng = random.Random(seed)
    strata = ([('nominal', None, 'ALLOW')] * 12 + [('nominal', 'cone', 'ALLOW')] * 4 + [('nominal', 'crate', 'ALLOW')] * 2 +
              [('nominal', 'box', 'ALLOW')] * 2 +
              [('swapped', None, 'DELIVER_AFTER_SEARCH')] * 12 + [('swapped', 'box', 'DELIVER_AFTER_SEARCH')] * 2 +
              [('swapped', 'crate', 'DELIVER_AFTER_SEARCH')] * 2 +
              [('empty', None, 'DENY')] * 6 + [('empty', 'crate', 'DENY')] * 4 + [('empty', 'box', 'DENY')] * 2 +
              [('nominal', 'fire', 'DENY_HAZARD')] * 8 + [('swapped', 'fire_other', 'DENY_HAZARD_AFTER_SEARCH')] * 4)
    items = ['water', 'medicine'] * (len(strata) // 2)
    rng.shuffle(items)
    rng.shuffle(strata)
    trials = []
    for k, ((scene, cond, action), item) in enumerate(zip(strata, items)):
        spec = {'lighting_params': random_lighting(rng),
                'prop_offsets': {n: [round(rng.uniform(-.12, .12), 3), round(rng.uniform(-.12, .12), 3),
                                     round(rng.uniform(-math.pi, math.pi), 3)] for n in ('sealed_water_bottles', 'first_aid_case')}}
        side = rng.choice([-1.0, 1.0])
        if cond in ('fire', 'fire_other'):
            spec['hazard_at'] = item if cond == 'fire' else OTHER[item]
            spec['hazard_geom'] = [round(rng.uniform(.75, 1.0), 3), round(rng.choice([-1, 1]) * rng.uniform(.25, .6), 3)]
        elif cond:
            spec['distractor_at'] = item
            spec['distractor_kind'] = cond
            spec['distractor_side'] = side
            spec['distractor_layout'] = 'platform'
            if scene != 'empty':
                # keep the supply on the other half of the platform from the distractor
                prop = PROP[item] if scene == 'nominal' else PROP[OTHER[item]]
                ox, oy = platform_side_offset(item, -side, 0.10)
                spec['prop_offsets'][prop][:2] = [round(ox + rng.uniform(-.04, .04), 3), round(oy + rng.uniform(-.04, .04), 3)]
        trials.append({'id': f'E{k + 1:03d}', 'order': k + 1, 'scene': scene, 'expected': item, 'condition': cond or 'plain',
                       'instruction': POOL[item][rng.randrange(len(POOL[item]))], 'world_spec': spec,
                       'expected_action': action})
    return {'schema': 'rescuemind_campaign_e_protocol', 'seed': seed, 'planned_n': len(trials), 'trials': trials}


def pilot():
    """Mechanics pilot (seed 'E-pilot', never the registered worlds): one trial per condition type."""
    seen, trials = set(), []
    for t in build('E-pilot')['trials']:
        key = (t['scene'], t['condition'])
        if t['condition'] != 'plain' and key not in seen:
            seen.add(key)
            trials.append(dict(t, id=f'P{len(trials) + 1:02d}', order=len(trials) + 1))
    out = {'schema': 'rescuemind_campaign_e_protocol', 'seed': 'E-pilot', 'planned_n': len(trials), 'trials': trials}
    (ROOT / 'experiments/campaign_e_pilot_protocol.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    print('pilot', [(t['id'], t['scene'], t['condition']) for t in trials])


def main():
    if '--pilot' in sys.argv:
        return pilot()
    out = ROOT / 'experiments/campaign_e_protocol.json'
    proto = build()
    if out.is_file() and json.loads(out.read_text()) != json.loads(json.dumps(proto, ensure_ascii=False)):
        sys.exit('registered protocol differs from the generator output; refusing to overwrite')
    out.write_text(json.dumps(proto, ensure_ascii=False, indent=1) + '\n')
    from collections import Counter
    print(proto['planned_n'], Counter(t['expected_action'] for t in proto['trials']),
          Counter(t['expected'] for t in proto['trials']))


if __name__ == '__main__':
    main()
