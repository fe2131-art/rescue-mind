#!/usr/bin/env python3
"""Study B (I-24): does advice credit bound what a source that is wrong at EVERY mission can cost?  Closed loop, k = 2.

Generated BEFORE any trial (seeded, deterministic).  Sequences of m = 6 missions in the same nominal world family
(E-style randomised lighting and prop placement; each (sequence, mission) has its own world, shared by both arms).  The
requested supply is the same within a sequence.  Source 'peer' sends the SAME advice file at every mission:
  "the requested supply is at the other station"  (location advice, station = the other station)
  liar   : nominal scene (the supply is at its own, catalog station)  -> the advice is false every mission
  honest : swapped scene (the supply really is at the other station) -> the advice is true every mission
Arms (both monotone advice, frozen v3.6 stack otherwise):
  nocredit : --advice-mode monotone --advice-file F
  credit   : the same plus --advice-credit LEDGER, one ledger file per (sequence, arm), fresh at mission 1 and kept
             across the sequence (trial field advice_credit {file, init}), settled by the orchestrator after every mission.
Registered predictions (deterministic given correct mechanics; see experiments/PREREGISTRATION_B.md):
  liar   nocredit: first station = the other station at every mission, 1 wasted visit per mission (m in total)
  liar   credit  : missions 1..C_LOC wasted (credit 2 -> 1 -> 0), missions C_LOC+1..m throttled, first station = catalog
  honest both    : advice applied, the other station checked first and holds the supply, nothing throttled, 0 wasted visits
Runs: 3 liar + 1 honest sequence x 6 missions x 2 arms = 48.  The mechanics pilot uses 1 liar sequence of 3 missions on
separate seeds (6 runs).  Ground truth (scene) is used only by scripts/b_analysis.py.
"""
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind import advice_credit as ac  # noqa: E402
from rescuemind.robust_scenes import random_lighting  # noqa: E402
from scripts.make_protocol_v34 import POOL  # noqa: E402
from scripts.make_protocol_a import file_items, write, OTHER  # noqa: E402

SEED = 'B-2026'
M = 6
N_LIAR = 3
N_HONEST = 1
ARMS = ('nocredit', 'credit')
ADVICE_DIR = 'experiments/advice_B'
CREDIT_DIR = 'experiments/results/credit_B'
PILOT = dict(seed='B-pilot', prefix='BP', advice_dir='experiments/advice_B_pilot', credit_dir='experiments/results/credit_B_pilot',
             m=3, n_liar=1, n_honest=0)


def world_spec(rng, item: str) -> dict:
    return {'lighting_params': random_lighting(rng),
            'prop_offsets': {n: [round(rng.uniform(-.12, .12), 3), round(rng.uniform(-.12, .12), 3),
                                 round(rng.uniform(-math.pi, math.pi), 3)] for n in ('sealed_water_bottles', 'first_aid_case')}}


def predictions(condition: str, arm: str, k: int, item: str) -> dict:
    """What the registered mechanics say for mission k (1-based) of a sequence."""
    other = OTHER[item]
    if condition == 'honest':
        return {'expected_action': 'ALLOW', 'expected_first_station': other, 'expected_wasted_visits': 0, 'expected_throttled': 0}
    if arm == 'nocredit' or k <= int(ac.C_LOC):
        return {'expected_action': 'ALLOW_AFTER_SEARCH', 'expected_first_station': other, 'expected_wasted_visits': 1,
                'expected_throttled': 0}
    return {'expected_action': 'ALLOW', 'expected_first_station': item, 'expected_wasted_visits': 0, 'expected_throttled': 1}


def build(seed: str = SEED, prefix: str = 'B', advice_dir: str = ADVICE_DIR, credit_dir: str = CREDIT_DIR, m: int = M,
          n_liar: int = N_LIAR, n_honest: int = N_HONEST) -> dict:
    rng = random.Random(seed)
    kinds = ['liar'] * n_liar + ['honest'] * n_honest
    items = (['water', 'medicine'] * n_liar)[:n_liar]       # liar sequences: both supplies when n_liar >= 2
    rng.shuffle(items)
    items += (['medicine', 'water'] * n_honest)[:n_honest]
    seqs, files, cells = {}, {}, []
    counts = {'liar': 0, 'honest': 0}
    for kind, item in zip(kinds, items):
        counts[kind] += 1
        seq = f'{prefix}{kind[0].upper()}{counts[kind]}'
        fpath = f'{advice_dir}/{seq}_{kind}.json'
        files[fpath] = file_items('truthful_location', item)           # source 'peer': location = the other station
        seqs[seq] = {'condition': kind, 'item': item, 'scene': 'nominal' if kind == 'liar' else 'swapped', 'advice_file': fpath}
        for k in range(1, m + 1):
            cells.append((seq, k, world_spec(rng, item), POOL[item][rng.randrange(len(POOL[item]))]))
    worlds = {(s, k): (w, ins) for s, k, w, ins in cells}
    trials = []
    for k in range(1, m + 1):                      # round-robin over missions: drift protection, per-(sequence, arm) order kept
        order = list(seqs)
        rng.shuffle(order)
        for seq in order:
            arms = list(ARMS)
            rng.shuffle(arms)
            s = seqs[seq]
            spec, ins = worlds[(seq, k)]
            for arm in arms:
                t = dict(sequence=seq, mission_index=k, world=f'{seq}m{k}', scene=s['scene'], expected=s['item'], world_spec=spec,
                         condition=s['condition'], advice_condition=s['condition'], config=arm, transition=None, instruction=ins,
                         advice={'mode': 'monotone', 'file': s['advice_file']},
                         state={'relocated': s['condition'] == 'honest', 'fire': False}, **predictions(s['condition'], arm, k, s['item']))
                if arm == 'credit':
                    t['advice_credit'] = {'file': f'{credit_dir}/{seq}_credit.json', 'init': 'fresh' if k == 1 else 'keep'}
                trials.append(t)
    for n, t in enumerate(trials):
        t['id'] = f'{prefix}{n + 1:03d}'
        t['order'] = n + 1
    return {'schema': 'rescuemind_study_b_campaign' if prefix == 'B' else 'rescuemind_study_b_pilot', 'seed': seed,
            'planned_n': len(trials), 'm': m, 'c_loc': ac.C_LOC, 'arms': list(ARMS), 'sequences': seqs, 'common_stack_args': [],
            'note': 'common_stack_args empty = orchestrator defaults (v3.6); advice and credit flags come from each trial',
            'advice_files': files, 'trials': trials}


def main():
    pilot = '--pilot' in sys.argv
    p = build(**PILOT) if pilot else build()
    write(p, ROOT / ('experiments/campaign_b_pilot_protocol.json' if pilot else 'experiments/campaign_b_protocol.json'))
    print('pilot' if pilot else 'campaign', p['planned_n'], 'trials', {s: v['condition'] for s, v in p['sequences'].items()})


if __name__ == '__main__':
    main()
