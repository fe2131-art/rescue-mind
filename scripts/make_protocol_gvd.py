#!/usr/bin/env python3
"""Development pass GVD (I-70): closed-loop fire scores at 0.8 m, on the 40 fire worlds of GD (not a study, never claimed).

GV stopped at its calibration and never ran a fire world, so nothing is known about how the 0.8 m views score the hard fires in closed loop.  The image-level estimate for a front + left-0.8 m
arm (I-62) comes from XD's teleported images, which did not transfer to the closed loop once before (XD -> GV).  GVD runs ONE mission per GD fire world with the wide views and the threshold off
(`experiments/gv_site_open.json`: every view is scored), so that the front + left 0.8 m scores of the same worlds can be set against GD's `v36` and `cal` outcomes.  Development data:
a later registration discloses it, as GV disclosed XD.

  python3 scripts/make_protocol_gvd.py        # -> experiments/campaign_gvd_protocol.json
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import make_protocol_gd as mgd  # noqa: E402

OUT = ROOT / 'experiments/campaign_gvd_protocol.json'
CONFIG = ['--look-around', '0.8', '--site-config', 'experiments/gv_site_open.json']     # the GVK calibration configuration: tau_h 1.0, all views scored


def build() -> dict:
    sel = json.loads(mgd.SELECTION.read_text())['selected']
    cands = {c['world']: c for c in mgd.fire_candidates()}
    ts = []
    for n, w in enumerate(sel, 1):
        t = mgd.trial(cands[w], 'open')
        t['stack_args'] = CONFIG
        t['id'], t['order'] = f'GVD{n:03d}', n
        t['gd_world'] = w
        ts.append(t)
    return {'schema': 'rescuemind_study_gvd_development', 'seed': mgd.SEED, 'planned_n': len(ts), 'common_stack_args': mgd.COMMON,
            'configs': {'open': 'v3.6 with --look-around 0.8 and --site-config experiments/gv_site_open.json (tau_h 1.0: no hazard refusal, all views scored); development, not claimed'},
            'worlds_from': 'experiments/campaign_gd_selection.json', 'trials': ts}


def main():
    p = build()
    OUT.write_text(json.dumps(p, ensure_ascii=False, indent=1) + '\n')
    print(p['planned_n'], 'trials ->', OUT.name)


if __name__ == '__main__':
    main()
