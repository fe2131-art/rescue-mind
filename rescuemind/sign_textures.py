"""Study S: PNG textures for scene-text signs (physical prompt injection tests).

One sign = white background, black bold text (one line per '\\n'), thin black border.  Every sign type uses the SAME style,
so only the words differ between an attack sign and the benign control.  Rendered with PIL and a Noto Sans CJK font (the
rm-dev / rm-next images have it; the plain host may not, in which case a CJK text raises FontMissing).

The orientation of a texture on a Gazebo box face depends on the renderer's UV layout.  `RESCUEMIND_SIGN_TEXTURE_TRANSFORM`
(none | fliplr | flipud | rot180) corrects it without touching any other code; scripts/build_testset_s.py --sign-check renders
a probe so that the right value can be read off a screenshot before the first study image is rendered.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path

FONT_BOLD = ('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
             '/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc',
             '/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc',
             '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
FONT_LATIN_FALLBACK = ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',)
TRANSFORMS = ('none', 'fliplr', 'flipud', 'rot180')
PX_PER_M = 1000          # texture resolution; a 0.44 x 0.34 m sign is 440 x 340 px


class FontMissing(RuntimeError):
    pass


def has_cjk(text: str) -> bool:
    return any(ord(c) > 0x2E80 for c in text)


def find_font(text: str = '') -> str:
    for p in FONT_BOLD:
        if os.path.isfile(p):
            return p
    if not has_cjk(text):
        for p in FONT_LATIN_FALLBACK:
            if os.path.isfile(p):
                return p
    raise FontMissing('no Noto Sans CJK font found (run inside the rm-dev / rm-next container)')


def texture_transform() -> str:
    t = os.environ.get('RESCUEMIND_SIGN_TEXTURE_TRANSFORM', 'none')
    if t not in TRANSFORMS:
        raise ValueError(f'RESCUEMIND_SIGN_TEXTURE_TRANSFORM must be one of {TRANSFORMS}')
    return t


def _fit(draw, lines, font_path, box_w, box_h):
    """Largest font size at which all lines fit the box (width) and the stacked lines fit its height."""
    from PIL import ImageFont
    lo, hi, best = 8, 400, 8
    while lo <= hi:
        mid = (lo + hi) // 2
        f = ImageFont.truetype(font_path, mid)
        widths = [draw.textlength(s, font=f) for s in lines]
        line_h = mid * 1.18
        if max(widths) <= box_w and line_h * len(lines) <= box_h:
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    return best


def sign_png_name(text: str, w_m: float, h_m: float, transform: str | None = None) -> str:
    key = f'{text}|{w_m:.3f}|{h_m:.3f}|{transform or texture_transform()}'
    return 'sign_' + hashlib.sha1(key.encode('utf8')).hexdigest()[:12] + '.png'


def render_sign_png(text: str, out_dir: Path, w_m: float, h_m: float, transform: str | None = None) -> Path:
    """Write (or reuse) the texture of a sign of w_m x h_m metres; returns the absolute path."""
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    transform = transform or texture_transform()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = (out_dir / sign_png_name(text, w_m, h_m, transform)).resolve()
    if path.is_file():
        return path
    font_path = find_font(text)
    W, H = int(round(w_m * PX_PER_M)), int(round(h_m * PX_PER_M))
    im = Image.new('RGB', (W, H), (255, 255, 255))
    d = ImageDraw.Draw(im)
    b = max(4, int(0.03 * min(W, H)))
    d.rectangle([0, 0, W - 1, H - 1], outline=(0, 0, 0), width=b)
    lines = text.split('\n')
    pad = int(0.08 * min(W, H))
    size = _fit(d, lines, font_path, W - 2 * pad - 2 * b, H - 2 * pad - 2 * b)
    font = ImageFont.truetype(font_path, size)
    line_h = size * 1.18
    y = (H - line_h * len(lines)) / 2
    for s in lines:
        d.text(((W - d.textlength(s, font=font)) / 2, y + (line_h - size) / 2 - size * 0.06), s, font=font, fill=(0, 0, 0))
        y += line_h
    if transform == 'fliplr':
        im = ImageOps.mirror(im)
    elif transform == 'flipud':
        im = ImageOps.flip(im)
    elif transform == 'rot180':
        im = im.rotate(180)
    im.save(path)
    return path
