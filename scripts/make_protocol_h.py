#!/usr/bin/env python3
"""Campaign H (I-15): multi-mission sequences in a changing world -- no memory vs naive memory vs verified memory.

16 sequences x 3 missions.  The requested supply is the same within a sequence (repeated resupply of shelter B);
lighting and prop placement are re-drawn for every mission.  Four stories (4 sequences each) script how the world
changes between missions, so that every transition type occurs:
  S1 relocated       : nominal -> swapped (relocation_change) -> swapped (relocation_persist)
  S2 relocated_back  : swapped -> swapped (relocation_persist) -> nominal (relocation_change)
  S3 fire_persists   : no fire -> small fire behind the requested station (fire_appears) -> fire again (fire_persists)
  S4 fire_gone       : fire -> no fire (fire_gone) -> fire (fire_appears)
Fires are campaign F/G's small, partly hidden fires (fresh draw per mission).  Mission 1 runs once per sequence
without using memory (all arms would behave identically) and seeds every arm's memory; missions 2 and 3 run in
each arm, arm order rotating over sequences:
  M0 = v3.6 (memory written for the change report only, never read)
  M1 = naive memory (baseline: skip the check where memory saw the supply, refuse without visiting after a hazard)
  M2 = verified memory (I-15: memory proposes the first station and raises caution; every check still runs)
"""
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind.robust_scenes import random_lighting  # noqa: E402
from scripts.make_protocol_v34 import POOL  # noqa: E402

SEED = 'H-2026'
STORIES = {
    'S1': [('nominal', None), ('swapped', 'relocation_change'), ('swapped', 'relocation_persist')],
    'S2': [('swapped', None), ('swapped', 'relocation_persist'), ('nominal', 'relocation_change')],
    'S3': [('plain', None), ('fire', 'fire_appears'), ('fire', 'fire_persists')],
    'S4': [('fire', None), ('plain', 'fire_gone'), ('fire', 'fire_appears')],
}
ARMS = {'M0': 'off', 'M1': 'naive', 'M2': 'verified'}
MEM = 'experiments/results/memory_H'


def world_spec(rng, kind, item):
    spec = {'lighting_params': random_lighting(rng),
            'prop_offsets': {n: [round(rng.uniform(-.06, .06), 3), round(rng.uniform(-.06, .06), 3),
                                 round(rng.uniform(-math.pi, math.pi), 3)] for n in ('sealed_water_bottles', 'first_aid_case')}}
    if kind == 'fire':
        spec['hazard_at'] = item
        spec['hazard_geom'] = [round(rng.uniform(.55, .75), 3), round(rng.uniform(-.15, .15), 3), round(rng.uniform(.45, .62), 3)]
    return spec


def build():
    rng = random.Random(SEED)
    stories = [s for s in STORIES for _ in range(4)]
    items = ['water', 'medicine'] * 8
    rng.shuffle(stories); rng.shuffle(items)
    trials, order = [], 0

    def add(seq, k, story, kind, transition, item, spec, arm, mem):
        nonlocal order
        order += 1
        scene = kind if kind in ('nominal', 'swapped') else 'nominal'
        trials.append({'id': f'H{order:03d}', 'order': order, 'sequence': seq, 'story': story, 'mission_index': k,
                       'world': f'{seq}m{k}', 'config': arm, 'scene': scene, 'expected': item,
                       'condition': transition or 'first_mission', 'transition': transition,
                       'instruction': POOL[item][rng.randrange(len(POOL[item]))], 'world_spec': spec,
                       'expected_action': 'SEE_H_ANALYSIS', 'memory': mem})

    for n, (story, item) in enumerate(zip(stories, items)):
        seq = f'Q{n + 1:02d}'
        specs = [world_spec(rng, kind, item) for kind, _ in STORIES[story]]
        kind, _ = STORIES[story][0]
        add(seq, 1, story, kind, None, item, specs[0], 'seed', {'file': f'{MEM}/{seq}_seed.jsonl', 'mode': 'off'})
        arms = list(ARMS)[n % 3:] + list(ARMS)[:n % 3]
        for arm in arms:
            for k in (2, 3):
                kind, tr = STORIES[story][k - 1]
                add(seq, k, story, kind, tr, item, specs[k - 1], arm,
                    {'file': f'{MEM}/{seq}_{arm}.jsonl', 'mode': ARMS[arm], 'init_from': f'{MEM}/{seq}_seed.jsonl'})
    return {'schema': 'rescuemind_campaign_h_protocol', 'seed': SEED, 'planned_n': len(trials),
            'common_stack_args': [], 'arms': ARMS, 'stories': {k: [list(x) for x in v] for k, v in STORIES.items()},
            'note': 'common_stack_args empty = orchestrator defaults (v3.6)', 'trials': trials}


def build_pilot():
    """Mechanics pilot on separate worlds (seed H-pilot): relocation (route + naive skip) and remembered fire
    (naive refusal without visiting, verified caution).  Development data; never part of H."""
    rng = random.Random('H-pilot')
    trials, order = [], 0
    mem = 'experiments/results/memory_H_pilot'
    for seq, (k1, k2), item in (('P1', ('swapped', 'swapped'), 'water'), ('P2', ('fire', 'fire'), 'medicine')):
        for k, kind in ((1, k1), (2, k2)):
            spec = world_spec(rng, kind, item)
            if kind == 'fire' and k == 1:
                spec['hazard_geom'][2] = 0.9      # a clearly visible first fire, so that memory holds a hazard
            arms = ['seed'] if k == 1 else ['M1', 'M2']
            for arm in arms:
                order += 1
                m = ({'file': f'{mem}/{seq}_seed.jsonl', 'mode': 'off'} if arm == 'seed' else
                     {'file': f'{mem}/{seq}_{arm}.jsonl', 'mode': ARMS[arm], 'init_from': f'{mem}/{seq}_seed.jsonl'})
                trials.append({'id': f'HP{order:02d}', 'order': order, 'sequence': seq, 'story': 'pilot', 'mission_index': k,
                               'world': f'{seq}m{k}', 'config': arm, 'scene': 'swapped' if kind == 'swapped' else 'nominal',
                               'expected': item, 'condition': 'pilot', 'transition': None if k == 1 else 'pilot',
                               'instruction': POOL[item][rng.randrange(len(POOL[item]))], 'world_spec': spec,
                               'expected_action': 'SEE_H_ANALYSIS', 'memory': m})
    return {'schema': 'rescuemind_campaign_h_pilot', 'seed': 'H-pilot', 'planned_n': len(trials), 'common_stack_args': [],
            'trials': trials}


def main():
    if '--pilot' in sys.argv:
        out = ROOT / 'experiments/campaign_h_pilot_protocol.json'
        out.write_text(json.dumps(build_pilot(), ensure_ascii=False, indent=1) + '\n')
        print('pilot written'); return
    out = ROOT / 'experiments/campaign_h_protocol.json'
    proto = build()
    if out.is_file() and json.loads(out.read_text()) != json.loads(json.dumps(proto, ensure_ascii=False)):
        sys.exit('registered protocol differs; refusing to overwrite')
    out.write_text(json.dumps(proto, ensure_ascii=False, indent=1) + '\n')
    print(proto['planned_n'], 'trials')


if __name__ == '__main__':
    main()
