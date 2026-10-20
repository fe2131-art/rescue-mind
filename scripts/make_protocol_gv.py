#!/usr/bin/env python3
"""Study GV (I-58): wider look-around views (0.8 m instead of 0.4 m) with a threshold calibrated on missions with the same views, in closed loop at the depot (experiments/PREREGISTRATION_GV.md), protocol generator.

  python3 scripts/make_protocol_gv.py                   # candidates + pilot + calibration protocol (+ the protocol if a selection exists)
  python3 scripts/make_protocol_gv.py --select FILE     # FILE = design fire masks of the candidates -> experiments/campaign_gv_selection.json

GD showed that a calibrated threshold controls false stops at the depot but does not lower the miss rate: the hard fires score inside the clean-world tail from the 0.4 m side views.  At image level in XD
(post hoc, `devset_xd_h36_tiles.json`), the views 0.8 m to the side separate them: front + 0.8 m views miss 1 of 100 hard-class worlds at the rank rule alpha = 5% (threshold 0.030), the 0.4 m views 6 of 100 (0.018).
GV runs this in closed loop.  Arms: `v36` (submitted v3.6), `wide` (look-around 0.8 m, tau_h 0.05: the geometry alone), `wcal` (look-around 0.8 m and tau_h = the rank rule at alpha = 2% over 100 fire-free depot
missions run with the same wide views and the threshold off, `scripts/gv_calibrate.py`).  72 candidates (seed `GV-2026`), the first 40 whose design masks (front, 0.4 m side poses; no model score) show the fire
(>= 614 px) are the fire worlds, 24 fire-free worlds.  3 x 40 fire runs + 2 x 24 fire-free runs = 168 runs if 40 qualify.
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

SEED = 'GV-2026'
N_CANDIDATES, N_FIRE, N_PLAIN, N_CAL = 72, 40, 24, 100
VISIBLE_PX = mx.VISIBLE_PX                     # 614: the perceivable-fire rule of X, Y, GR and GC
WIDE = ['--look-around', '0.8']                  # the side views 0.8 m left and right of the bay (v3.6 uses 0.4 m)
CONFIG_V36 = []                                 # orchestrator defaults = v3.6 (look-around 0.4 m, tau_h 0.05)
CONFIG_WIDE = WIDE                              # geometry alone: look-around 0.8 m, tau_h 0.05
CONFIG_WCAL = WIDE + ['--site-config', 'experiments/gv_site_cal.json']     # look-around 0.8 m and tau_h from the rank rule over 100 fire-free missions with the same views
ARMS = {'v36': CONFIG_V36, 'wide': CONFIG_WIDE, 'wcal': CONFIG_WCAL}
CLEAN_ARMS = ('wcal', 'wide')                   # the fire-free worlds measure false stops of the calibrated arm and of the wide views alone
CONFIG_OPEN = WIDE + ['--site-config', 'experiments/gv_site_open.json']       # Amendment 1: tau_h 1.0 (never refuses for a hazard), so every mission scores the front and both side views: the calibration runs
CALIBRATION = ROOT / 'experiments/campaign_gvk_protocol.json'
COMMON = ['--mission-timeout', str(mx.MISSION_TIMEOUT_S)]
CANDIDATES = ROOT / 'experiments/campaign_gv_candidates.json'
PILOT = ROOT / 'experiments/campaign_gv_pilot_protocol.json'
SELECTION = ROOT / 'experiments/campaign_gv_selection.json'
OUT = ROOT / 'experiments/campaign_gv_protocol.json'


def _spec(rng: random.Random, item: str, fire: bool, geom: list | None = None) -> dict:
    """The depot with the requested supply at its first inventory bay only; the fire (if any) stands behind that bay."""
    c1, _ = mx.first_two(item)
    spec = mx.base_spec(rng, mx.natural(item, c1), rng.randrange(10 ** 6), rng.random() < 0.25)
    if fire:
        spec['hazard_at'] = c1
        spec['hazard_geom'] = geom or mx.small_geometry(rng)
        spec['depot']['particle_smoke'] = rng.random() < 0.5
    return spec


def fire_candidates() -> list:
    rng = random.Random(SEED + '-fire')
    items = ['water', 'medicine'] * (N_CANDIDATES // 2)
    rng.shuffle(items)
    return [{'world': f'GV{i + 1:02d}', 'item': it, 'fire': True, 'world_spec': _spec(rng, it, True),
             'instruction': POOL[it][rng.randrange(len(POOL[it]))]} for i, it in enumerate(items)]


def plain_worlds() -> list:
    rng = random.Random(SEED + '-plain')
    items = ['water', 'medicine'] * (N_PLAIN // 2)
    rng.shuffle(items)
    return [{'world': f'GVP{i + 1:02d}', 'item': it, 'fire': False, 'world_spec': _spec(rng, it, False),
             'instruction': POOL[it][rng.randrange(len(POOL[it]))]} for i, it in enumerate(items)]


def calibration_worlds() -> list:
    """100 fire-free depot worlds of the GV generator (never part of GV), one mission each with the threshold off; their per-world maximum view score calibrates tau_h."""
    rng = random.Random(SEED + '-cal')
    items = ['water', 'medicine'] * (N_CAL // 2)
    rng.shuffle(items)
    return [{'world': f'GVK{i + 1:03d}', 'item': it, 'fire': False, 'world_spec': _spec(rng, it, False),
             'instruction': POOL[it][rng.randrange(len(POOL[it]))]} for i, it in enumerate(items)]


def calibration_protocol() -> dict:
    ts = []
    for n, w in enumerate(calibration_worlds(), 1):
        t = trial(w, 'open')
        t['id'], t['order'] = f'GVK{n:03d}', n
        ts.append(t)
    return {'schema': 'rescuemind_study_gv_calibration', 'seed': SEED + '-cal', 'planned_n': len(ts), 'common_stack_args': COMMON,
            'configs': {'open': 'v3.6 with --look-around 0.8 and --site-config experiments/gv_site_open.json (tau_h 1.0: no hazard refusal, all three views scored)'}, 'trials': ts}


def pilot_worlds() -> list:
    """Mechanics pilot (never part of GV): a fire world whose fire is large by construction (the big-fire geometry of X-a) and a fire-free world."""
    rng = random.Random(SEED + '-pilot')
    fire = {'world': 'GVQ1', 'item': 'water', 'fire': True, 'world_spec': _spec(rng, 'water', True, [0.9, 0.3, 1.0]), 'instruction': POOL['water'][0]}
    plain = {'world': 'GVQ2', 'item': 'medicine', 'fire': False, 'world_spec': _spec(rng, 'medicine', False), 'instruction': POOL['medicine'][0]}
    return [fire, plain]


def candidates_protocol() -> dict:
    ws = pilot_worlds()[:1] + fire_candidates()          # GVQ1's masks are rendered with the candidates (the pilot gate needs its front pixels)
    return {'schema': 'rescuemind_study_gv_candidates', 'seed': SEED, 'common_stack_args': COMMON,
            'rule': {'eligible': f'any of the front / left / right design masks >= {VISIBLE_PX} px', 'take': N_FIRE, 'order': 'id'},
            'trials': [{'id': w['world'], 'world': w['world'], 'scene': 'nominal', 'world_spec': w['world_spec'], 'order': n} for n, w in enumerate(ws, 1)]}


def trial(w: dict, arm: str) -> dict:
    return {'id': None, 'order': None, 'world': w['world'], 'config': arm, 'scene': 'nominal', 'expected': w['item'],
            'condition': 'fire_hidden' if w['fire'] else 'plain', 'instruction': w['instruction'], 'world_spec': w['world_spec'],
            'expected_action': 'DENY_HAZARD' if w['fire'] else 'ALLOW', 'stack_args': {**ARMS, 'open': CONFIG_OPEN}[arm]}


def pilot_protocol() -> dict:
    ts = [trial(pilot_worlds()[0], 'wcal'), trial(pilot_worlds()[1], 'wcal')]
    for n, t in enumerate(ts, 1):
        t['id'], t['order'] = f'GVPILOT{n}', n
    return {'schema': 'rescuemind_study_gv_pilot', 'seed': SEED, 'planned_n': len(ts), 'common_stack_args': COMMON, 'trials': ts}


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
    pilot = {k: px.get(k) for k in ('GVQ1', 'GVQ1L', 'GVQ1R')}
    return {'rule': candidates_protocol()['rule'], 'selected': sel, 'n_eligible_in_candidates': sum(max(r.values()) >= VISIBLE_PX for r in rows.values()),
            'design_pixels': rows, 'pilot_design_pixels': pilot}


def build(selection: dict | None = None) -> dict:
    cands = {c['world']: c for c in fire_candidates()}
    sel = (selection or {}).get('selected') or []
    rng = random.Random(SEED + '-order')
    blocks = []
    for w in [cands[x] for x in sel]:
        arms = list(ARMS)
        rng.shuffle(arms)
        blocks.append([trial(w, a) for a in arms])
    for w in plain_worlds():                                  # the fire-free worlds: the calibrated arm and the wide views alone
        arms = list(CLEAN_ARMS)
        rng.shuffle(arms)
        blocks.append([trial(w, a) for a in arms])
    rng.shuffle(blocks)
    trials = [t for b in blocks for t in b]
    for n, t in enumerate(trials, 1):
        t['id'], t['order'] = f'GV{n:03d}', n
    return {'schema': 'rescuemind_study_gv_protocol', 'seed': SEED, 'status': 'REGISTERED_AT_COMMIT', 'planned_n': len(trials), 'common_stack_args': COMMON,
            'configs': {'v36': 'v3.6 (orchestrator defaults, look-around 0.4 m, tau_h 0.05)', 'wide': 'v3.6 with --look-around 0.8', 'wcal': 'v3.6 with --look-around 0.8 and --site-config experiments/gv_site_cal.json (tau_h from scripts/gv_calibrate.py, h36, tiles)'},
            'worlds_from': 'experiments/campaign_gv_selection.json',
            'gd': {'candidates': len(cands), 'selected': sel, 'plain': [w['world'] for w in plain_worlds()]}, 'trials': trials}


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
    write(pilot_protocol(), PILOT, force)
    write(calibration_protocol(), CALIBRATION, force)
    p = build(json.loads(SELECTION.read_text()) if SELECTION.is_file() else None)
    if p['planned_n'] > len(CLEAN_ARMS) * N_PLAIN:
        write(p, OUT, force)
    print(p['planned_n'], 'trials')


if __name__ == '__main__':
    main()
