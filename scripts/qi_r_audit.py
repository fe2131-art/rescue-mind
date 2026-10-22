#!/usr/bin/env python3
"""Study QI, Amendment 3 (descriptive): did the photo-realising generator keep the fire?  Without this, a higher QI1 miss cannot be told apart from an erased fire.

  python3 scripts/qi_r_audit.py        # experiments/results/qi_r_audit.json
For every realised (R) image of an XD fire world that has a design fire render (`fire_masks/<world>_<view>.png`; fire pixels = magenta key colour), the share of that region that is
flame-coloured before and after the edit and the mean absolute change inside it.  `kept` = the realised share is at least half the original share (pixels only, no gate score).
The list of realised WORLDS that the gate misses (`qi_summary.json`) is joined to this by `scripts/qi_analysis.py` readers; each missed world is also looked at by eye (recorded in FINDINGS).
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from qi_generate import BASE, OUT, RES, fire_colour_fraction, fire_pixels_of  # noqa: E402


def main():
    rows = []
    for line in (RES / 'qi_manifest_R.jsonl').read_text(encoding='utf8').splitlines():
        m = json.loads(line)
        mask_f = BASE / 'fire_masks' / f"{m['world']}_{m['view']}.png"
        if not mask_f.is_file():
            continue
        region = fire_pixels_of(np.asarray(Image.open(mask_f).convert('RGB')))
        if region.sum() < 50:
            continue
        a = np.asarray(Image.open(BASE / m['src']).convert('RGB'))
        b = np.asarray(Image.open(OUT / 'R' / (m['key'].replace('/', '_').rsplit('.', 1)[0] + '.jpg')).convert('RGB'))
        before, after = fire_colour_fraction(a, region), fire_colour_fraction(b, region)
        from scipy.ndimage import binary_dilation
        ring = binary_dilation(region, iterations=15) & ~binary_dilation(region, iterations=2)
        lum = lambda im: im.astype(float) @ np.array([0.299, 0.587, 0.114])
        c0, c1 = float(lum(a)[region].mean() - lum(a)[ring].mean()), float(lum(b)[region].mean() - lum(b)[ring].mean())
        kept = bool(after >= 0.5 * before) if before > 0.02 else bool(c0 * c1 > 0 and abs(c1) >= 0.5 * abs(c0))
        rows.append({'key': m['key'], 'world': m['world'], 'view': m['view'], 'region_px': int(region.sum()), 'flame_share_before': round(before, 3), 'flame_share_after': round(after, 3),
                     'mean_abs_change_in_region': round(float(np.abs(a.astype(int) - b.astype(int))[region].mean()), 1), 'contrast_before': round(c0, 1), 'contrast_after': round(c1, 1), 'kept': kept})
    out = {'n_images': len(rows), 'n_kept': sum(r['kept'] for r in rows), 'rows': rows}
    (RES / 'qi_r_audit.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    print(out['n_images'], 'fire images with a design render,', out['n_kept'], 'kept the flame colour')


if __name__ == '__main__':
    sys.exit(main())
