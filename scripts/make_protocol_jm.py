#!/usr/bin/env python3
"""Study JM (I-121): is the residual miss concentrated in worlds with a smoke plume?  A paired smoke ablation (experiments/PREREGISTRATION_JM.md).

  python3 scripts/make_protocol_jm.py                   # candidates (+ the protocol if a selection exists)
  python3 scripts/make_protocol_jm.py --select FILE     # FILE = design fire masks of the candidates -> experiments/campaign_jm_selection.json

GM's generator and realism variants with the seed `JM-2026` (no earlier world is reused): 72 candidates `JM001..`; the first 60 in id order whose design masks show the fire (>= 614 px from the front or a 0.4 m side pose, no model score) are
the fire worlds.  Every selected world is run as a TWIN PAIR that differs ONLY in the smoke plume: `<id>S` (depot.particle_smoke true) and `<id>N` (false).  Arms `v36` and `adapt` (as JK/JL), interleaved.
60 x 2 twins x 2 arms = 240 runs.  No fire-free worlds (a smoke plume exists only above a fire).
"""
from __future__ import annotations
import copy
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import make_protocol_gm as mg  # noqa: E402
from scripts import make_protocol_jk as mjk  # noqa: E402

SEED = 'JM-2026'
N_CANDIDATES, N_FIRE = 72, 60
VISIBLE_PX = mg.VISIBLE_PX
ARMS = {'v36': [], 'adapt': mjk.ADAPT}
COMMON = mg.COMMON
CANDIDATES = ROOT / 'experiments/campaign_jm_candidates.json'
SELECTION = ROOT / 'experiments/campaign_jm_selection.json'
OUT = ROOT / 'experiments/campaign_jm_protocol.json'


def fire_candidates() -> list:
    saved_seed, saved_n = mg.SEED, mg.N_CANDIDATES
    mg.SEED, mg.N_CANDIDATES = SEED, N_CANDIDATES
    try:
        ws = mg.fire_candidates()
    finally:
        mg.SEED, mg.N_CANDIDATES = saved_seed, saved_n
    for w in ws:
        w['world'] = w['world'].replace('GM', 'JM', 1)
    return ws


def twin(w: dict, smoke: bool) -> dict:
    t = copy.deepcopy(w)
    t['world'] = w['world'] + ('S' if smoke else 'N')
    t['world_spec']['depot']['particle_smoke'] = smoke
    return t


def candidates_protocol() -> dict:
    ws = fire_candidates()
    return {'schema': 'rescuemind_study_jm_candidates', 'seed': SEED, 'common_stack_args': COMMON,
            'rule': {'eligible': f'any of the front / left / right design masks >= {VISIBLE_PX} px', 'take': N_FIRE, 'order': 'id'},
            'trials': [{'id': w['world'], 'world': w['world'], 'scene': 'nominal', 'world_spec': twin(w, False)['world_spec'], 'order': n} for n, w in enumerate(ws, 1)]}   # masks are fire-only: the smoke flag does not matter for them


def trial(w: dict, arm: str) -> dict:
    return {'id': None, 'order': None, 'world': w['world'], 'config': arm, 'scene': 'nominal', 'expected': w['item'], 'condition': 'fire_hidden', 'instruction': w['instruction'],
            'world_spec': w['world_spec'], 'expected_action': 'DENY_HAZARD', 'stack_args': ARMS[arm]}


def select(masks: list) -> dict:
    px = {m['key']: m['fire_pixels'] for m in masks}
    sel, rows = [], {}
    for c in fire_candidates():
        w = c['world']
        if w not in px or w + 'L' not in px or w + 'R' not in px:
            continue
        rows[w] = {'F': px[w], 'L': px[w + 'L'], 'R': px[w + 'R']}
        if max(rows[w].values()) >= VISIBLE_PX and len(sel) < N_FIRE:
            sel.append(w)
    return {'rule': candidates_protocol()['rule'], 'selected': sel, 'n_eligible_in_candidates': sum(max(r.values()) >= VISIBLE_PX for r in rows.values()), 'design_pixels': rows}


def build(selection: dict) -> dict:
    cands = {c['world']: c for c in fire_candidates()}
    sel = selection['selected']
    rng = random.Random(SEED + '-order')
    blocks = []
    for x in sel:
        for smoke in (True, False):
            w = twin(cands[x], smoke)
            arms = list(ARMS)
            rng.shuffle(arms)
            blocks.append([trial(w, a) for a in arms])
    rng.shuffle(blocks)
    trials = [t for b in blocks for t in b]
    for n, t in enumerate(trials, 1):
        t['id'], t['order'] = f'JMT{n:03d}', n
    return {'schema': 'rescuemind_study_jm_protocol', 'seed': SEED, 'status': 'REGISTERED_AT_COMMIT', 'planned_n': len(trials), 'common_stack_args': COMMON,
            'configs': {'v36': 'v3.6 (orchestrator defaults)', 'adapt': 'v3.6 plus --adaptive-views 0.8 --adaptive-near 0'}, 'worlds_from': 'experiments/campaign_jm_selection.json',
            'jm': {'candidates': len(cands), 'selected': sel, 'twins': 'S = particle smoke plume, N = none; same world otherwise'}, 'trials': trials}


def write(proto: dict, out: Path, force: bool) -> None:
    new = json.loads(json.dumps(proto, ensure_ascii=False))
    if out.is_file() and json.loads(out.read_text()) != new and not force:
        sys.exit(f'registered protocol {out.name} differs from the generator output; refusing to overwrite (--force while it is a draft)')
    out.write_text(json.dumps(new, ensure_ascii=False, indent=1) + '\n')


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    force = '--force' in argv
    if '--select' in argv:
        files = [f for f in argv[argv.index('--select') + 1:] if not f.startswith('--')]
        sel = select([m for f in files for m in json.loads(Path(f).read_text())])
        SELECTION.write_text(json.dumps(sel, ensure_ascii=False, indent=1) + '\n')
        print('selected', len(sel['selected']), 'eligible', sel['n_eligible_in_candidates'], 'of', len(sel['design_pixels']))
    write(candidates_protocol(), CANDIDATES, force)
    if SELECTION.is_file():
        p = build(json.loads(SELECTION.read_text()))
        write(p, OUT, force)
        print(p['planned_n'], 'trials')


if __name__ == '__main__':
    main()
