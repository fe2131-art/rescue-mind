#!/usr/bin/env python3
"""Link check for README.md (what GitHub renders): every relative link, image and <img>/<a> target must exist and be tracked by git,
and every in-page anchor (#...) must match a heading (GitHub slug rules).  Also reports the pixel size of local images.

  python3 scripts/check_readme_links.py [README.md]      # exit 1 on a broken link
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r'!?\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)|(?:src|href)="([^"]+)"')


def slug(h: str) -> str:
    """GitHub heading anchor: lowercase, drop punctuation except - and _, spaces -> -."""
    h = h.strip().lower()
    h = re.sub(r'[^\w\- ]', '', h, flags=re.U)
    return h.replace(' ', '-')


def check(readme: Path):
    txt = readme.read_text(encoding='utf8')
    body = re.sub(r'```.*?```', '', txt, flags=re.S)          # code blocks are not links
    tracked = set(subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=True).stdout.decode().split('\0'))
    heads = {slug(m.group(1)) for m in re.finditer(r'^#{1,6}\s+(.+?)\s*$', body, flags=re.M)}
    bad, imgs, n = [], [], 0
    for m in LINK.finditer(body):
        tgt = m.group(1) or m.group(2)
        if re.match(r'[a-z][a-z0-9+.-]*:', tgt):             # http(s), mailto: not checked offline
            continue
        n += 1
        path, _, frag = tgt.partition('#')
        path = unquote(path.split('?')[0])
        if not path:
            if frag and unquote(frag) not in heads:
                bad.append(f'anchor #{frag}: no such heading')
            continue
        f = (readme.parent / path)
        try:
            rel = f.resolve().relative_to(ROOT).as_posix()
            inside = True
        except ValueError:
            rel, inside = path, False
        if not f.exists():
            bad.append(f'{tgt}: file missing')
        elif f.is_file() and inside and rel not in tracked:
            bad.append(f'{tgt}: exists but is not tracked by git (would be a broken link on GitHub)')
        elif f.suffix.lower() in ('.png', '.jpg', '.jpeg', '.gif'):
            try:
                from PIL import Image
                imgs.append((rel, Image.open(f).size, f.stat().st_size))
            except Exception:
                pass
    return n, bad, imgs


if __name__ == '__main__':
    readme = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'README.md'
    n, bad, imgs = check(readme.resolve())
    for rel, size, nbytes in sorted(set(imgs)):
        print(f'image {rel}: {size[0]}x{size[1]}, {nbytes / 1024:.0f} KB' + ('  (large: > 1.5 MB)' if nbytes > 1.5e6 else ''))
    print(f'{n} relative links checked, {len(bad)} broken')
    for b in bad:
        print('BROKEN', b)
    sys.exit(1 if bad else 0)
