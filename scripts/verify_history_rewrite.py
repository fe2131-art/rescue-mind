#!/usr/bin/env python3
"""Verify the one-time history rewrite of 2026-10-26 (docs/PROVENANCE.md): the commit messages of `main` lost their Claude co-author trailer lines and
nothing else.  The original history is the public tag `archive/pre-claude-attribution-rewrite-20261026`; the rewritten history ends at REWRITE_HEAD.

The old and new DAGs are walked in parallel from their heads (parent i with parent i).  For every pair this checks: identical tree; identical headers
(author and committer name, email, time, zone); the same number of parents; the message equal after removing ONLY lines that are Claude co-author
trailers; no such trailer left.  The pairing must cover every commit of both histories exactly once.  It does not recompute any hash.

  python3 scripts/verify_history_rewrite.py [--old REF] [--new REF] [--write-map docs/provenance/commit_map_20261026.tsv] [--check-map FILE]
Needs the archive tag: git fetch origin tag archive/pre-claude-attribution-rewrite-20261026
"""
from __future__ import annotations
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_TAG = 'refs/tags/archive/pre-claude-attribution-rewrite-20261026'
REWRITE_HEAD = '76f69aad66c1148f534c08013a31827eb709c834'      # the head of main as rewritten on 2026-10-26 (later commits are on top of it)
TRAILER = re.compile(rb'^[ \t]*co-authored-by:[ \t]*claude[^\r\n]*<noreply@anthropic\.com>[ \t]*$', re.I)


def git(*a):
    return subprocess.check_output(['git', *a], cwd=ROOT)


def parse(sha):
    head, _, msg = git('cat-file', 'commit', sha).partition(b'\n\n')
    d = {'parent': []}
    for ln in head.split(b'\n'):
        k, _, v = ln.partition(b' ')
        if k == b'parent':
            d['parent'].append(v.decode())
        else:
            d.setdefault(k.decode(), []).append(v)
    return d, msg


def pair(old_head, new_head):
    o2n, n2o, stack = {}, {}, [(old_head, new_head)]
    removed = merges = 0
    while stack:
        o, n = stack.pop()
        if o in o2n:
            assert o2n[o] == n, f'inconsistent pairing for {o}'
            continue
        assert n not in n2o, f'{n} is paired with two original commits'
        o2n[o], n2o[n] = n, o
        do, mo = parse(o)
        dn, mn = parse(n)
        for k in set(do) | set(dn):
            if k != 'parent':
                assert do.get(k) == dn.get(k), f'header {k} differs for {o}'
        assert len(do['parent']) == len(dn['parent']), f'number of parents differs for {o}'
        merges += len(do['parent']) > 1
        lo, ln_ = mo.splitlines(keepends=True), mn.splitlines(keepends=True)
        kept = [x for x in lo if not TRAILER.fullmatch(x.rstrip(b'\r\n'))]
        assert kept == ln_, f'message differs beyond the Claude trailer lines for {o}'
        assert not any(TRAILER.fullmatch(x.rstrip(b'\r\n')) for x in ln_), f'trailer left in {n}'
        removed += len(lo) - len(kept)
        stack += list(zip(do['parent'], dn['parent']))
    return o2n, merges, removed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--old', default=ARCHIVE_TAG + '^{commit}')
    ap.add_argument('--new', default=REWRITE_HEAD)
    ap.add_argument('--write-map')
    ap.add_argument('--check-map')
    a = ap.parse_args()
    old_head, new_head = (git('rev-parse', '--verify', x).decode().strip() for x in (a.old, a.new))
    o2n, merges, removed = pair(old_head, new_head)
    all_old = set(git('rev-list', old_head).decode().split())
    all_new = set(git('rev-list', new_head).decode().split())
    assert set(o2n) == all_old and set(o2n.values()) == all_new, 'the pairing does not cover every commit of both histories'
    assert git('rev-parse', f'{old_head}^{{tree}}') == git('rev-parse', f'{new_head}^{{tree}}'), 'the final trees differ'
    print(f'OK: {len(o2n)} commits paired one-to-one ({merges} merges); trees, authors, committers, dates and parents identical; {removed} Claude trailer lines removed, nothing else changed.')
    print(f'    original head {old_head}\n    rewritten head {new_head}')
    rows = ''.join(f'{o}\t{n}\n' for o, n in sorted(o2n.items()))
    if a.write_map:
        Path(a.write_map).write_text(rows)
        print('wrote', a.write_map)
    if a.check_map:
        assert Path(a.check_map).read_text() == rows, f'{a.check_map} differs from the computed pairing'
        print('the published commit map matches the computed pairing')


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, subprocess.CalledProcessError) as e:
        print('FAILED:', e, file=sys.stderr)
        sys.exit(1)
