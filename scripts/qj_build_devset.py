#!/usr/bin/env python3
"""Study QJ (I-90): assemble the text-to-image scenes into devsets of the format of scripts/vlm_devset_eval.py (the frozen gate scores them unchanged).

  python3 scripts/qj_build_devset.py     # outputs/qj/devset_{N0,NF,NB}/ from experiments/results/qj_manifest_*.jsonl; `qj_audit.json` = the pixel audit (no gate score)
Pixel audit (registered, from pixels only): a fire image (NF, NB) is AUDITED-IN when its flame-coloured share of the whole frame is at least FLAME_MIN; the others stay in the audit table and out of the miss claims.
A clean image (N0) is never excluded.  FLAME_MIN is fixed in PREREGISTRATION_QJ.md before the main generation.
"""
from __future__ import annotations
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/qj'
RES = ROOT / 'experiments/results'
FLAME_MIN = 0.002          # share of flame-coloured pixels of the whole frame (placeholder until the pilot fixes it; see PREREGISTRATION_QJ.md)


def label(mode: str, m: dict) -> dict:
    fire = mode != 'N0'
    return {'image': f"images/{m['key']}.jpg", 'world_id': m['world'] + '_' + mode, 'world_kind': 'hazard' if fire else 'twin', 'cls': mode, 'split': 'test', 'view': 'F',
            'station': m['item'], 'truth_supply': m['item'], 'truth_hazard_visible': fire, 'qj_key': m['key'], 'qj_mode': mode, 'qj_item': m['item'], 'qj_light': m['light'], 'flame_share': m['flame_share']}


def main():
    audit = {}
    for mode in ('N0', 'NF', 'NB'):
        mf = RES / f'qj_manifest_{mode}.jsonl'
        if not mf.is_file():
            continue
        d = OUT / f'devset_{mode}'
        (d / 'images').mkdir(parents=True, exist_ok=True)
        rows = []
        for line in mf.read_text(encoding='utf8').splitlines():
            m = json.loads(line)
            shutil.copyfile(OUT / mode / f"{m['key']}.jpg", d / f"images/{m['key']}.jpg")            # every image is scored; the audit decides which count in the claims
            rows.append(label(mode, m))
        (d / 'labels.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf8')
        audit[mode] = {'n': len(rows), 'flame_min': FLAME_MIN, 'n_flame': sum(r['flame_share'] >= FLAME_MIN for r in rows) if mode != 'N0' else None,
                       'flame_share_by_key': {r['qj_key']: r['flame_share'] for r in rows}}
        print(mode, len(rows), 'images', audit[mode]['n_flame'], 'with flame colour')
    (RES / 'qj_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=1) + '\n')


if __name__ == '__main__':
    sys.exit(main())
