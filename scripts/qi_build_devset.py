#!/usr/bin/env python3
"""Study QI (I-82): assemble the generated images into XD-format devsets so that the FROZEN scoring path of XD (scripts/vlm_devset_eval.py, v3.6 = h36 + tiles, both passes) scores them unchanged.

  python3 scripts/qi_build_devset.py            # outputs/qi/devset_{R,G,C}/ (labels.jsonl + images/) from the manifests in experiments/results/qi_manifest_*.jsonl
Labels: R keeps the XD label of the source image; G carries the label of the FIRE world (truth_hazard_visible, class) on the generated image of its clean twin; C carries the twin's own (clean) label.
Images whose pixel check failed (G: flame-coloured share of the fire mask below FIRE_MIN, or pixels outside the mask changed; C: pixels outside the mask changed; R has no pixel check: the simulator's own fires are not flame-coloured, median share 0 for small tongues) are NOT scored: they go to qi_excluded.json with the reason.
"""
from __future__ import annotations
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'experiments/vlm_testset_xd'
OUT = ROOT / 'outputs/qi'
RES = ROOT / 'experiments/results'
FIRE_MIN = 0.02            # G: at least 2% of the fire mask's pixels must be flame-coloured after the edit (an edit with none did not draw a fire); set before any generated image was seen, may be refit on the pilot only (PREREGISTRATION_QI)


def keep(mode: str, m: dict) -> str | None:
    """None = keep; otherwise the reason for the exclusion (decided from pixels only, never from a gate score)."""
    qc = m['qc']
    if mode in ('G', 'G2'):
        if not qc['outside_unchanged']:
            return 'pixels outside the mask changed'
        if qc['fire_colour_in_mask'] < FIRE_MIN:
            return f"flame colour in the mask {qc['fire_colour_in_mask']} < {FIRE_MIN}"
    if mode in ('C', 'K1', 'K2') and not qc['outside_unchanged']:
        return 'pixels outside the mask changed'
    return None


def main():
    labels = {json.loads(x)['image']: json.loads(x) for x in (BASE / 'labels.jsonl').read_text(encoding='utf8').splitlines() if x.strip()}
    byw = {(r['world_id'], r['view']): r for r in labels.values()}
    excluded = {}
    for mode in ('R', 'G', 'C', 'G2', 'K1', 'K2'):
        mf = RES / f'qi_manifest_{mode}.jsonl'
        if not mf.is_file():
            continue
        d = OUT / f'devset_{mode}'
        (d / 'images').mkdir(parents=True, exist_ok=True)
        rows = []
        for line in mf.read_text(encoding='utf8').splitlines():
            m = json.loads(line)
            why = keep(mode, m)
            if why:
                excluded.setdefault(mode, []).append({'key': m['key'], 'reason': why})
                continue
            src = OUT / mode / (m['key'].replace('/', '_').rsplit('.', 1)[0] + '.jpg')
            r = dict(labels[m['src']] if mode in ('R', 'C', 'K1', 'K2') else byw[(m['fire_world'], m['view'])])
            name = f"images/{m['key'].replace('/', '_').rsplit('.', 1)[0]}.jpg"
            shutil.copyfile(src, d / name)
            r['image'], r['qi_key'], r['qi_mode'] = name, m['key'], mode
            if mode != 'R':
                r['world_id'] = m['fire_world'] + '_gen' if mode in ('G', 'G2') else m['world']            # G: the generated fire world (id of the fire world + _gen); C: the clean twin
            rows.append(r)
        (d / 'labels.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf8')
        print(mode, len(rows), 'images,', len(excluded.get(mode, [])), 'excluded')
    (RES / 'qi_excluded.json').write_text(json.dumps(excluded, ensure_ascii=False, indent=1) + '\n')


if __name__ == '__main__':
    sys.exit(main())
