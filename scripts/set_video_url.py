#!/usr/bin/env python3
"""Put the YouTube URL of the submission video into the documents (after the user has uploaded the video).

  python3 scripts/set_video_url.py URL                 # DRY RUN (default): show the diff and the commands, change nothing
  python3 scripts/set_video_url.py URL --apply         # write README.md and docs/SUBMISSION.md, then rebuild the explanation PDF
  python3 scripts/set_video_url.py URL --apply --no-report    # texts only (no docker)
  python3 scripts/set_video_url.py URL --apply --snapshot     # also build the snapshot PDF (docs/snapshot/report/, untracked)
  python3 scripts/set_video_url.py --clear --apply     # back to the placeholder

The URL is checked (youtube.com/watch?v=ID, youtu.be/ID or youtube.com/shorts/ID, ID = 11 characters) and normalised to
https://www.youtube.com/watch?v=ID.  The places are the text between <!--VIDEOURL--> and <!--/VIDEOURL--> in README.md (first screen)
and docs/SUBMISSION.md; the PDF gets it through `make_report.py --video-url`.  Idempotent.  Nothing is committed or pushed.
"""
from __future__ import annotations
import argparse
import difflib
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = 'YouTube（提出時にURLを記載）'
UNSET_SUB = '未設定'
MARK = re.compile(r'(<!--VIDEOURL-->)(.*?)(<!--/VIDEOURL-->)', re.S)
ID_RX = re.compile(r'^[A-Za-z0-9_-]{11}$')


def normalize_url(raw: str) -> str:
    """Return https://www.youtube.com/watch?v=ID, or raise ValueError."""
    u = urlparse(raw.strip())
    host = (u.hostname or '').lower().removeprefix('www.').removeprefix('m.')
    vid = None
    if host == 'youtu.be':
        vid = u.path.strip('/').split('/')[0]
    elif host == 'youtube.com':
        if u.path == '/watch':
            vid = (parse_qs(u.query).get('v') or [''])[0]
        elif u.path.startswith(('/shorts/', '/live/', '/embed/')):
            vid = u.path.split('/')[2] if u.path.count('/') >= 2 else ''
    if u.scheme not in ('http', 'https') or not vid or not ID_RX.match(vid):
        raise ValueError(f'not a YouTube video URL: {raw!r} (expected https://www.youtube.com/watch?v=<11 chars> or https://youtu.be/<11 chars>)')
    return f'https://www.youtube.com/watch?v={vid}'


def rewrite(text: str, inner: str, name: str) -> str:
    """Replace the text inside the (exactly one) VIDEOURL marker pair."""
    if len(MARK.findall(text)) != 1:
        raise ValueError(f'{name}: expected exactly one <!--VIDEOURL-->...<!--/VIDEOURL--> pair, found {len(MARK.findall(text))}')
    return MARK.sub(lambda m: m.group(1) + inner + m.group(3), text)


def new_texts(url: str | None) -> dict[str, str]:
    """{relative path: new text}.  url=None restores the placeholders."""
    out = {}
    for rel, inner in (('README.md', f'[YouTube]({url})' if url else PLACEHOLDER), ('docs/SUBMISSION.md', url or UNSET_SUB)):
        out[rel] = rewrite((ROOT / rel).read_text(encoding='utf8'), inner, rel)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('url', nargs='?')
    ap.add_argument('--clear', action='store_true', help='restore the placeholders')
    ap.add_argument('--apply', action='store_true', help='write the files (default: dry run)')
    ap.add_argument('--no-report', action='store_true', help='do not rebuild the explanation PDF')
    ap.add_argument('--snapshot', action='store_true', help='also rebuild the snapshot PDF (docs/snapshot/report/)')
    ap.add_argument('--account', default='tetsutetsu')
    ap.add_argument('--dev', default='rm-dev', help='container that has reportlab')
    a = ap.parse_args(argv)
    if bool(a.url) == a.clear:
        ap.error('give exactly one of URL or --clear')
    try:
        url = None if a.clear else normalize_url(a.url)
    except ValueError as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 2
    try:
        texts = new_texts(url)
    except ValueError as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 2
    changed = 0
    for rel, new in texts.items():
        old = (ROOT / rel).read_text(encoding='utf8')
        if old == new:
            print(f'{rel}: already up to date')
            continue
        changed += 1
        sys.stdout.writelines(difflib.unified_diff(old.splitlines(True), new.splitlines(True), f'a/{rel}', f'b/{rel}', n=0))
        if a.apply:
            (ROOT / rel).write_text(new, encoding='utf8')
            print(f'{rel}: written')
    cmds = []
    if not a.no_report:
        base = ['docker', 'exec', '-w', str(ROOT), a.dev, 'rescuemind-entrypoint', 'python3', 'scripts/make_report.py', '--account', a.account]
        if url:
            base += ['--video-url', url]
        cmds.append(base)
        if a.snapshot:
            cmds.append(base + ['--snapshot'])
    if not a.apply:
        print('\nDRY RUN: nothing was changed.  Add --apply to write.' + ''.join('\n  would run: nice -n 19 ' + ' '.join(c).replace(str(ROOT), '.') for c in cmds))
        return 0
    for c in cmds:
        print('running:', ' '.join(c).replace(str(ROOT), '.'))
        r = subprocess.run(['nice', '-n', '19', *c], cwd=ROOT)
        if r.returncode:
            print(f'ERROR: report build failed (rc={r.returncode}); is container {a.dev} running?', file=sys.stderr)
            return r.returncode
    print('\nNext: python3 scripts/check_consistency.py   (exit 0), then git add README.md docs/SUBMISSION.md docs/report && git commit && git push')
    return 0


if __name__ == '__main__':
    sys.exit(main())
