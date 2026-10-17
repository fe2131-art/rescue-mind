#!/usr/bin/env python3
"""Study Q label audit: contact sheets of the candidate photographs, for a HUMAN check before any inference.

  python3 scripts/q_contact_sheet.py [--cols 6 --rows 5] [--unaudited]

Writes ~/.cache/rescuemind/q/sheets/<class>__<type>__<k>.jpg (outside the repository).  Each tile shows the image id.
The reviewer lists the ids that break the class definition in experiments/q_exclusions.json (format below) and freezes the file
(its sha256 is written into q_sample_final.json) before q_eval.py --run.  The audit never sees a model output.

  {"criteria_version": 1, "reviewer": "...", "audited": [every id that was looked at], "excluded": [{"id": 12345, "reason": "W4 ..."}, ...]}

--unaudited draws sheets only for candidates that are not yet in "audited" (a later audit round).

Needs only Pillow.  If no TrueType font is installed Pillow's built-in bitmap font is used; if even that fails the script exits
with a message instead of writing unlabeled sheets.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path.home() / '.cache/rescuemind/q'
TILE_W, TILE_H, LABEL_H = 230, 172, 18


def font():
    from PIL import ImageFont
    for name in ('DejaVuSans.ttf', 'LiberationSans-Regular.ttf', 'Arial.ttf'):
        try:
            return ImageFont.truetype(name, 13)
        except OSError:
            pass
    try:
        return ImageFont.load_default(13)
    except Exception:
        return None


def sheets(images: list, cols: int, rows: int, out: Path):
    from PIL import Image, ImageDraw, ImageOps
    f = font()
    if f is None:
        sys.exit('no usable font: cannot label the tiles, not writing sheets')
    out.mkdir(parents=True, exist_ok=True)
    groups = {}
    for r in images:
        groups.setdefault((r['class'], r['type']), []).append(r)
    written = []
    for (cls, typ), rs in sorted(groups.items()):
        rs = sorted(rs, key=lambda r: r['id'])
        per = cols * rows
        for k in range(0, len(rs), per):
            sheet = Image.new('RGB', (cols * TILE_W, rows * (TILE_H + LABEL_H)), 'white')
            d = ImageDraw.Draw(sheet)
            for j, r in enumerate(rs[k:k + per]):
                x, y = (j % cols) * TILE_W, (j // cols) * (TILE_H + LABEL_H)
                try:
                    with Image.open(CACHE / 'images' / r['file']) as im:
                        tile = ImageOps.fit(ImageOps.exif_transpose(im).convert('RGB'), (TILE_W - 4, TILE_H - 2))
                    sheet.paste(tile, (x + 2, y + 1))
                except OSError:
                    d.text((x + 6, y + 6), 'unreadable', fill='red', font=f)
                d.text((x + 4, y + TILE_H), f'{r["id"]}', fill='black', font=f)
            p = out / f'{cls}__{typ}__{k // per + 1}.jpg'
            sheet.save(p, quality=85)
            written.append(p)
    return written


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cols', type=int, default=6); ap.add_argument('--rows', type=int, default=5)
    ap.add_argument('--unaudited', action='store_true')
    a = ap.parse_args()
    images = json.loads((ROOT / 'experiments/q_sample.json').read_text())['images']
    images = [r for r in images if r.get('file') and (CACHE / 'images' / r['file']).is_file()]
    if a.unaudited:
        done = set(json.loads((ROOT / 'experiments/q_exclusions.json').read_text()).get('audited', []))
        images = [r for r in images if r['id'] not in done]
    w = sheets(images, a.cols, a.rows, CACHE / ('sheets_new' if a.unaudited else 'sheets'))
    print(len(w), 'sheets written')


if __name__ == '__main__':
    main()
