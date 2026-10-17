#!/usr/bin/env python3
"""Study L: closed-loop protocol with a freshly sampled ARENA LAYOUT per trial, built BEFORE running it.

24 trials (seed 'L-2026'), one rescuemind.layout.sample_layout layout each (stations + shelter moved):
  nominal (8) -> ALLOW                    swapped (6) -> DELIVER_AFTER_SEARCH
  empty (4)   -> DENY                     fire (6)    -> DENY_HAZARD (nominal scene, clearly visible fire behind the
                                           requested station, scale 0.75-1.0 as in campaign E)
Lighting and prop offsets are drawn as in campaign E (no prop offsets for an empty scene); a single configuration
(orchestrator defaults = v3.6).  The fire geometry is drawn before the layout and the layout is feasibility-checked with
that exact fire.  Each trial also carries 'world' (= its id) so scripts/fire_mask_at_pose.py --design keys the masks.

  python3 scripts/make_protocol_l.py            # experiments/campaign_l_protocol.json (refuses to overwrite a differing one)
  python3 scripts/make_protocol_l.py --smoke    # experiments/campaign_l_smoke_protocol.json (seed 'L-smoke', development)
"""
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind.layout import sample_layout  # noqa: E402
from rescuemind.robust_scenes import random_lighting  # noqa: E402
from scripts.make_protocol_v34 import POOL  # noqa: E402

SEED = 'L-2026'
SMOKE_SEED = 'L-smoke'
STRATA = ([('nominal', None, 'ALLOW')] * 8 + [('swapped', None, 'DELIVER_AFTER_SEARCH')] * 6 +
          [('empty', None, 'DENY')] * 4 + [('nominal', 'fire', 'DENY_HAZARD')] * 6)
SMOKE_STRATA = [('nominal', None, 'ALLOW'), ('swapped', None, 'DELIVER_AFTER_SEARCH'), ('empty', None, 'DENY')]
PROPS = ('sealed_water_bottles', 'first_aid_case')


def build(seed: str = SEED, strata=None, prefix: str = 'L'):
    strata = list(STRATA if strata is None else strata)
    rng = random.Random(seed)
    items = ['water', 'medicine'] * (len(strata) // 2 + 1)
    items = items[:len(strata)]
    rng.shuffle(items)
    rng.shuffle(strata)
    trials = []
    for k, ((scene, cond, action), item) in enumerate(zip(strata, items)):
        kw = {}
        spec = {}
        if cond == 'fire':
            geom = [round(rng.uniform(.75, 1.0), 3), round(rng.choice([-1, 1]) * rng.uniform(.25, .6), 3)]
            kw = {'hazard_at': item, 'hazard_geom': tuple(geom)}
        layout = sample_layout(rng, **kw)
        spec['layout'] = layout.to_dict()
        spec['lighting_params'] = random_lighting(rng)
        if scene != 'empty':      # as in campaign E: an empty scene has no props to move
            spec['prop_offsets'] = {n: [round(rng.uniform(-.12, .12), 3), round(rng.uniform(-.12, .12), 3),
                                        round(rng.uniform(-math.pi, math.pi), 3)] for n in PROPS}
        if cond == 'fire':
            spec['hazard_at'] = item
            spec['hazard_geom'] = geom
        tid = f'{prefix}{k + 1:03d}' if prefix == 'L' else f'{prefix}{k + 1:02d}'
        trials.append({'id': tid, 'order': k + 1, 'world': tid, 'scene': scene, 'expected': item,
                       'condition': cond or 'plain', 'instruction': POOL[item][rng.randrange(len(POOL[item]))],
                       'world_spec': spec, 'expected_action': action})
    return {'schema': 'rescuemind_campaign_l_protocol', 'seed': seed, 'planned_n': len(trials), 'common_stack_args': [],
            'trials': trials}


def build_smoke():
    """Development layouts (seed 'L-smoke'); asserted disjoint from the registered L layouts."""
    proto = build(SMOKE_SEED, SMOKE_STRATA, prefix='S')
    reg = {json.dumps(t['world_spec']['layout'], sort_keys=True) for t in build()['trials']}
    if any(json.dumps(t['world_spec']['layout'], sort_keys=True) in reg for t in proto['trials']):
        raise SystemExit('smoke layout coincides with a registered L layout')
    proto['schema'] = 'rescuemind_campaign_l_smoke_protocol'
    return proto


def write(out: Path, proto: dict, overwrite_registered: bool = False):
    if out.is_file() and json.loads(out.read_text()) != json.loads(json.dumps(proto, ensure_ascii=False)):
        sys.exit('registered protocol differs from the generator output; refusing to overwrite')
    out.write_text(json.dumps(proto, ensure_ascii=False, indent=1) + '\n')


def main():
    from collections import Counter
    smoke = '--smoke' in sys.argv
    proto = build_smoke() if smoke else build()
    write(ROOT / ('experiments/campaign_l_smoke_protocol.json' if smoke else 'experiments/campaign_l_protocol.json'), proto)
    print(proto['planned_n'], Counter(t['expected_action'] for t in proto['trials']),
          Counter(t['expected'] for t in proto['trials']))


if __name__ == '__main__':
    main()
