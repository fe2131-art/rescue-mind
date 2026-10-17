#!/usr/bin/env python3
"""Study V (validation of the repeated-mission model in closed loop): world sequences drawn from the model's own change
process instead of scripted stories.

10 sequences x 6 missions, the requested supply fixed per sequence.  As in scripts/h_change_rate_model.py:
  * mission 1: relocated ~ Bernoulli(0.5) (the requested supply sits at the other station: scene 'swapped'),
               fire ~ Bernoulli(0.3) (a small, partly hidden fire behind the station that HOLDS the requested supply);
  * between missions each flag toggles independently with probability q = 0.2.
Lighting, prop placement and the fire geometry are re-drawn every mission (campaign H's distributions).
Mission 1 runs once per sequence without using memory and seeds every arm (as in H); missions 2-6 run in each arm
(M0 off, M1 naive, M2 verified), arm order rotating over sequences.  1 + 5 x 3 = 16 runs per sequence, 160 in total.
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.make_protocol_h import world_spec, ARMS  # noqa: E402
from scripts.make_protocol_v34 import POOL  # noqa: E402

SEED = 'V-2026'
N_SEQ, N_MISSIONS, Q, P_RELOC0, P_FIRE0 = 10, 6, 0.2, 0.5, 0.3
MEM = 'experiments/results/memory_V'
OTHER = {'water': 'medicine', 'medicine': 'water'}


def states(rng):
    rel, fire = rng.random() < P_RELOC0, rng.random() < P_FIRE0
    out = []
    for k in range(N_MISSIONS):
        if k:
            rel ^= rng.random() < Q
            fire ^= rng.random() < Q
        out.append({'relocated': rel, 'fire': fire})
    return out


def build():
    rng = random.Random(SEED)
    items = ['water', 'medicine'] * (N_SEQ // 2)
    rng.shuffle(items)
    trials, seq_states, order = [], {}, 0
    for n, item in enumerate(items):
        seq = f'V{n + 1:02d}'
        st = states(rng)
        seq_states[seq] = st
        specs = []
        for s in st:
            spec = world_spec(rng, 'fire' if s['fire'] else 'plain', item)
            if s['fire']:
                spec['hazard_at'] = OTHER[item] if s['relocated'] else item     # behind the station that holds the supply
            specs.append(spec)
        instr = [POOL[item][rng.randrange(len(POOL[item]))] for _ in st]

        def add(k, arm, mem):
            nonlocal order
            order += 1
            prev = st[k - 2] if k > 1 else None
            trials.append({'id': f'V{order:03d}', 'order': order, 'sequence': seq, 'mission_index': k,
                           'world': f'{seq}m{k}', 'config': arm, 'scene': 'swapped' if st[k - 1]['relocated'] else 'nominal',
                           'expected': item, 'state': st[k - 1],
                           'story': 'random',
                           'transition': None if prev is None else (
                               f"relocation_{'change' if prev['relocated'] != st[k - 1]['relocated'] else 'persist'}"
                               f"|fire_{'change' if prev['fire'] != st[k - 1]['fire'] else 'persist'}"),
                           'condition': 'first_mission' if k == 1 else 'random_change',
                           'instruction': instr[k - 1], 'world_spec': specs[k - 1],
                           'expected_action': 'SEE_V_ANALYSIS', 'memory': mem})
        add(1, 'seed', {'file': f'{MEM}/{seq}_seed.jsonl', 'mode': 'off'})
        arms = list(ARMS)[n % 3:] + list(ARMS)[:n % 3]
        for arm in arms:
            for k in range(2, N_MISSIONS + 1):
                add(k, arm, {'file': f'{MEM}/{seq}_{arm}.jsonl', 'mode': ARMS[arm], 'init_from': f'{MEM}/{seq}_seed.jsonl'})
    return {'schema': 'rescuemind_campaign_v_protocol', 'seed': SEED, 'planned_n': len(trials),
            'process': {'n_sequences': N_SEQ, 'n_missions': N_MISSIONS, 'q': Q, 'p_relocated_1': P_RELOC0, 'p_fire_1': P_FIRE0},
            'common_stack_args': [], 'arms': ARMS, 'sequence_states': seq_states,
            'note': 'common_stack_args empty = orchestrator defaults (v3.6); states are the drawn world flags before mask labelling',
            'trials': trials}


def build_pilot():
    """Mechanics pilot on separate worlds (seed V-pilot; development data, never part of V).  New in V and never run in
    H: a fire behind the OTHER station while the supply is relocated.  M0 must search and then stop at the fire
    (DENY_HAZARD_AFTER_SEARCH), M2 must go there first and stop, M1 must deliver blindly (mission 2 skip)."""
    rng = random.Random('V-pilot')
    item, trials, order = 'water', [], 0
    mem = 'experiments/results/memory_V_pilot'
    sts = [{'relocated': True, 'fire': False}, {'relocated': True, 'fire': True}]
    for k, s in enumerate(sts, 1):
        spec = world_spec(rng, 'fire' if s['fire'] else 'plain', item)
        if s['fire']:
            spec['hazard_at'] = OTHER[item]
            spec['hazard_geom'][2] = 0.9                  # clearly visible: this pilot tests mechanics, not perception
        for arm in (['seed'] if k == 1 else ['M0', 'M2', 'M1']):
            order += 1
            m = ({'file': f'{mem}/VP1_seed.jsonl', 'mode': 'off'} if arm == 'seed' else
                 {'file': f'{mem}/VP1_{arm}.jsonl', 'mode': ARMS[arm], 'init_from': f'{mem}/VP1_seed.jsonl'})
            trials.append({'id': f'VP{order:02d}', 'order': order, 'sequence': 'VP1', 'story': 'pilot', 'mission_index': k,
                           'world': f'VP1m{k}', 'config': arm, 'scene': 'swapped', 'expected': item, 'state': s,
                           'condition': 'pilot', 'transition': None if k == 1 else 'pilot',
                           'instruction': POOL[item][rng.randrange(len(POOL[item]))], 'world_spec': spec,
                           'expected_action': 'SEE_V_ANALYSIS', 'memory': m})
    return {'schema': 'rescuemind_campaign_v_pilot', 'seed': 'V-pilot', 'planned_n': len(trials), 'common_stack_args': [],
            'trials': trials}


def main():
    if '--pilot' in sys.argv:
        out = ROOT / 'experiments/campaign_v_pilot_protocol.json'
        out.write_text(json.dumps(build_pilot(), ensure_ascii=False, indent=1) + '\n')
        print('pilot written'); return
    out = ROOT / 'experiments/campaign_v_protocol.json'
    proto = build()
    if out.is_file() and json.loads(out.read_text()) != json.loads(json.dumps(proto, ensure_ascii=False)):
        sys.exit('registered protocol differs; refusing to overwrite')
    out.write_text(json.dumps(proto, ensure_ascii=False, indent=1) + '\n')
    n_fire = sum(s['fire'] for v in proto['sequence_states'].values() for s in v)
    n_rel = sum(s['relocated'] for v in proto['sequence_states'].values() for s in v)
    print(proto['planned_n'], 'trials;', n_fire, 'fire missions,', n_rel, 'relocated missions of', N_SEQ * N_MISSIONS)


if __name__ == '__main__':
    main()
