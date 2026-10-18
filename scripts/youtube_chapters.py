#!/usr/bin/env python3
"""YouTube-valid chapter list, by construction.

YouTube turns the timestamp lines of a description into chapters only when
  * the first chapter starts at 0:00,
  * there are at least 3 chapters,
  * the starts are ascending, and
  * every chapter is at least 10 seconds long (measured on the shown mm:ss marks, i.e. floored seconds).
Otherwise the whole list is silently ignored.

merge_short() merges a short segment (a title card of 5-6 s) into the following chapter, or into the preceding one when the
following one is short too (or when it is the last), with a combined title.  A merged chapter keeps the list of the original
segments in 'segments', so the merge is reversible (flatten) and idempotent.  The video script writes docs/video_chapters.json
through merge_short(); scripts/make_youtube_description.py and scripts/check_consistency.py call validate().

  python3 scripts/youtube_chapters.py            # re-merge docs/video_chapters.json from its own segments (no re-render)
  python3 scripts/youtube_chapters.py --check    # exit 1 if the file is not YouTube-valid
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIN_S = 10
MIN_N = 3
SEP = ' ＋ '
KIND_RANK = {'mission': 3, 'table': 2, 'card': 1}      # the kind of a merged chapter: the most informative part


def mmss(sec):
    s = int(sec)                                   # chapter marks: floor, like YouTube's own player
    return f'{s // 60}:{s % 60:02d}'


def flatten(chapters):
    """The original segments (a merged chapter lists its own in 'segments')."""
    out = []
    for c in sorted(chapters, key=lambda c: c['start_s']):
        out.extend(c['segments'] if c.get('segments') else [c])
    return out


def lengths(chapters):
    """Effective length of every chapter as YouTube measures it: floored start marks, the last one up to the video end."""
    marks = [int(c['start_s']) for c in chapters]
    return [(marks[i + 1] if i + 1 < len(chapters) else chapters[-1]['end_s']) - marks[i] for i in range(len(chapters))]


def demo_title(c):
    """Title of the demo run inside a chapter ('デモN：...'), or the chapter title when it holds no run."""
    return c.get('demo_title') or c['title']


def _join(parts):
    """Combined title; a part already contained in another part ('出動をまたぐ記憶' in 'デモ3：出動をまたぐ記憶 → 直行') is dropped."""
    keep = []
    for i, p in enumerate(parts):
        if any(i != j and p != q and p in q for j, q in enumerate(parts)) or p in keep:
            continue
        keep.append(p)
    return SEP.join(keep)


def _merge_two(a, b):
    segs = (a.get('segments') or [a]) + (b.get('segments') or [b])
    best = a if KIND_RANK.get(a.get('kind'), 0) >= KIND_RANK.get(b.get('kind'), 0) else b      # ties: the earlier one
    titles = [s['title'] for s in segs]
    out = {'start_s': a['start_s'], 'end_s': b['end_s'], 'title': _join(titles), 'kind': best.get('kind'),
           'speed': best.get('speed'), 'run_id': best.get('run_id')}
    run = next((s for s in segs if s.get('kind') == 'mission'), None)
    if run:
        out['demo_title'] = run['title']
        out['speed'], out['run_id'] = run.get('speed'), run.get('run_id')
    out['segments'] = [{k: v for k, v in s.items() if k != 'segments'} for s in segs]
    return out


def merge_short(chapters, min_s=MIN_S, min_n=MIN_N):
    """YouTube-valid chapter list from the raw segment list (idempotent).  Raises ValueError when no valid list exists."""
    ch = sorted((dict(c) for c in chapters), key=lambda c: c['start_s'])
    if not ch:
        raise ValueError('no chapters')
    if ch[0]['start_s'] > 0:
        ch[0] = dict(ch[0], start_s=0.0)       # the first chapter must start at 0:00
    while True:
        ln = lengths(ch)
        short = [i for i, x in enumerate(ln) if x < min_s]
        if not short:
            return ch
        if len(ch) - 1 < min_n:
            raise ValueError(f'cannot keep {min_n} chapters of >= {min_s} s ({len(ch)} chapters, video {ch[-1]["end_s"]:.1f} s)')
        i = short[0]
        last = i == len(ch) - 1
        nxt_ok = not last and ln[i + 1] >= min_s
        if nxt_ok or (not last and i == 0):
            j = i                      # merge with the following chapter
        else:
            j = i - 1                  # last, or the following one is short too: merge into the preceding chapter
        ch[j:j + 2] = [_merge_two(ch[j], ch[j + 1])]


def validate(chapters, min_s=MIN_S, min_n=MIN_N):
    """List of problems (empty = YouTube shows the chapters)."""
    if not chapters:
        return ['no chapters']
    bad = []
    if len(chapters) < min_n:
        bad.append(f'only {len(chapters)} chapters (YouTube needs at least {min_n})')
    if mmss(chapters[0]['start_s']) != '0:00':
        bad.append('first chapter does not start at 0:00')
    marks = [int(c['start_s']) for c in chapters]
    if any(b <= a for a, b in zip(marks, marks[1:])):
        bad.append('chapter starts are not strictly ascending')
    for c, x in zip(chapters, lengths(chapters)):
        if x < min_s:
            bad.append(f"chapter '{c['title']}' ({mmss(c['start_s'])}) is {x:g} s, shorter than {min_s} s")
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--file', default=str(ROOT / 'docs/video_chapters.json'))
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args(argv)
    p = Path(a.file)
    cur = json.loads(p.read_text(encoding='utf8'))
    if a.check:
        bad = validate(cur)
        print('\n'.join(bad) if bad else f'ok: {len(cur)} chapters, all >= {MIN_S} s')
        return 1 if bad else 0
    new = merge_short(flatten(cur))
    txt = json.dumps(new, ensure_ascii=False, indent=1) + '\n'
    if txt != p.read_text(encoding='utf8'):
        p.write_text(txt, encoding='utf8')
    for c, x in zip(new, lengths(new)):
        print(f"{mmss(c['start_s'])} {c['title']}  ({x:g} s)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
