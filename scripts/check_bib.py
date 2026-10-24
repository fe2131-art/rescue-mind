#!/usr/bin/env python3
"""references.bib hygiene (I-139): no key defined twice, no paper (same title or same arXiv id) under two keys, every cited key defined.

  python3 scripts/check_bib.py           # exit 1 and a list when a problem exists
  python3 scripts/check_bib.py --fix     # merge duplicates: keep the first key, rewrite citations of the others in docs/paper/*.tex, drop the later entries

Called by tests/test_bib.py and scripts/check_consistency.py.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIB = ROOT / 'docs/paper/references.bib'
ENTRY = re.compile(r'@(\w+)\{([^,\s]+),(.*?)\n\}\n?', re.S)


def entries(text: str) -> list:
    return [(m.group(2), m.group(3), m.start(), m.end()) for m in ENTRY.finditer(text)]


def norm_title(body: str) -> str:
    m = re.search(r'title\s*=\s*\{(.+?)\},?\s*\n', body, re.S)
    return re.sub(r'[^a-z0-9]', '', (m.group(1) if m else '').lower())


def eprint(body: str) -> str:
    m = re.search(r'eprint\s*=\s*\{([0-9]{4}\.[0-9]{4,5})', body)
    return m.group(1) if m else ''


def duplicates(text: str) -> dict:
    """{later key: first key} for every entry whose key, title or arXiv id was already defined."""
    first_key, by_title, by_eprint, dup = set(), {}, {}, {}
    for k, body, _a, _b in entries(text):
        t, e = norm_title(body), eprint(body)
        if k in first_key:
            dup.setdefault(k, k)
            continue
        hit = by_title.get(t) if t else None
        hit = hit or (by_eprint.get(e) if e else None)
        if hit:
            dup[k] = hit
            continue
        first_key.add(k)
        if t:
            by_title[t] = k
        if e:
            by_eprint[e] = k
    return dup


def cited_keys() -> set:
    keys = set()
    for f in (ROOT / 'docs/paper').glob('*.tex'):
        if f.name.endswith('.draft.tex'):
            continue
        for m in re.finditer(r'\\cite[pt]?\*?(?:\[[^\]]*\])?\{([^}]+)\}', f.read_text(encoding='utf8')):
            keys.update(x.strip() for x in m.group(1).split(','))
    return keys


def problems() -> list:
    text = BIB.read_text(encoding='utf8')
    out = [f'duplicate bib entry: {k} (same key, title or arXiv id as {v})' for k, v in duplicates(text).items()]
    defined = {k for k, *_ in entries(text)}
    out += [f'cited but not defined: {k}' for k in sorted(cited_keys() - defined)]
    return out


def fix() -> int:
    text = BIB.read_text(encoding='utf8')
    dup = duplicates(text)
    if not dup:
        return 0
    seen, keep = set(), []
    last = 0
    for k, body, a, b in entries(text):
        drop = (k in dup and dup[k] != k) or (k in seen)
        keep.append(text[last:a])
        if not drop:
            keep.append(text[a:b])
        seen.add(k)
        last = b
    keep.append(text[last:])
    BIB.write_text(re.sub(r'\n{3,}', '\n\n', ''.join(keep)), encoding='utf8')
    for f in (ROOT / 'docs/paper').glob('*.tex'):
        s = f.read_text(encoding='utf8')
        s2 = s
        for k, v in dup.items():
            if k != v:
                s2 = re.sub(r'(?<=[{,\s])' + re.escape(k) + r'(?=[},\s])', v, s2)
        if s2 != s:
            f.write_text(s2, encoding='utf8')
    return len(dup)


if __name__ == '__main__':
    if '--fix' in sys.argv:
        print('merged', fix())
    p = problems()
    for x in p:
        print('BIB:', x)
    print(f'{len(p)} bib problems')
    sys.exit(1 if p else 0)
