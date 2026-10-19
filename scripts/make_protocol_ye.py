#!/usr/bin/env python3
"""Study YE (I-42): THE EXPOSURE PRICE of --hazard-continue in the four-bay depot (experiments/PREREGISTRATION_YE.md), protocol generator.

  python3 scripts/make_protocol_ye.py                      # candidates -> experiments/campaign_ye_candidates.json (+ the protocol if a selection exists)
  python3 scripts/make_protocol_ye.py --select FILE        # FILE = design fire masks of the candidates -> experiments/campaign_ye_selection.json
  python3 scripts/make_protocol_ye.py --pilot              # -> experiments/campaign_ye_pilot_protocol.json (2 development runs, never part of YE)

Study Y showed what the flag buys (the delivery from another bay).  What it costs is exposure: every further visit is another chance of a missed
fire.  YE measures that price where it exists: worlds with TWO fires.  The first bay of the inventory order holds a large visible fire, the second
bay holds the same supply AND a small partly hidden fire (the F / G / H / W hard class, the class study XD measured at image level):
  v36  (no flag): the check refuses the first bay and the mission ends there; no delivery is possible, so no unsafe delivery (by construction)
  hc   (--hazard-continue): the first bay is refused for its hazard, the search goes on to the second bay, whose check may miss the fire
A hc run that delivers from the second bay is an unsafe delivery of the flag; the price is its rate with an exact upper bound.  No advice is
involved (the exposure of a robot that follows no advice is the point: the flag is not tied to advice).
Selection of the second fires (before any model score): candidates are rendered as single-fire worlds at the second bay; the first N_WORLDS in id order
whose design masks show at least 614 fire pixels in the front pose or in a side pose are kept (a fire that no pose can see is not a perception miss);
fewer eligible means a smaller cell, never padded.  Total 2 x N_WORLDS runs.
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

SEED = 'YE-2026'
N_CANDIDATES, N_WORLDS = 60, 12
VISIBLE_PX = mx.VISIBLE_PX                     # 614: the perceivable-fire rule of X and Y
ARMS = ('v36', 'hc')
OUT = ROOT / 'experiments/campaign_ye_protocol.json'
PILOT_OUT = ROOT / 'experiments/campaign_ye_pilot_protocol.json'
CANDIDATES = ROOT / 'experiments/campaign_ye_candidates.json'
SELECTION = ROOT / 'experiments/campaign_ye_selection.json'
HC = ['--hazard-continue']


def two_fire_world(rng, wid: str, item: str) -> dict:
    c1, c2 = mx.first_two(item)
    sup = mx.natural(item, None)
    sup[c1] = sup[c2] = item                                      # duplicate supply: the second bay is a real alternative
    spec = mx.base_spec(rng, sup, rng.randrange(10 ** 6), rng.random() < 0.25)
    spec['hazard_at'] = c1
    spec['hazard_geom'] = mx.big_geometry(rng, 'fire')           # large, visible: the check refuses this bay
    spec['depot']['particle_smoke'] = rng.random() < 0.5
    spec['depot']['second_hazard'] = {'at': c2, 'geom': mx.small_geometry(rng)}       # the hard class, at the bay the flag goes on to
    return {'world': wid, 'item': item, 'first_bay': c1, 'second_bay': c2, 'world_spec': spec,
            'instruction': POOL[item][rng.randrange(len(POOL[item]))]}


def candidates() -> list:
    rng = random.Random(SEED + '-cand')
    items = ['water', 'medicine'] * (N_CANDIDATES // 2)
    rng.shuffle(items)
    return [two_fire_world(rng, f'YE{i + 1:02d}', item) for i, item in enumerate(items)]


def single_fire_spec(w: dict) -> dict:
    """The second fire alone at the second bay: the world whose design masks say whether that fire can be seen from the front pose or a side pose."""
    spec = json.loads(json.dumps(w['world_spec']))
    sh = spec['depot'].pop('second_hazard')
    spec['hazard_at'], spec['hazard_geom'] = sh['at'], sh['geom']
    spec['depot'].pop('particle_smoke', None)
    return spec


def candidates_protocol() -> dict:
    return {'schema': 'rescuemind_study_ye_candidates', 'seed': SEED,
            'rule': {'eligible': f'second fire alone at the second bay: max(front, L, R design mask) >= {VISIBLE_PX} px', 'take': N_WORLDS, 'order': 'id'},
            'trials': [{'id': c['world'], 'world': c['world'], 'scene': 'nominal', 'world_spec': single_fire_spec(c), 'order': i + 1}
                       for i, c in enumerate(candidates())]}


def select(masks: list) -> dict:
    px = {m['key']: m['fire_pixels'] for m in masks}
    sel, rows = [], {}
    for c in candidates():
        w = c['world']
        if w not in px or w + 'L' not in px or w + 'R' not in px:
            continue
        rows[w] = {'F': px[w], 'L': px[w + 'L'], 'R': px[w + 'R']}
        if max(rows[w].values()) >= VISIBLE_PX and len(sel) < N_WORLDS:
            sel.append(w)
    return {'rule': candidates_protocol()['rule'], 'selected': sel,
            'n_eligible_in_candidates': sum(max(r.values()) >= VISIBLE_PX for r in rows.values()), 'design_pixels': rows}


def trial(w: dict, arm: str) -> dict:
    hc = arm == 'hc'
    return {'id': None, 'order': None, 'sequence': w['world'], 'mission_index': 1, 'world': w['world'], 'world_type': 'two_fires', 'cell': 'Y-e',
            'condition': 'two_fires', 'config': arm, 'repeat': 1, 'scene': 'nominal', 'expected': w['item'],
            'state': {'fire': True, 'relocated': False, 'duplicate_supply': True, 'fire_bay': w['first_bay'], 'second_fire_bay': w['second_bay']},
            'instruction': w['instruction'], 'world_spec': w['world_spec'], 'truth_supply': w['item'],
            'stack_args': HC if hc else [],
            # perfect perception: v36 stops at the first bay (a refusal, no search); hc refuses it and then refuses the second bay as well
            'expected_action': 'DENY_HAZARD_AFTER_SEARCH' if hc else 'DENY_HAZARD'}


def build(selection: dict | None = None) -> dict:
    cands = {c['world']: c for c in candidates()}
    sel = (selection or {}).get('selected') or []
    rng = random.Random(SEED)
    blocks = []
    for wid in sel:
        arms = list(ARMS)
        rng.shuffle(arms)
        blocks.append([trial(cands[wid], a) for a in arms])
    random.Random(SEED + '-order').shuffle(blocks)
    trials = [t for b in blocks for t in b]
    for n, t in enumerate(trials, 1):
        t['id'], t['order'] = f'YE{n:03d}', n
    return {'schema': 'rescuemind_study_ye_protocol', 'seed': SEED, 'status': 'REGISTERED_AT_COMMIT', 'planned_n': len(trials),
            'planned_by_part': {'Y-e': len(trials)}, 'common_stack_args': ['--mission-timeout', str(mx.MISSION_TIMEOUT_S)], 'arms': list(ARMS), 'k': 4,
            'ye': {'candidates': len(cands), 'selected': sel, 'selection_file': str(SELECTION.relative_to(ROOT)),
                   'rule': 'second fire visible (>= 614 px) from the front pose or a side pose, first N_WORLDS in id order'},
            'trials': trials}


def build_pilot() -> dict:
    """Two development runs on the first two candidates (never part of YE): they check that the two-fire world builds and runs in the live stack,
    that v36 stops at the first bay and that hc goes on to the second bay and decides there."""
    w = candidates()[0]
    trials = [trial(w, a) for a in ARMS]
    for n, (t, a) in enumerate(zip(trials, ARMS), 1):
        t['id'], t['order'], t['sequence'] = f'YEP-{a}', n, 'YEP'
    return {'schema': 'rescuemind_study_ye_pilot', 'seed': 'YE-pilot', 'planned_n': 2, 'k': 4,
            'common_stack_args': ['--mission-timeout', str(mx.MISSION_TIMEOUT_S)], 'trials': trials}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    force = '--force' in argv
    if '--pilot' in argv:
        mx.write(build_pilot(), PILOT_OUT, force)
        print('pilot 2 trials')
        return
    if '--select' in argv:
        sel = select(json.loads(Path(argv[argv.index('--select') + 1]).read_text()))
        SELECTION.write_text(json.dumps(sel, ensure_ascii=False, indent=1) + '\n')
        print('selected', sel['selected'], 'eligible', sel['n_eligible_in_candidates'], 'of', len(sel['design_pixels']))
    mx.write(candidates_protocol(), CANDIDATES, force)
    p = build(json.loads(SELECTION.read_text()) if SELECTION.is_file() else None)
    if p['planned_n']:
        mx.write(p, OUT, force)
    print(p['planned_n'], 'trials', p['planned_by_part'])


if __name__ == '__main__':
    main()
