#!/usr/bin/env python3
"""Study GM (I-92): does the GL result (left-only 0.8 m look-around with the front + left threshold 0.028 against v3.6) transfer to depot worlds with one realism feature off? (experiments/PREREGISTRATION_GM.md), protocol generator.

  python3 scripts/make_protocol_gm.py                   # candidates + pilot (+ the protocol if a selection exists)
  python3 scripts/make_protocol_gm.py --select FILE     # FILE = design fire masks of the candidates -> experiments/campaign_gm_selection.json

Same generator and arms as GL (small partly hidden fire behind the only bay that holds the requested supply; `v36` and `left`, the threshold of `experiments/gl_site_cal.json`, NO recalibration), fresh worlds (seed `GM-2026`),
and each world has one realism feature of XD's ablation set switched off, in a fixed cycle by world number: default lighting, no clutter, no surroundings, plain platforms.  132 candidates; the first 100 in id order whose
design masks show the fire (>= 614 px, no model score) are the fire worlds; 32 fire-free worlds.  2 x 100 + 2 x 32 = 264 runs if 100 qualify.
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

SEED = 'GM-2026'
N_CANDIDATES, N_FIRE, N_PLAIN = 132, 100, 32
VISIBLE_PX = mx.VISIBLE_PX                     # 614: the perceivable-fire rule of X, Y, GR and GC
CONFIG_V36 = []                                 # orchestrator defaults = v3.6 (look-around 0.4 m both sides, tau_h 0.05)
CONFIG_LEFT = ['--look-around', '0.8', '--look-around-sides', 'L', '--site-config', 'experiments/gl_site_cal.json']   # left 0.8 m view only; tau_h 0.028 (rank rule, alpha = 2%, front/left maxima of the 100 GVK missions), h36, tiles
ARMS = {'v36': CONFIG_V36, 'left': CONFIG_LEFT}
CLEAN_ARMS = ('left', 'v36')                    # the fire-free worlds measure false stops of both arms
COMMON = ['--mission-timeout', str(mx.MISSION_TIMEOUT_S)]
CANDIDATES = ROOT / 'experiments/campaign_gm_candidates.json'
PILOT = ROOT / 'experiments/campaign_gm_pilot_protocol.json'
SELECTION = ROOT / 'experiments/campaign_gm_selection.json'
OUT = ROOT / 'experiments/campaign_gm_protocol.json'


VARIANTS = ('default_light', 'no_clutter', 'no_surroundings', 'plain_platforms')       # the realism features of XD's ablation worlds, one per world in a fixed cycle (index mod 4)


def variant_of(world: str) -> str | None:
    """GM001.. and GMP01.. cycle through VARIANTS by their number; the pilot worlds GMQ* have none."""
    digits = ''.join(ch for ch in world if ch.isdigit())
    return None if world.startswith('GMQ') or not digits else VARIANTS[(int(digits) - 1) % len(VARIANTS)]


def apply_variant(spec: dict, variant: str | None) -> dict:
    """One realism feature off, exactly as scripts/make_protocol_xd.ablation_world does it (applied after the world is drawn, so the random stream of the generator is the one of GL)."""
    if variant is None:
        return spec
    dep = spec['depot']
    if variant == 'default_light':
        spec.pop('lighting_params', None)             # Amendment 1: build_variant's own default lighting; the key spec['lighting'] = 'default' of XD's image builder is not a world_spec key of the orchestrator (exit 2)
    elif variant == 'no_clutter':
        dep['clutter'] = False
    elif variant == 'no_surroundings':
        dep['surroundings'] = False
    elif variant == 'plain_platforms':
        dep.pop('pallets', None)
    else:
        raise ValueError(variant)
    return spec


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
    return [{'world': f'GM{i + 1:03d}', 'item': it, 'fire': True, 'world_spec': apply_variant(_spec(rng, it, True), variant_of(f'GM{i + 1:03d}')),
             'instruction': POOL[it][rng.randrange(len(POOL[it]))]} for i, it in enumerate(items)]


def plain_worlds() -> list:
    rng = random.Random(SEED + '-plain')
    items = ['water', 'medicine'] * (N_PLAIN // 2)
    rng.shuffle(items)
    return [{'world': f'GMP{i + 1:02d}', 'item': it, 'fire': False, 'world_spec': apply_variant(_spec(rng, it, False), variant_of(f'GMP{i + 1:02d}')),
             'instruction': POOL[it][rng.randrange(len(POOL[it]))]} for i, it in enumerate(items)]


def pilot_worlds() -> list:
    """Mechanics pilot (never part of GL): a fire world whose fire is large by construction (the big-fire geometry of X-a) and a fire-free world."""
    rng = random.Random(SEED + '-pilot')
    fire = {'world': 'GMQ1', 'item': 'water', 'fire': True, 'world_spec': apply_variant(_spec(rng, 'water', True, [0.9, 0.3, 1.0]), 'plain_platforms'), 'instruction': POOL['water'][0]}
    plain = {'world': 'GMQ2', 'item': 'medicine', 'fire': False, 'world_spec': apply_variant(_spec(rng, 'medicine', False), 'no_surroundings'), 'instruction': POOL['medicine'][0]}
    return [fire, plain]


def candidates_protocol() -> dict:
    ws = pilot_worlds()[:1] + fire_candidates()          # GLQ1's masks are rendered with the candidates (the pilot gate needs its front pixels)
    return {'schema': 'rescuemind_study_gm_candidates', 'seed': SEED, 'common_stack_args': COMMON,
            'rule': {'eligible': f'any of the front / left / right design masks >= {VISIBLE_PX} px', 'take': N_FIRE, 'order': 'id'},
            'trials': [{'id': w['world'], 'world': w['world'], 'scene': 'nominal', 'world_spec': w['world_spec'], 'order': n} for n, w in enumerate(ws, 1)]}


def trial(w: dict, arm: str) -> dict:
    return {'id': None, 'order': None, 'world': w['world'], 'config': arm, 'scene': 'nominal', 'expected': w['item'],
            'condition': 'fire_hidden' if w['fire'] else 'plain', 'instruction': w['instruction'], 'world_spec': w['world_spec'],
            'expected_action': 'DENY_HAZARD' if w['fire'] else 'ALLOW', 'stack_args': ARMS[arm]}


def pilot_protocol() -> dict:
    ts = [trial(pilot_worlds()[0], 'left'), trial(pilot_worlds()[1], 'left')]
    for n, t in enumerate(ts, 1):
        t['id'], t['order'] = f'GMPILOT{n}', n
    return {'schema': 'rescuemind_study_gm_pilot', 'seed': SEED, 'planned_n': len(ts), 'common_stack_args': COMMON, 'trials': ts}


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
    pilot = {k: px.get(k) for k in ('GMQ1', 'GLQ1L', 'GLQ1R')}
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
    for w in plain_worlds():                                  # the fire-free worlds: both arms
        arms = list(CLEAN_ARMS)
        rng.shuffle(arms)
        blocks.append([trial(w, a) for a in arms])
    rng.shuffle(blocks)
    trials = [t for b in blocks for t in b]
    for n, t in enumerate(trials, 1):
        t['id'], t['order'] = f'GMT{n:03d}', n
    return {'schema': 'rescuemind_study_gm_protocol', 'seed': SEED, 'status': 'REGISTERED_AT_COMMIT', 'planned_n': len(trials), 'common_stack_args': COMMON,
            'configs': {'v36': 'v3.6 (orchestrator defaults, look-around 0.4 m both sides, tau_h 0.05)', 'left': 'v3.6 with --look-around 0.8 --look-around-sides L and --site-config experiments/gl_site_cal.json (tau_h 0.028, h36, tiles)'},
            'worlds_from': 'experiments/campaign_gm_selection.json',
            'gm': {'candidates': len(cands), 'selected': sel, 'plain': [w['world'] for w in plain_worlds()]}, 'trials': trials}


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
    p = build(json.loads(SELECTION.read_text()) if SELECTION.is_file() else None)
    if p['planned_n'] > len(CLEAN_ARMS) * N_PLAIN:
        write(p, OUT, force)
    print(p['planned_n'], 'trials')


if __name__ == '__main__':
    main()
