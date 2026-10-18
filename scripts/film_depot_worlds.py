#!/usr/bin/env python3
"""Worlds and run classification for the filmed depot missions of the final video (segment 6; scripts/film_depot.sh).

  python3 scripts/film_depot_worlds.py --write      # regenerate experiments/film_depot_worlds.json
  python3 scripts/film_depot_worlds.py --show TAG   # TAG: search | fire1 | fire2 | fire3  ->  {"instruction", "world_spec"} as JSON
  python3 scripts/film_depot_worlds.py --classify outputs/runs/<id>   # what the filmed run shows

These worlds are NOT trial worlds of study X, XD or the X pilot: they are drawn from their own seed (FILM-DEPOT-2026) with the
generator helpers of scripts/make_protocol_x.py, so filming them cannot be mistaken for running (or previewing) a registered trial.
The frozen specs are committed in experiments/film_depot_worlds.json (a unit test checks they equal this generator and share no
depot seed, lighting or request with the X / XD protocols).

  search  the first water bay W1 holds medicine (a swapped supply), W2 holds water: the robot checks W1, refuses, checks W2, delivers.
  fire1..3  one small, partly hidden fire (the hard class of studies F / G / W / A) behind W1 with a moving smoke plume, the
          requested water stands at W1; three candidate worlds (different geometry and clutter).  The film script tries them in
          order until a run shows the intended event (front check approves, a side view finds the fire -> stop); a world is only
          a candidate: nobody knows beforehand whether the front camera sees this fire (that is what the side view is for).
"""
from __future__ import annotations
import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import make_protocol_x as mpx  # noqa: E402

SEED = 'FILM-DEPOT-2026'
OUT = ROOT / 'experiments/film_depot_worlds.json'
N_FIRE_CANDIDATES = 3


def japanese(item: str) -> list:
    """The video is in Japanese: only the Japanese requests of the pool."""
    return [x for x in mpx.POOL[item] if any(ord(c) > 127 for c in x)]


def build() -> dict:
    rng = random.Random(SEED)
    worlds = {}
    # search: swapped first bay, the supply at the second one
    sup = mpx.natural('water', 'W2')
    sup['W1'] = 'medicine'
    spec = mpx.base_spec(rng, sup, rng.randrange(10 ** 6), False)
    worlds['search'] = {'kind': 'search_deliver', 'item': 'water',
                        'instruction': japanese('water')[rng.randrange(len(japanese('water')))], 'world_spec': spec}
    # fire candidates: the requested supply at the first bay, a small hidden fire behind it, particle smoke on
    for i in range(1, N_FIRE_CANDIDATES + 1):
        item = 'water'
        sup = mpx.natural(item, 'W1')
        spec = mpx.base_spec(rng, sup, rng.randrange(10 ** 6), rng.random() < 0.25)
        spec['hazard_at'] = 'W1'
        spec['hazard_geom'] = mpx.small_geometry(rng)
        spec['depot']['particle_smoke'] = True
        worlds[f'fire{i}'] = {'kind': 'side_fire', 'item': item,
                              'instruction': japanese(item)[rng.randrange(len(japanese(item)))], 'world_spec': spec}
    return {'schema': 'rescuemind_film_depot_worlds', 'seed': SEED,
            'note': 'filming only; not a trial world of study X / XD / the X pilot (own seed); see scripts/film_depot_worlds.py',
            'worlds': worlds}


def load() -> dict:
    return json.loads(OUT.read_text(encoding='utf8'))


def classify(run_dir) -> dict:
    """What a filmed run shows, from its own record (mission.json + stack_result.json)."""
    run_dir = Path(run_dir)
    m = json.loads((run_dir / 'mission.json').read_text(encoding='utf8'))
    s = json.loads((run_dir / 'stack_result.json').read_text(encoding='utf8'))
    dec = (m.get('checkpoint') or {}).get('decision') or {}
    peeks = (m.get('look_around') or {}).get('peeks') or []
    side_hazard = [p['side'] for p in peeks if p.get('hazard')] or list(dec.get('look_around_hazard_sides') or [])
    searched = bool(m.get('recovery'))
    state = s.get('state')
    if side_hazard and dec.get('front_reason') and not dec.get('allow'):
        kind = 'side_fire'            # the front check approved, a side view found the fire, the approval was revoked
    elif not dec.get('allow') and dec.get('reason') == 'visible_hazard_at_checkpoint':
        kind = 'front_fire'           # seen from the front already (still a stop, but not the intended event)
    elif searched and dec.get('allow') and state in ('COMPLETED', 'COMPLETED_EXPECTED_DELIVERY'):
        kind = 'search_deliver'
    elif dec.get('allow') and state == 'COMPLETED':
        kind = 'delivery'
    else:
        kind = 'other'
    return {'kind': kind, 'state': state, 'searched': searched, 'side_hazard': side_hazard,
            'first_station': (m.get('recovery') or {}).get('first_station'), 'station': m.get('checkpoint_station')}


def build_world(tag: str, dest_dir) -> Path:
    """Write the Gazebo world of one film world exactly as scripts/v32_orchestrate.py does (offline; no Gazebo) and validate it."""
    from rescuemind.robust_scenes import write_variant
    from rescuemind.gazebo_transport_contract import validate_static
    kw = dict(load()['worlds'][tag]['world_spec'])
    if 'hazard_geom' in kw:
        kw['hazard_geom'] = tuple(kw['hazard_geom'])
    w = write_variant(ROOT / 'worlds/scenarios', Path(dest_dir), 'nominal', **kw)
    validate_static(w, ROOT / 'configs/ros_gz_bridge_v20.yaml')
    return w


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--write', action='store_true')
    g.add_argument('--show', metavar='TAG')
    g.add_argument('--tags', action='store_true', help='print the tags, one per line')
    g.add_argument('--classify', metavar='RUN_DIR')
    g.add_argument('--check', metavar='DIR', help='regenerate and compare the frozen file, then build and validate every world into DIR')
    a = ap.parse_args(argv)
    if a.write:
        OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf8')
        print(OUT)
    elif a.tags:
        print('\n'.join(load()['worlds']))
    elif a.check:
        if load() != json.loads(json.dumps(build())):
            sys.exit('FILM_WORLDS_STALE: experiments/film_depot_worlds.json differs from the generator (run --write and review)')
        from rescuemind import depot
        problems = depot.check_k4_layout()
        if problems:
            sys.exit('k=4 layout problems: ' + '; '.join(problems))
        Path(a.check).mkdir(parents=True, exist_ok=True)
        for tag in load()['worlds']:
            print(tag, build_world(tag, Path(a.check) / tag).name)
    elif a.show:
        w = load()['worlds'][a.show]
        print(json.dumps({'instruction': w['instruction'], 'world_spec': w['world_spec']}, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(classify(a.classify), ensure_ascii=False))


if __name__ == '__main__':
    main()
