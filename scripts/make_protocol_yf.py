#!/usr/bin/env python3
"""Study YF (I-43): Y ON FRESH WORLDS (experiments/PREREGISTRATION_YF.md), protocol generator.

  python3 scripts/make_protocol_yf.py                   # candidates -> experiments/campaign_yf_candidates.json (+ the protocol if a selection exists)
  python3 scripts/make_protocol_yf.py --select FILE...  # FILEs = design fire masks of the candidates (batches a and b) -> experiments/campaign_yf_selection.json

Study Y re-ran the five steering worlds of X (not blind: the X outcomes shaped its predictions; its tighten-only miss is ONE world, XC05, three repeats).
YF repeats Y with worlds nobody has seen: 48 candidates from the new seed `YF-2026`, the X selection rule on their design masks (front <= 20 px and a
side pose >= 614 px, no model score), the first 6 in id order as fire worlds and the fire-free twins of every second one (3), three arms (control_hc,
monotone_hc, scrutiny_hc, all with --hazard-continue), one run per world and arm (the worlds are the replicates). Total (6 + 3) x 3 = 27 runs; fewer eligible
means a smaller cell, never padded.  The advice is the same truthful peer item as in X and Y (the second inventory bay holds the supply as well).
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
from scripts import make_protocol_y as my  # noqa: E402

SEED = 'YF-2026'
N_CANDIDATES, N_FIRE, N_TWINS = 48, 6, 3
N_CANDIDATES_B = 48            # Amendment 1 (before any YF trial and any model score): a second batch FC49-FC96, see PREREGISTRATION_YF.md
ADVICE_DIR = 'experiments/advice_YF'
CANDIDATES = ROOT / 'experiments/campaign_yf_candidates.json'
CANDIDATES_B = ROOT / 'experiments/campaign_yf_candidates_b.json'
SELECTION = ROOT / 'experiments/campaign_yf_selection.json'
OUT = ROOT / 'experiments/campaign_yf_protocol.json'


def _batch(stream: str, n: int, first: int) -> list:
    rng = random.Random(SEED + stream)
    items = ['water', 'medicine'] * (n // 2)
    rng.shuffle(items)
    out = []
    for i, item in enumerate(items):
        w = mx.steer_world(rng, f'FC{first + i:02d}', item, True)
        w['instruction'] = POOL[item][rng.randrange(len(POOL[item]))]
        out.append(w)
    return out


def candidates_a() -> list:
    return _batch('-steer', N_CANDIDATES, 1)                      # FC01-FC48 (the registered first batch; unchanged by Amendment 1)


def candidates_b() -> list:
    return _batch('-steer-b', N_CANDIDATES_B, N_CANDIDATES + 1)   # FC49-FC96 (Amendment 1: an independent stream of the same generator)


def candidates() -> list:
    return candidates_a() + candidates_b()


def candidates_protocol(batch: str = 'a') -> dict:
    cs = candidates_a() if batch == 'a' else candidates_b()
    return {'schema': 'rescuemind_study_yf_candidates', 'seed': SEED, 'batch': batch, 'rule': {
        'eligible': f'front design mask <= {mx.HARD_MAX_FRONT_PX} px and L or R >= {mx.VISIBLE_PX} px', 'take': N_FIRE, 'order': 'id (batch a, then batch b)'},
        'trials': [{'id': c['world'], 'world': c['world'], 'scene': 'nominal', 'world_spec': c['world_spec'], 'order': int(c['world'][2:])} for c in cs]}


def select(masks: list) -> dict:
    px = {m['key']: m['fire_pixels'] for m in masks}
    sel, rows = [], {}
    for c in candidates():
        w = c['world']
        if w not in px or w + 'L' not in px or w + 'R' not in px:
            continue
        rows[w] = {'F': px[w], 'L': px[w + 'L'], 'R': px[w + 'R']}
        if px[w] <= mx.HARD_MAX_FRONT_PX and max(px[w + 'L'], px[w + 'R']) >= mx.VISIBLE_PX and len(sel) < N_FIRE:
            sel.append(w)
    return {'rule': candidates_protocol('a')['rule'], 'selected': sel, 'n_eligible_in_candidates': sum(
        r['F'] <= mx.HARD_MAX_FRONT_PX and max(r['L'], r['R']) >= mx.VISIBLE_PX for r in rows.values()), 'design_pixels': rows}


def build(selection: dict | None = None) -> dict:
    cands = {c['world']: c for c in candidates()}
    sel = (selection or {}).get('selected') or []
    fire_worlds = [cands[w] for w in sel]
    rng = random.Random(SEED)
    twins = []
    for w in fire_worlds[::2][:N_TWINS]:
        t = dict(mx.steer_world(rng, f"{w['world']}t", w['item'], False, w['world'], w['world_spec']))
        t['instruction'] = w['instruction']
        twins.append(t)
    blocks, files = [], {}
    for w in fire_worlds + twins:
        fpath = f"{ADVICE_DIR}/{w['world']}_truthful_location.json"
        files[fpath] = mx.advice_item(w)
        arms = list(my.ARMS)
        rng.shuffle(arms)
        blocks.append([my.trial_y(w, a, 1, fpath) for a in arms])
    random.Random(SEED + '-order').shuffle(blocks)
    trials = [t for b in blocks for t in b]
    for n, t in enumerate(trials, 1):
        t['id'], t['order'] = f'YF{n:03d}', n
        t['cell'] = 'Y-s'
    return {'schema': 'rescuemind_study_yf_protocol', 'seed': SEED, 'status': 'REGISTERED_AT_COMMIT', 'planned_n': len(trials),
            'planned_by_part': {'Y-s': len(trials), 'Y-c': 0}, 'common_stack_args': ['--mission-timeout', str(mx.MISSION_TIMEOUT_S)], 'arms': list(my.ARMS),
            'k': 4, 'n_repeats': 1, 'worlds_from': 'experiments/campaign_yf_selection.json (fresh candidates, seed YF-2026)', 'advice_files': files,
            'yf': {'candidates': len(cands), 'selected': sel, 'twins_of': [w['twin_of'] for w in twins]}, 'trials': trials}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    force = '--force' in argv
    if '--select' in argv:
        files = argv[argv.index('--select') + 1:]
        files = [f for f in files if not f.startswith('--')]
        sel = select([m for f in files for m in json.loads(Path(f).read_text())])
        SELECTION.write_text(json.dumps(sel, ensure_ascii=False, indent=1) + '\n')
        print('selected', sel['selected'], 'eligible', sel['n_eligible_in_candidates'], 'of', len(sel['design_pixels']))
    if not CANDIDATES.is_file():                  # the registered first batch is never rewritten (Amendment 1 only adds batch b)
        mx.write(candidates_protocol('a'), CANDIDATES, force)
    mx.write(candidates_protocol('b'), CANDIDATES_B, force)
    p = build(json.loads(SELECTION.read_text()) if SELECTION.is_file() else None)
    if p['planned_n']:
        mx.write(p, OUT, force)
    print(p['planned_n'], 'trials', p['planned_by_part'])


if __name__ == '__main__':
    main()
