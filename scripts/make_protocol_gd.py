#!/usr/bin/env python3
"""Study GD (I-51): the per-site calibrated hazard threshold in closed loop at a SECOND site, the four-bay depot (experiments/PREREGISTRATION_GD.md), protocol generator.

  python3 scripts/make_protocol_gd.py                   # candidates + pilot -> experiments/campaign_gd_{candidates,pilot_protocol}.json (+ the protocol if a selection exists)
  python3 scripts/make_protocol_gd.py --select FILE     # FILE = design fire masks of the candidates -> experiments/campaign_gd_selection.json

GC showed in the arena that a threshold calibrated on fire-free views of the site (0.01) lowers the closed-loop miss rate of the hard class at no false stop.  The paper says the threshold is per site:
in the depot the fire-free scores are about four times larger (the arena's value would stop 96 of 124 clean depot worlds, `scripts/calibration_sites.py`).  GD runs the recipe at the depot:
the threshold is the split-conformal rank rule at alpha = 2% over the 124 fire-free depot twins of XD (scored before GD), 0.0223, rounded up to the next thousandth = 0.023 (`experiments/gd_site_cal.json`).
72 candidates (seed `GD-2026`): a small partly hidden fire (the hard class of F, G, H, W, XD) at the only bay that holds the requested supply, the first 40 in id order whose design masks show the fire
(>= 614 px from the front or a side pose, no model score) are the fire worlds, 24 fire-free worlds measure false stops.  Arms: `v36` (orchestrator defaults, tau_h 0.05) and `cal` (`--site-config
experiments/gd_site_cal.json`) on every fire world, `cal` alone on the fire-free worlds.  Total 2 x (number selected) + 2 x 24 = 128 runs if 40 qualify (Amendment 1: `v36` also on the fire-free worlds).
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

SEED = 'GD-2026'
N_CANDIDATES, N_FIRE, N_PLAIN, N_CAL = 72, 40, 24, 100
VISIBLE_PX = mx.VISIBLE_PX                     # 614: the perceivable-fire rule of X, Y, GR and GC
CONFIG_V36 = []                                 # orchestrator defaults = v3.6 (tau_h 0.05)
CONFIG_CAL = ['--site-config', 'experiments/gd_site_cal.json']     # tau_h 0.023, h36, tiles: the rank rule at alpha = 2% over the 124 depot twins of XD, rounded up
ARMS = {'v36': CONFIG_V36, 'cal': CONFIG_CAL}
CONFIG_OPEN = ['--site-config', 'experiments/gd_site_open.json']       # Amendment 1: tau_h 1.0 (never refuses for a hazard), so every mission scores the front and both side views: the calibration runs
CALIBRATION = ROOT / 'experiments/campaign_gdk_protocol.json'
COMMON = ['--mission-timeout', str(mx.MISSION_TIMEOUT_S)]
CANDIDATES = ROOT / 'experiments/campaign_gd_candidates.json'
PILOT = ROOT / 'experiments/campaign_gd_pilot_protocol.json'
SELECTION = ROOT / 'experiments/campaign_gd_selection.json'
OUT = ROOT / 'experiments/campaign_gd_protocol.json'


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
    return [{'world': f'GD{i + 1:02d}', 'item': it, 'fire': True, 'world_spec': _spec(rng, it, True),
             'instruction': POOL[it][rng.randrange(len(POOL[it]))]} for i, it in enumerate(items)]


def plain_worlds() -> list:
    rng = random.Random(SEED + '-plain')
    items = ['water', 'medicine'] * (N_PLAIN // 2)
    rng.shuffle(items)
    return [{'world': f'GDP{i + 1:02d}', 'item': it, 'fire': False, 'world_spec': _spec(rng, it, False),
             'instruction': POOL[it][rng.randrange(len(POOL[it]))]} for i, it in enumerate(items)]


def calibration_worlds() -> list:
    """Amendment 1: 100 fire-free depot worlds of the GD generator (never part of GD), one mission each with the threshold off; their per-world maximum view score calibrates tau_h."""
    rng = random.Random(SEED + '-cal')
    items = ['water', 'medicine'] * (N_CAL // 2)
    rng.shuffle(items)
    return [{'world': f'GDK{i + 1:03d}', 'item': it, 'fire': False, 'world_spec': _spec(rng, it, False),
             'instruction': POOL[it][rng.randrange(len(POOL[it]))]} for i, it in enumerate(items)]


def calibration_protocol() -> dict:
    ts = []
    for n, w in enumerate(calibration_worlds(), 1):
        t = trial(w, 'open')
        t['id'], t['order'] = f'GDK{n:03d}', n
        ts.append(t)
    return {'schema': 'rescuemind_study_gd_calibration', 'seed': SEED + '-cal', 'planned_n': len(ts), 'common_stack_args': COMMON,
            'configs': {'open': 'v3.6 with --site-config experiments/gd_site_open.json (tau_h 1.0: no hazard refusal, all three views scored)'}, 'trials': ts}


def pilot_worlds() -> list:
    """Mechanics pilot (never part of GD): a fire world whose fire is large by construction (the big-fire geometry of X-a) and a fire-free world."""
    rng = random.Random(SEED + '-pilot')
    fire = {'world': 'GDQ1', 'item': 'water', 'fire': True, 'world_spec': _spec(rng, 'water', True, [0.9, 0.3, 1.0]), 'instruction': POOL['water'][0]}
    plain = {'world': 'GDQ2', 'item': 'medicine', 'fire': False, 'world_spec': _spec(rng, 'medicine', False), 'instruction': POOL['medicine'][0]}
    return [fire, plain]


def candidates_protocol() -> dict:
    ws = pilot_worlds()[:1] + fire_candidates()          # GDQ1's masks are rendered with the candidates (the pilot gate needs its front pixels)
    return {'schema': 'rescuemind_study_gd_candidates', 'seed': SEED, 'common_stack_args': COMMON,
            'rule': {'eligible': f'any of the front / left / right design masks >= {VISIBLE_PX} px', 'take': N_FIRE, 'order': 'id'},
            'trials': [{'id': w['world'], 'world': w['world'], 'scene': 'nominal', 'world_spec': w['world_spec'], 'order': n} for n, w in enumerate(ws, 1)]}


def trial(w: dict, arm: str) -> dict:
    return {'id': None, 'order': None, 'world': w['world'], 'config': arm, 'scene': 'nominal', 'expected': w['item'],
            'condition': 'fire_hidden' if w['fire'] else 'plain', 'instruction': w['instruction'], 'world_spec': w['world_spec'],
            'expected_action': 'DENY_HAZARD' if w['fire'] else 'ALLOW', 'stack_args': {**ARMS, 'open': CONFIG_OPEN}[arm]}


def pilot_protocol() -> dict:
    ts = [trial(pilot_worlds()[0], 'cal'), trial(pilot_worlds()[1], 'cal')]
    for n, t in enumerate(ts, 1):
        t['id'], t['order'] = f'GDPILOT{n}', n
    return {'schema': 'rescuemind_study_gd_pilot', 'seed': SEED, 'planned_n': len(ts), 'common_stack_args': COMMON, 'trials': ts}


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
    pilot = {k: px.get(k) for k in ('GDQ1', 'GDQ1L', 'GDQ1R')}
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
    for w in plain_worlds():                                  # Amendment 1: both arms on the fire-free worlds (the v36 run is the control for false stops)
        arms = list(ARMS)
        rng.shuffle(arms)
        blocks.append([trial(w, a) for a in arms])
    rng.shuffle(blocks)
    trials = [t for b in blocks for t in b]
    for n, t in enumerate(trials, 1):
        t['id'], t['order'] = f'GD{n:03d}', n
    return {'schema': 'rescuemind_study_gd_protocol', 'seed': SEED, 'status': 'REGISTERED_AT_COMMIT', 'planned_n': len(trials), 'common_stack_args': COMMON,
            'configs': {'v36': 'v3.6 (orchestrator defaults, tau_h 0.05)', 'cal': 'v3.6 with --site-config experiments/gd_site_cal.json (tau_h from scripts/gd_calibrate.py, h36, tiles)'},
            'worlds_from': 'experiments/campaign_gd_selection.json',
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
    if p['planned_n'] > 2 * N_PLAIN:
        write(p, OUT, force)
    print(p['planned_n'], 'trials')


if __name__ == '__main__':
    main()
