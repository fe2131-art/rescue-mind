#!/usr/bin/env python3
"""Study JI (I-94; experiments/PREREGISTRATION_JI.md): a fresh image set for the post hoc findings of the JH factor analysis (I-93): do more views, and a second judge on top of them, remove the hard class's last misses?

  python3 scripts/make_protocol_ji.py            # -> experiments/campaign_ji_protocol.json  (seed JI-2026)
It is the XD generator (scripts/make_protocol_xd.py) with another seed and only the hard class: 120 worlds with a small partly hidden fire behind the checked bay ('tongues_small', the geometry of F, G, H, W, XD)
and, for every one of them, its fire-free twin (same world, no fire) = 120 clean worlds; every world gets the six views F, L, R (0.4 m), L2, R2 (0.8 m), N (0.3 m closer).  No ablation copies (the clustering of XD's
test set was the first finding of I-93), no calibration split (every world is a test world; the thresholds are frozen from XD), no lookalikes, no other class.  240 worlds x 6 views = 1440 images.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
import make_protocol_xd as mx  # noqa: E402

OUT = ROOT / 'experiments/campaign_ji_protocol.json'


def build() -> dict:
    keep = {k: getattr(mx, k) for k in ('SEED', 'CLASSES', 'HAZARD_CLASSES', 'TWIN_EVERY', 'CAL_FRACTION', 'ABLATION_N', 'N_LOOKALIKE_OK', 'N_LOOKALIKE_EMPTY')}
    try:
        mx.SEED, mx.CLASSES, mx.HAZARD_CLASSES = 'JI-2026', {'tongues_small': 120}, ('tongues_small',)
        mx.TWIN_EVERY, mx.CAL_FRACTION, mx.ABLATION_N, mx.N_LOOKALIKE_OK, mx.N_LOOKALIKE_EMPTY = 1, 0.0, 0, 0, 0
        proto = mx.build()
    finally:
        for k, v in keep.items():
            setattr(mx, k, v)
    for w in proto['worlds']:
        w['id'] = 'ji' + w['id'][2:]
        if w.get('twin_of'):
            w['twin_of'] = 'ji' + w['twin_of'][2:]
    proto['schema'], proto['status'] = 'rescuemind_study_ji_protocol', 'REGISTERED_AT_COMMIT'
    proto['views_all'] = list(mx.VIEWS) + list(mx.VIEWS_EXTRA)
    proto['n_images'] = 6 * len(proto['worlds'])
    return proto


def main(argv=None):
    force = '--force' in (argv if argv is not None else sys.argv[1:])
    proto = build()
    new = json.loads(json.dumps(proto, ensure_ascii=False))
    if OUT.is_file() and json.loads(OUT.read_text()) != new and not force:
        sys.exit('registered protocol differs from the generator output; refusing to overwrite (--force while it is a draft)')
    OUT.write_text(json.dumps(new, ensure_ascii=False, indent=1) + '\n')
    print(len(proto['worlds']), 'worlds', proto['n_images'], 'images;', proto['class_counts'])


if __name__ == '__main__':
    main()
