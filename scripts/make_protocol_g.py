#!/usr/bin/env python3
"""Campaign G: paired closed-loop test of the I-14 look-around on NEW worlds (built before running).

Same world distribution as campaign F (24 worlds: 12 small fires straight behind the requested station,
8 fire-free, 4 fires behind the other station) but a fresh seed, because F's worlds were used to design I-14.
Each world is run with B (v3.5 + h36 wording + crops, campaign F's configuration B) and C (B + look-around 0.4 m),
order alternating BC/CB.  World-level fire label: magenta-mask pixels at the canonical front checkpoint pose and at
the two side poses (scripts/fire_mask_at_pose.py --design-sides), fixed before any trial.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.make_protocol_f import COMMON, worlds  # noqa: E402

SEED = 'G-2026'
CONFIG_B = ['--hazard-prompt', 'h36', '--hazard-views', 'tiles']
CONFIG_C = CONFIG_B + ['--look-around', '0.4']


def build():
    trials, order = [], 0
    for k, w in enumerate(worlds(SEED)):
        pair = ('B', 'C') if k % 2 == 0 else ('C', 'B')
        for cfg in pair:
            order += 1
            exp = {'plain': 'ALLOW', 'fire_hidden': 'DENY_HAZARD', 'fire_hidden_other': 'DENY_HAZARD_AFTER_SEARCH'}[w['condition']]
            trials.append({'id': f'G{order:03d}', 'order': order, 'world': w['world'], 'config': cfg, 'scene': w['scene'],
                           'expected': w['expected'], 'condition': w['condition'], 'instruction': w['instruction'],
                           'world_spec': w['world_spec'], 'expected_action': exp,
                           'stack_args': CONFIG_B if cfg == 'B' else CONFIG_C})
    return {'schema': 'rescuemind_campaign_g_protocol', 'seed': SEED, 'planned_n': len(trials),
            'common_stack_args': COMMON, 'configs': {'B': CONFIG_B, 'C': CONFIG_C}, 'trials': trials}


def main():
    out = ROOT / 'experiments/campaign_g_protocol.json'
    proto = build()
    if out.is_file() and json.loads(out.read_text()) != json.loads(json.dumps(proto, ensure_ascii=False)):
        sys.exit('registered protocol differs; refusing to overwrite')
    out.write_text(json.dumps(proto, ensure_ascii=False, indent=1) + '\n')
    print(proto['planned_n'], 'trials')


if __name__ == '__main__':
    main()
