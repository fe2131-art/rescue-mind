#!/usr/bin/env python3
"""Study JK (I-107): suspicion-triggered extra views (I-20: L2, R2 at 0.8 m and N 0.3 m closer, triggered when a standard view scores >= 0.005) in the closed loop at the depot, on the worlds of study GM
(experiments/PREREGISTRATION_JK.md).

  python3 scripts/make_protocol_jk.py          # pilot + protocol (the worlds and their selection are GM's: experiments/campaign_gm_selection.json)

One new arm, `adapt` = the submitted v3.6 plus `--adaptive-views 0.8` (tau_h 0.05, tau_sus 0.005, near 0.3: defaults), on the 100 fire worlds and the 32 fire-free worlds of GM, 132 runs.  The comparators
`v36` and `left` are GM's own runs of the same worlds (campaign_GM_ledger.jsonl, final rows): the pairing is by world, NOT concurrent (disclosed in the registration).
"""
from __future__ import annotations
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import make_protocol_gm as mg  # noqa: E402
from scripts.make_protocol_v34 import POOL  # noqa: E402

SEED = 'JK-2026'
ADAPT = ['--adaptive-views', '0.8']                           # tau_sus 0.005 and near 0.3 keep their defaults (I-20)
ADAPT_FORCED = ['--adaptive-views', '0.8', '--adaptive-tau-sus', '0']      # pilot only: the extra views are forced so that the poses are exercised
ARMS = {'adapt': ADAPT}
COMMON = mg.COMMON
PILOT = ROOT / 'experiments/campaign_jk_pilot_protocol.json'
OUT = ROOT / 'experiments/campaign_jk_protocol.json'
SELECTION = mg.SELECTION


def pilot_worlds() -> list:
    """Never part of JK: GM's two pilot worlds (a large fire; a fire-free world) and one more fire-free world (the pilot worlds of GM are not GM worlds either)."""
    ws = mg.pilot_worlds()
    rng = random.Random(SEED + '-pilot3')
    ws.append({'world': 'JKQ3', 'item': 'water', 'fire': False, 'world_spec': mg.apply_variant(mg._spec(rng, 'water', False), 'default_light'), 'instruction': POOL['water'][0]})
    return ws


def trial(w: dict, arm: str, args: list) -> dict:
    return {'id': None, 'order': None, 'world': w['world'], 'config': arm, 'scene': 'nominal', 'expected': w['item'], 'condition': 'fire_hidden' if w['fire'] else 'plain',
            'instruction': w['instruction'], 'world_spec': w['world_spec'], 'expected_action': 'DENY_HAZARD' if w['fire'] else 'ALLOW', 'stack_args': args}


def pilot_protocol() -> dict:
    q1, q2, q3 = pilot_worlds()
    ts = [trial(q1, 'adapt', ADAPT), trial(q2, 'adapt_forced', ADAPT_FORCED), trial(q3, 'adapt_forced', ADAPT_FORCED)]
    for n, t in enumerate(ts, 1):
        t['id'], t['order'] = f'JKPILOT{n}', n
    return {'schema': 'rescuemind_study_jk_pilot', 'seed': SEED, 'planned_n': len(ts), 'common_stack_args': COMMON, 'trials': ts}


def build(selection: dict) -> dict:
    cands = {c['world']: c for c in mg.fire_candidates()}
    sel = selection['selected']
    rng = random.Random(SEED + '-order')
    ws = [cands[x] for x in sel] + mg.plain_worlds()
    rng.shuffle(ws)
    trials = [trial(w, 'adapt', ADAPT) for w in ws]
    for n, t in enumerate(trials, 1):
        t['id'], t['order'] = f'JKT{n:03d}', n
    return {'schema': 'rescuemind_study_jk_protocol', 'seed': SEED, 'status': 'REGISTERED_AT_COMMIT', 'planned_n': len(trials), 'common_stack_args': COMMON,
            'configs': {'adapt': 'v3.6 (look-around 0.4 m both sides, tau_h 0.05) plus --adaptive-views 0.8 (tau_sus 0.005, near 0.3: the I-20 defaults)'},
            'worlds_from': 'experiments/campaign_gm_selection.json (the worlds and world specs of study GM)', 'trials': trials}


def write(proto: dict, out: Path, force: bool) -> None:
    new = json.loads(json.dumps(proto, ensure_ascii=False))
    if out.is_file() and json.loads(out.read_text()) != new and not force:
        sys.exit(f'registered protocol {out.name} differs from the generator output; refusing to overwrite (--force while it is a draft)')
    out.write_text(json.dumps(new, ensure_ascii=False, indent=1) + '\n')


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    force = '--force' in argv
    write(pilot_protocol(), PILOT, force)
    p = build(json.loads(SELECTION.read_text()))
    write(p, OUT, force)
    print(p['planned_n'], 'trials')


if __name__ == '__main__':
    main()
