#!/usr/bin/env python3
"""Study XD-R (experiments/PREREGISTRATION_XD.md): collect the real, fire-free warehouse photographs from Wikimedia Commons.

Modelled on scripts/q_fetch.py (same Commons API use, same 960-px Commons thumbnail, same licence policy, same descriptive
User-Agent).  Nothing here looks at a model output; no inference is run.

  python3 scripts/xd_fetch.py --list       # query the Commons API per source category (cached in ~/.cache/rescuemind/xd_real/listing)
  python3 scripts/xd_fetch.py --draw       # metadata filters + seeded per-category draw -> experiments/xd_real_candidates.json
  python3 scripts/xd_fetch.py --download   # fetch the 960-px thumbnails (resumable) into the candidate folder, record sha256
  python3 scripts/xd_fetch.py --sheets     # contact sheets (20 per sheet, labelled with the Commons page id) for the investigator
  python3 scripts/xd_fetch.py --finalize   # apply experiments/xd_real_exclusions.json -> manifest.jsonl for xd_realphoto.py
                                           #   (excluded images are moved out of the folder; the manifest is copied to experiments/)

Layout (images stay OUTSIDE the repository):
  ~/.cache/rescuemind/xd_real/listing, candidates/, sheets/, excluded/      working files
  ~/.cache/rescuemind/warehouse_negatives/<pageid>.jpg + manifest.jsonl     what scripts/xd_realphoto.py reads (kept images only)
In the repository: experiments/xd_real_candidates.json, experiments/xd_real_exclusions.json, experiments/xd_real_manifest.jsonl.

The manifest follows scripts/xd_realphoto.py: file, source_url, licence (one of its registered spellings), fire_free_checked, kind;
plus title, author, licence_commons (the string on the Commons file page), commons_id, sha256, width, height.
Only the Python standard library (and Pillow for --sheets).
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import random
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = Path.home() / '.cache/rescuemind/xd_real'
DEST = Path.home() / '.cache/rescuemind/warehouse_negatives'
CANDS = ROOT / 'experiments/xd_real_candidates.json'
EXCL = ROOT / 'experiments/xd_real_exclusions.json'
MANIFEST_COPY = ROOT / 'experiments/xd_real_manifest.jsonl'
SEED = 'XD-real-2026-cand'
API = 'https://commons.wikimedia.org/w/api.php'
UA = {'User-Agent': 'RescueMind-study-XD/1.0 (offline academic evaluation of false alarms; https://github.com/fe2131-art/rescue-mind)'}
THUMB_WIDTH = 960            # the same standard Commons thumbnail size as study Q
SLEEP = 0.5                  # polite pause between requests

# (kind [one of xd_realphoto.KINDS], Commons category [direct files only], cap).  Caps apply after the metadata filters.
SOURCES = [
    ('warehouse', 'Interiors of warehouses', 40),
    ('warehouse', 'High-rack warehouses', 25),
    ('warehouse', 'Cold storage warehouses (interior)', 7),
    ('warehouse', 'Interior of Lepakko', 7),
    ('warehouse', 'Order picking', 18),
    ('warehouse', 'Automated storage and retrieval systems', 22),
    ('warehouse', 'Amazon.com distribution centres', 14),
    ('warehouse', 'Godowns', 8),
    ('warehouse', 'Parcel hubs', 2),
    ('warehouse', 'Warehouses', 30),
    ('warehouse', 'Logistics', 12),
    ('shelves', 'Pallet racking', 30),
    ('shelves', 'Wire shelving', 10),
    ('shelves', 'Supermarket shelves', 12),
    ('shelves', 'Shop shelves', 8),
    ('storeroom', 'Stockrooms', 24),
    ('storeroom', 'Storehouses', 6),
    ('storeroom', 'Relief supplies', 5),
    ('storeroom', 'Disaster relief', 6),
    ('storeroom', 'Food banks', 15),
    ('loading_dock', 'Loading bays', 18),
    ('other', 'Wooden pallets', 10),
    ('other', 'Pallets', 8),
]
# Round 2 (added after the visual check of round 1 left 207 of 316 photographs, a thin margin over the 200 registered; still before any
# inference).  A category listed again is drawn from the files not taken in round 1, with the same per-category seed; round 1 is unchanged.
SOURCES += [
    ('shelves', 'Pallet racking', 15),
    ('warehouse', 'Automated storage and retrieval systems', 1),
    ('warehouse', 'Godowns', 1),
    ('storeroom', 'Storehouses', 3),
    ('warehouse', 'Warehouses', 30),
    ('warehouse', 'Logistics', 6),
    ('loading_dock', 'Loading bays', 8),
    ('shelves', 'Supermarket shelves', 6),
    ('shelves', 'Shop shelves', 4),
    ('other', 'Wooden pallets', 4),
]
KINDS = ('warehouse', 'storeroom', 'shelves', 'loading_dock', 'other')

# licence policy (fixed before any download): CC0, CC BY, CC BY-SA, public domain; NC / ND / GFDL-only / unknown are out.  Only the
# versions that scripts/xd_realphoto.py registers are taken (CC0, BY 3.0 / 4.0, BY-SA 3.0 / 4.0, public domain), unported.
LICENCE_MAP = [(re.compile(r'^CC0', re.I), 'CC0'),
               (re.compile(r'^CC[ -]BY[ -]4\.0$', re.I), 'CC-BY-4.0'),
               (re.compile(r'^CC[ -]BY[ -]3\.0$', re.I), 'CC-BY-3.0'),
               (re.compile(r'^CC[ -]BY-SA[ -]4\.0$', re.I), 'CC-BY-SA-4.0'),
               (re.compile(r'^CC[ -]BY-SA[ -]3\.0$', re.I), 'CC-BY-SA-3.0'),
               (re.compile(r'^(Public domain|PD\b)', re.I), 'PUBLIC-DOMAIN')]
# titles that point at drawings, maps, scans, fires ... (deterministic pre-filter on metadata; every kept image is also looked at)
TITLE_BAD = re.compile(r'logo|icon|diagram|drawing|illustration|poster|advert|screenshot|\bmap\b|flag|stamp|vector|clipart|render|'
                       r'symbol|pictogram|\bsign\b|infographic|painting|cartoon|\bsvg\b|plan\b|blueprint|scan\b|postcard|'
                       r'fire|burn|blaze|smoke|flame|explos|attack|arson|damage|ruin|destroy|collaps|bomb|war\b|portrait|'
                       r'worker|portrait|team|staff|crew|group|ceremony|opening|visit|meeting|speech', re.I)
MIN_W, MIN_H, MAX_RATIO = 480, 320, 2.5


def norm_licence(short: str | None) -> str | None:
    s = (short or '').strip()
    for rx, name in LICENCE_MAP:
        if rx.match(s):
            return name
    return None


def strip_html(s: str | None) -> str:
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', s or '')).split())[:200]


def usable(rec: dict) -> bool:
    """Deterministic pre-filter on the Commons metadata (no image is looked at)."""
    if rec.get('mime') != 'image/jpeg' or norm_licence(rec.get('licence')) is None:
        return False
    w, h = rec.get('width') or 0, rec.get('height') or 0
    if w < MIN_W or h < MIN_H or max(w / h, h / w) > MAX_RATIO:
        return False
    return not TITLE_BAD.search(rec.get('title', ''))


def draw(listings: dict, sources=SOURCES, seed: str = SEED) -> list:
    """listings: {category: [rec, ...]} -> candidate list.  Pure and deterministic.  A file in several categories stays with the
    first source in `sources` order; caps apply per category after the filters."""
    taken, out = set(), []
    for kind, cat, cap in sources:
        pool = sorted((r for r in listings.get(cat, []) if r['pageid'] not in taken and usable(r)), key=lambda r: r['pageid'])
        pick = random.Random(f'{seed}|{cat}').sample(pool, min(cap, len(pool)))
        for r in sorted(pick, key=lambda r: r['pageid']):
            taken.add(r['pageid'])
            out.append({'id': r['pageid'], 'kind': kind, 'category': cat, 'licence_norm': norm_licence(r['licence']),
                        **{k: r[k] for k in ('title', 'page_url', 'thumb_url', 'width', 'height', 'licence', 'licence_url', 'artist')}})
    return out


# ------------------------------------------------------------------ Commons API
def _get(url: str, *, binary: bool = False, tries: int = 6):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as f:
                data = f.read()
            return data if binary else json.loads(data)
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or k == tries - 1:
                raise
            time.sleep(min(60, 2 ** (k + 1) * (3 if e.code == 429 else 1)))
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if k == tries - 1:
                raise
            time.sleep(2 ** (k + 1))


def list_category(cat: str, max_files: int = 1200) -> list:
    params = {'action': 'query', 'format': 'json', 'generator': 'categorymembers', 'gcmtitle': f'Category:{cat}',
              'gcmtype': 'file', 'gcmlimit': '50', 'prop': 'imageinfo', 'iiprop': 'url|size|mime|extmetadata',
              'iiurlwidth': str(THUMB_WIDTH), 'iiextmetadatafilter': 'LicenseShortName|LicenseUrl|Artist|Credit'}
    pages, cont = {}, {}
    while True:
        d = _get(API + '?' + urllib.parse.urlencode({**params, **cont}))
        for pid, pg in (d.get('query') or {}).get('pages', {}).items():
            cur = pages.setdefault(int(pid), {})
            cur.update({k: v for k, v in pg.items() if k != 'imageinfo'})
            if 'imageinfo' in pg:
                cur['imageinfo'] = pg['imageinfo'][0]
        cont = d.get('continue') or {}
        if not cont or len(pages) >= max_files:
            break
        time.sleep(SLEEP)
    out = []
    for pid, pg in sorted(pages.items()):
        ii = pg.get('imageinfo')
        if not ii:
            continue
        md = ii.get('extmetadata') or {}
        val = lambda k: (md.get(k) or {}).get('value')
        out.append({'pageid': pid, 'title': pg.get('title', ''), 'page_url': ii.get('descriptionurl'),
                    'thumb_url': ii.get('thumburl') or ii.get('url'), 'mime': ii.get('mime'),
                    'width': ii.get('width'), 'height': ii.get('height'), 'licence': val('LicenseShortName'),
                    'licence_url': val('LicenseUrl'), 'artist': strip_html(val('Artist')) or strip_html(val('Credit'))})
    return out


def _lf(cat: str) -> Path:
    return WORK / 'listing' / (re.sub(r'\W+', '_', cat) + '.json')


def do_list():
    (WORK / 'listing').mkdir(parents=True, exist_ok=True)
    for _k, cat, _cap in SOURCES:
        if _lf(cat).is_file():
            continue
        _lf(cat).write_text(json.dumps(list_category(cat)))
        print('listed', cat, len(json.loads(_lf(cat).read_text())), flush=True)
        time.sleep(SLEEP)


def load_listings() -> dict:
    out = {}
    for _k, cat, _cap in SOURCES:
        if not _lf(cat).is_file():
            sys.exit(f'missing listing for {cat}: run --list first')
        out[cat] = json.loads(_lf(cat).read_text())
    return out


def write_cands(cands: list):
    CANDS.write_text(json.dumps({
        'study': 'XD-R', 'prereg': 'experiments/PREREGISTRATION_XD.md', 'seed': SEED,
        'source': 'Wikimedia Commons (per-image licence from the file page)', 'thumb_width': THUMB_WIDTH,
        'licence_policy': [rx.pattern + ' -> ' + n for rx, n in LICENCE_MAP], 'n': len(cands),
        'note': 'candidates before the visual check; images are not in the repository; working copy ~/.cache/rescuemind/xd_real/candidates/<id>.jpg',
        'images': cands}, indent=1, ensure_ascii=False) + '\n')


def do_draw():
    cands = draw(load_listings())
    old = {}
    if CANDS.is_file():
        old = {r['id']: r for r in json.loads(CANDS.read_text())['images']}
    for r in cands:
        if r['id'] in old and old[r['id']].get('sha256'):
            r.update({k: old[r['id']][k] for k in ('sha256', 'bytes', 'file') if k in old[r['id']]})
    write_cands(cands)
    print('drawn', len(cands), {k: sum(r['kind'] == k for r in cands) for k in KINDS})


def do_download():
    img = WORK / 'candidates'
    img.mkdir(parents=True, exist_ok=True)
    cands = json.loads(CANDS.read_text())['images']
    for i, r in enumerate(cands):
        f = img / f'{r["id"]}.jpg'
        if not f.is_file():
            f.write_bytes(_get(r['thumb_url'], binary=True))
            time.sleep(SLEEP)
        b = f.read_bytes()
        r.update({'sha256': hashlib.sha256(b).hexdigest(), 'bytes': len(b), 'file': f'{r["id"]}.jpg'})
        if (i + 1) % 50 == 0:
            print('downloaded', i + 1, '/', len(cands), flush=True)
            write_cands(cands)
    seen, keep = {}, []
    for r in sorted(cands, key=lambda r: r['id']):      # byte-identical duplicates: keep the lowest id
        if r['sha256'] in seen:
            print('duplicate bytes dropped:', r['id'], '=', seen[r['sha256']])
            (img / r['file']).unlink(missing_ok=True)
            continue
        seen[r['sha256']] = r['id']
        keep.append(r)
    write_cands(keep)
    print('downloaded', len(keep), 'images,', round(sum(r['bytes'] for r in keep) / 1e6, 1), 'MB')


def do_sheets(per: int = 20, cols: int = 5, tile: int = 320):
    from PIL import Image, ImageDraw
    out = WORK / 'sheets'
    out.mkdir(parents=True, exist_ok=True)
    cands = sorted(json.loads(CANDS.read_text())['images'], key=lambda r: r['id'])
    rows = -(-per // cols)
    for s in range(0, len(cands), per):
        sheet = Image.new('RGB', (cols * tile, rows * (tile + 16)), 'white')
        dr = ImageDraw.Draw(sheet)
        for j, r in enumerate(cands[s:s + per]):
            x, y = (j % cols) * tile, (j // cols) * (tile + 16)
            im = Image.open(WORK / 'candidates' / r['file']).convert('RGB')
            im.thumbnail((tile - 4, tile - 4))
            sheet.paste(im, (x + 2, y + 16))
            dr.text((x + 3, y + 2), f'{r["id"]} {r["kind"][:4]}', fill='black')
        sheet.save(out / f'sheet_{s // per:02d}.jpg', quality=88)
    print('sheets', -(-len(cands) // per), 'in', out)


def do_finalize():
    ex = json.loads(EXCL.read_text())
    excluded = {int(k): v for k, v in ex['excluded'].items()}
    cands = json.loads(CANDS.read_text())['images']
    ids = {r['id'] for r in cands}
    unknown = set(excluded) - ids
    if unknown:
        sys.exit(f'exclusions for ids that are not candidates: {sorted(unknown)}')
    DEST.mkdir(parents=True, exist_ok=True)
    (WORK / 'excluded').mkdir(parents=True, exist_ok=True)
    rows = []
    for r in sorted(cands, key=lambda r: r['id']):
        src = WORK / 'candidates' / r['file']
        if r['id'] in excluded:
            (DEST / r['file']).unlink(missing_ok=True)
            continue
        shutil.copy2(src, DEST / r['file'])
        if hashlib.sha256((DEST / r['file']).read_bytes()).hexdigest() != r['sha256']:
            sys.exit(f'{r["file"]}: sha256 differs from the candidate record')
        rows.append({'file': r['file'], 'source_url': r['page_url'], 'licence': r['licence_norm'], 'fire_free_checked': True,
                     'kind': r['kind'], 'title': r['title'], 'author': r['artist'], 'licence_commons': r['licence'],
                     'licence_url': r['licence_url'], 'commons_id': r['id'], 'sha256': r['sha256'],
                     'width': r['width'], 'height': r['height']})
    text = ''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in rows)
    (DEST / 'manifest.jsonl').write_text(text, encoding='utf-8')
    MANIFEST_COPY.write_text(text, encoding='utf-8')
    for f in DEST.iterdir():                          # nothing in the folder without a manifest row
        if f.name != 'manifest.jsonl' and f.name not in {x['file'] for x in rows}:
            f.rename(WORK / 'excluded' / f.name)
    print('kept', len(rows), 'excluded', len(excluded))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k in ('list', 'draw', 'download', 'sheets', 'finalize'):
        ap.add_argument('--' + k, action='store_true')
    a = ap.parse_args()
    if a.list:
        do_list()
    if a.draw:
        do_draw()
    if a.download:
        do_download()
    if a.sheets:
        do_sheets()
    if a.finalize:
        do_finalize()


if __name__ == '__main__':
    main()
