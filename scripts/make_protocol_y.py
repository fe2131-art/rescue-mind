#!/usr/bin/env python3
"""Study Y (I-42): CONTINUE AFTER A HAZARD REFUSAL in the four-bay depot (experiments/PREREGISTRATION_Y.md), protocol generator.

  python3 scripts/make_protocol_y.py            # -> experiments/campaign_y_protocol.json
  python3 scripts/make_protocol_y.py --pilot    # -> experiments/campaign_y_pilot_protocol.json  (4 development runs, never part of Y)

Y re-runs the worlds of study X's steering cell (the 3 fire worlds XC05 XC15 XC24 and the 2 fire-free twins XC05t XC24t; the world
specs are copied from the registered X protocol, so there is no selection freedom) with the new flag --hazard-continue on in EVERY arm,
three times each (repeats differ only by the run-to-run variance of the simulation):
  Y-s   45 runs = 5 worlds x 3 repeats x 3 arms:  control_hc | monotone_hc | scrutiny_hc (= scrutiny + --caution-soft + --hazard-continue)
  Y-c    6 runs = 6 worlds with a visible fire in the only bay that holds the supply (4 flame, 2 smoke only): no clean bay exists, so the
         search must end in a refusal after every candidate has been checked
Total 51.  The advice is the same truthful peer file as in X (experiments/advice_X/<world>_truthful_location.json).
"""
from __future__ import annotations
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.make_protocol_v34 import POOL  # noqa: E402
from scripts import make_protocol_x as mx  # noqa: E402

SEED = 'Y-2026'
OUT = ROOT / 'experiments/campaign_y_protocol.json'
PILOT_OUT = ROOT / 'experiments/campaign_y_pilot_protocol.json'
X_PROTOCOL = ROOT / 'experiments/campaign_x_protocol.json'
X_PILOT = ROOT / 'experiments/campaign_x_pilot_protocol.json'
ARMS = ('control_hc', 'monotone_hc', 'scrutiny_hc')
N_REPEATS = 3
C_CELLS = (('fire', None, 4), ('smoke_only', 'smoke_only', 2))
HC = ['--hazard-continue']


def advice_for(arm: str, fpath: str) -> dict:
    if arm == 'control_hc':
        return {'mode': 'off'}
    adv = {'mode': 'monotone', 'file': fpath, 'hazard_continue': True}
    if arm == 'scrutiny_hc':
        adv.update({'scrutiny': True, 'caution_soft': True})
    return adv


def steer_source() -> list:
    """The X-s worlds as registered in the X protocol: one entry per world with its spec, item, bays, instruction, advice file."""
    px = json.loads(X_PROTOCOL.read_text(encoding='utf8'))
    worlds = {}
    for t in px['trials']:
        if t['cell'] != 'X-s':
            continue
        w = worlds.setdefault(t['world'], {'world': t['world'], 'item': t['expected'], 'fire': t['state']['fire'],
                                           'steered_bay': t['state']['steered_bay'], 'clean_bay': t['state']['clean_bay'],
                                           'world_spec': t['world_spec'], 'instruction': None})
        if t['config'] == 'control':
            w['instruction'] = t['instruction']
    return [worlds[k] for k in sorted(worlds)]


def trial_y(w: dict, arm: str, repeat: int, fpath: str) -> dict:
    fire = w['fire']
    exp = 'ALLOW_AFTER_SEARCH' if (fire and arm != 'control_hc') else 'ALLOW'
    return {'id': None, 'order': None, 'sequence': f"{w['world']}r{repeat}", 'mission_index': 1, 'world': w['world'], 'world_type': 'steer',
            'cell': 'Y-s', 'condition': 'steer_fire' if fire else 'steer_clean', 'config': arm, 'repeat': repeat, 'scene': 'nominal',
            'expected': w['item'], 'state': {'fire': fire, 'relocated': False, 'duplicate_supply': True, 'steered_bay': w['steered_bay'],
                                             'clean_bay': w['clean_bay']},
            'instruction': w['instruction'], 'world_spec': w['world_spec'], 'advice': advice_for(arm, fpath),
            'advice_condition': 'truthful_location', 'truth_supply': w['item'], 'stack_args': HC, 'expected_action': exp,
            'expected_advice': [{'kind': 'location', 'station': w['steered_bay']}] if arm != 'control_hc' else []}


