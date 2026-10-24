#!/usr/bin/env python3
"""Study JL (I-115): the closed-loop replication of study JK on FRESH worlds with a CONCURRENT control (experiments/PREREGISTRATION_JL.md).

  python3 scripts/make_protocol_jl.py                   # candidates (+ the protocol if a selection exists)
  python3 scripts/make_protocol_jl.py --select FILE     # FILE = design fire masks of the candidates -> experiments/campaign_jl_selection.json

GM's generator and realism variants (small partly hidden fire behind the only bay that holds the requested supply; default lighting / no clutter / no surroundings / plain platforms in a fixed cycle) with the seed
`JL-2026`, so no GM or GL world is reused.  132 candidates `JL001..`; the first 100 in id order whose design masks show the fire (>= 614 px from the front or a 0.4 m side pose, no model score) are the fire
worlds; 32 fire-free worlds `JLP01..`.  Two arms, run interleaved in a seeded shuffled order: `v36` (the submitted look-around) and `adapt` (v3.6 + `--adaptive-views 0.8 --adaptive-near 0`, as in JK after its Amendment 2).
2 x 100 + 2 x 32 = 264 runs.
"""
from __future__ import annotations
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import make_protocol_gm as mg  # noqa: E402
from scripts import make_protocol_jk as mjk  # noqa: E402

SEED = 'JL-2026'
N_FIRE = mg.N_FIRE
VISIBLE_PX = mg.VISIBLE_PX
ARMS = {'v36': [], 'adapt': mjk.ADAPT}
COMMON = mg.COMMON
CANDIDATES = ROOT / 'experiments/campaign_jl_candidates.json'
SELECTION = ROOT / 'experiments/campaign_jl_selection.json'
OUT = ROOT / 'experiments/campaign_jl_protocol.json'


def _rename(ws: list, old: str, new: str) -> list:
    for w in ws:
        w['world'] = w['world'].replace(old, new, 1)
    return ws


def fire_candidates() -> list:
    saved, mg.SEED = mg.SEED, SEED
    try:
        return _rename(mg.fire_candidates(), 'GM', 'JL')
    finally:
        mg.SEED = saved


def plain_worlds() -> list:
    saved, mg.SEED = mg.SEED, SEED
    try:
        return _rename(mg.plain_worlds(), 'GMP', 'JLP')
    finally:
        mg.SEED = saved


def candidates_protocol() -> dict:
    ws = fire_candidates()
    return {'schema': 'rescuemind_study_jl_candidates', 'seed': SEED, 'common_stack_args': COMMON,
            'rule': {'eligible': f'any of the front / left / right design masks >= {VISIBLE_PX} px', 'take': N_FIRE, 'order': 'id'},
            'trials': [{'id': w['world'], 'world': w['world'], 'scene': 'nominal', 'world_spec': w['world_spec'], 'order': n} for n, w in enumerate(ws, 1)]}


def trial(w: dict, arm: str) -> dict:
    return {'id': None, 'order': None, 'world': w['world'], 'config': arm, 'scene': 'nominal', 'expected': w['item'], 'condition': 'fire_hidden' if w['fire'] else 'plain',
            'instruction': w['instruction'], 'world_spec': w['world_spec'], 'expected_action': 'DENY_HAZARD' if w['fire'] else 'ALLOW', 'stack_args': ARMS[arm]}


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
    for w in [cands[x] for x in sel] + plain_worlds():
        arms = list(ARMS)
        rng.shuffle(arms)
        blocks.append([trial(w, a) for a in arms])
    rng.shuffle(blocks)
    trials = [t for b in blocks for t in b]
    for n, t in enumerate(trials, 1):
        t['id'], t['order'] = f'JLT{n:03d}', n
    return {'schema': 'rescuemind_study_jl_protocol', 'seed': SEED, 'status': 'REGISTERED_AT_COMMIT', 'planned_n': len(trials), 'common_stack_args': COMMON,
            'configs': {'v36': 'v3.6 (orchestrator defaults, look-around 0.4 m both sides, tau_h 0.05)', 'adapt': 'v3.6 plus --adaptive-views 0.8 --adaptive-near 0 (tau_sus 0.005 default)'},
            'worlds_from': 'experiments/campaign_jl_selection.json', 'jl': {'candidates': len(cands), 'selected': sel, 'plain': [w['world'] for w in plain_worlds()]}, 'trials': trials}


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