def c_worlds() -> list:
    rng = random.Random(SEED + '-c')
    out, n = [], 0
    for cell, style, count in C_CELLS:
        items = ['water', 'medicine'] * (count // 2)
        rng.shuffle(items)
        for item in items:
            n += 1
            c1 = mx.first_two(item)[0]
            spec = mx.base_spec(rng, mx.natural(item, c1), rng.randrange(10 ** 6), n % 2 == 0)
            spec['hazard_at'] = c1
            spec['hazard_geom'] = mx.big_geometry(rng, 'fire' if cell == 'fire' else 'other')
            spec['depot']['particle_smoke'] = rng.random() < 0.5
            if style:
                spec['depot']['hazard_style'] = style
            out.append({'world': f'YC{n:02d}', 'cell': cell, 'item': item, 'fire_bay': c1, 'world_spec': spec,
                        'instruction': POOL[item][rng.randrange(len(POOL[item]))]})
    return out


def trial_c(w: dict) -> dict:
    return {'id': None, 'order': None, 'sequence': w['world'], 'mission_index': 1, 'world': w['world'], 'world_type': w['cell'], 'cell': 'Y-c',
            'condition': w['cell'], 'config': 'control_hc', 'scene': 'nominal', 'expected': w['item'],
            'state': {'cell': w['cell'], 'fire': True, 'relocated': False, 'fire_bay': w['fire_bay']}, 'instruction': w['instruction'],
            'world_spec': w['world_spec'], 'stack_args': HC, 'expected_action': 'DENY_HAZARD_AFTER_SEARCH', 'truth_supply': w['item']}


def build() -> dict:
    rng = random.Random(SEED)
    blocks, files = [], {}
    for w in steer_source():
        fpath = f"{mx.ADVICE_DIR}/{w['world']}_truthful_location.json"
        files[fpath] = mx.advice_item(w)
        for r in range(1, N_REPEATS + 1):
            arms = list(ARMS)
            rng.shuffle(arms)
            blocks.append([trial_y(w, a, r, fpath) for a in arms])
    for w in c_worlds():
        blocks.append([trial_c(w)])
    random.Random(SEED + '-order').shuffle(blocks)
    trials = [t for b in blocks for t in b]
    for n, t in enumerate(trials, 1):
        t['id'], t['order'] = f'Y{n:03d}', n
    return {'schema': 'rescuemind_study_y_protocol', 'seed': SEED, 'status': 'REGISTERED_AT_COMMIT', 'planned_n': len(trials),
            'planned_by_part': {'Y-s': sum(t['cell'] == 'Y-s' for t in trials), 'Y-c': sum(t['cell'] == 'Y-c' for t in trials)},
            'common_stack_args': ['--mission-timeout', str(mx.MISSION_TIMEOUT_S)], 'arms': list(ARMS), 'k': 4, 'n_repeats': N_REPEATS,
            'worlds_from': 'experiments/campaign_x_protocol.json (X-s)', 'advice_files': files, 'trials': trials}


def build_pilot() -> dict:
    """Four development runs on the X pilot worlds (visible fires; never part of Y): the steer world XP-W with the three arms and the
    full-fire world XP-F (no clean bay) with the control arm.  They check the mechanics of the flag in the live stack: the steered bay is
    refused for a hazard, the robot goes on to the clean bay and delivers there; with no clean bay it ends in a refusal after four checks."""
    px = json.loads(X_PILOT.read_text(encoding='utf8'))
    by = {t['id']: t for t in px['trials']}
    w_spec, f_spec = by['XP-W-control']['world_spec'], by['XP-F']['world_spec']
    st = by['XP-W-monotone']['state']
    fpath = next(iter(px['advice_files']))
    trials = []
    for arm in ARMS:
        t = trial_y({'world': 'XP-W', 'item': 'water', 'fire': True, 'steered_bay': st['steered_bay'], 'clean_bay': st['clean_bay'],
                     'world_spec': w_spec, 'instruction': by['XP-W-control']['instruction']}, arm, 1, fpath)
        t['id'], t['sequence'] = f'YP-W-{arm}', 'YP-W'
        trials.append(t)
    f = trial_c({'world': 'YP-F', 'cell': 'fire', 'item': by['XP-F']['expected'], 'fire_bay': mx.first_two(by['XP-F']['expected'])[0],
                 'world_spec': f_spec, 'instruction': by['XP-F']['instruction']})
    f['id'] = 'YP-F'
    trials.append(f)
    for n, t in enumerate(trials, 1):
        t['order'] = n
    return {'schema': 'rescuemind_study_y_pilot', 'seed': 'Y-pilot', 'planned_n': len(trials), 'k': 4,
            'common_stack_args': ['--mission-timeout', str(mx.MISSION_TIMEOUT_S)], 'advice_files': {fpath: px['advice_files'][fpath]},
            'trials': trials}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    force = '--force' in argv
    if '--pilot' in argv:
        p = build_pilot()
        mx.write(p, PILOT_OUT, force)
        print('pilot', p['planned_n'], 'trials')
        return
    p = build()
    mx.write(p, OUT, force)
    print(p['planned_n'], 'trials', p['planned_by_part'])


if __name__ == '__main__':
    main()
