#!/usr/bin/env python3
"""Study Q (experiments/PREREGISTRATION_Q.md): fetch the candidate real photographs from Wikimedia Commons.

  python3 scripts/q_fetch.py --list          # query the Commons API per source category (cached in ~/.cache/rescuemind/q/listing)
  python3 scripts/q_fetch.py --draw          # apply the filters, draw the candidates (seed Q-2026), write experiments/q_sample.json
  python3 scripts/q_fetch.py --download      # fetch the 960-px thumbnails (resumable), record sha256 -> experiments/q_sample.json
  python3 scripts/q_fetch.py --all           # the three steps

Only the Python standard library is used.  Images stay outside the repository (~/.cache/rescuemind/q/images);
the repository holds file page URL, licence, author and sha256 per image.  Nothing here looks at a model output.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path.home() / '.cache/rescuemind/q'
SAMPLE = ROOT / 'experiments/q_sample.json'
SEED = 'Q-2026'
API = 'https://commons.wikimedia.org/w/api.php'
UA = {'User-Agent': 'RescueMind-study-Q/1.0 (offline academic evaluation; https://github.com/tetsutetsu/rescue-mind)'}
THUMB_WIDTH = 960            # a standard Commons thumbnail size

# (class, type, Commons category [direct files only], cap).  Caps are applied after the filters, per category.
# water = sealed drinking-water bottles; medicine = first-aid kits / boxes / bags; neither = everything else.
SOURCES = [
    ('water', 'bottled_water', 'Bottled water', 100),
    ('water', 'water_bottles', 'Water bottles', 70),
    ('water', 'evian', 'Evian Water bottles', 14),
    ('water', 'nongfu', 'Nongfu Spring water bottles', 8),
    ('medicine', 'first_aid_kits', 'First aid kits', 95),
    ('medicine', 'kits_de', 'First aid kits in Germany', 35),
    ('medicine', 'kits_nl', 'First aid kits in the Netherlands', 15),
    ('medicine', 'kits_military', 'Military first aid kits', 25),
    ('medicine', 'kits_sncf', 'SNCF - Kit assistance', 15),
    ('medicine', 'kits_tabloid', 'Tabloid First Aid Box', 8),
    ('medicine', 'kits_idf', 'IDF Corona medical equipment kit', 5),
    ('medicine', 'kits_din', 'DIN 13164', 1),
    ('medicine', 'kits_din', 'DIN 13167', 3),
    ('medicine', 'kits_ba', 'First aid kits in Bosnia and Herzegovina', 4),
    ('neither', 'soda_bottle', 'Soft drink bottles', 25),
    ('neither', 'wine_bottle', 'Wine bottles', 25),
    ('neither', 'toolbox', 'Toolboxes', 25),
    ('neither', 'cardboard_box', 'Cardboard boxes', 25),
    ('neither', 'red_box', 'Red boxes', 25),
    ('neither', 'pill_bottle', 'Medicine bottles', 25),
    ('neither', 'empty_platform', 'Empty shop shelves', 9),
    ('neither', 'empty_platform', 'Wooden pallets', 8),
    ('neither', 'empty_platform', 'Pallets', 8),
    ('neither', 'crate', 'Crates', 25),
]
# Round 2 (added after the label audit of round 1 showed a ~45% yield for water and medicine; still before any inference).
# A category listed again is drawn from the files not taken in round 1, with the same per-category seed.
SOURCES += [('water', 'water_brands', c, 7) for c in (
    'Aquafina', 'Poland Spring', 'Borjomi water', 'Top Bronnen', 'Mattoni', 'Bonaqua Water', 'I LOHAS', 'Watsons Water', 'Evian',
    'Vittel water', 'Fiji Water', 'Cristaline', 'Volvic (mineral water)', 'Ganten (brand)', "China Resources C'estbon Beverage")]
SOURCES += [
    ('medicine', 'first_aid_kits', 'First aid kits', 60),
    ('medicine', 'kits_museum', 'First aid in Auckland Museum', 25),
    ('medicine', 'kits_museum', 'Bag, first aid (AM 650776)', 6),
    ('medicine', 'kits_museum', 'Kit, medical (AM 1979.59)', 6),
    ('medicine', 'kits_museum', 'Kit, medical (AM 2015.20.18)', 3),
    ('medicine', 'kits_de', 'Anker Verbandkasten', 5),
    ('medicine', 'kits_de', 'Kraftwagen-Einheitsverbandkasten der Berufsgenossenschaften', 3),
    ('neither', 'toolbox', 'Toolboxes', 15),
    ('neither', 'soda_bottle', 'Soft drink bottles', 15),
    ('neither', 'wine_bottle', 'Wine bottles', 8),
    ('neither', 'red_box', 'Red boxes', 10),
    ('neither', 'pill_bottle', 'Medicine bottles', 10),
    ('neither', 'shoe_box', 'Shoe boxes', 12),
    ('neither', 'briefcase', 'Briefcases', 12),
    ('neither', 'plastic_box', 'Plastic boxes', 10),
    ('neither', 'ammo_box', 'Ammunition boxes', 10),
]
# Round 3 (after the round-2 audit: water still short, brand categories turned out to be mostly advertising / buses / people).
SOURCES += [
    ('water', 'bottled_water', 'Bottled water', 80),
    ('water', 'mineral_waters', 'Mineral waters', 35),
    ('water', 'mineral_waters', 'Voss (water)', 9),
    ('water', 'mineral_waters', 'Spa (mineral water)', 10),
    ('water', 'mineral_waters', 'Apollinaris (water)', 10),
    ('water', 'mineral_waters', 'Ifri (mineral water)', 9),
    ('water', 'mineral_waters', 'Contrex (mineral water)', 7),
    ('water', 'mineral_waters', 'Glaceau Smartwater', 6),
    ('water', 'mineral_waters', 'Spring water', 8),
    ('medicine', 'kits_bags', 'Medical bags', 10),
]
CLASSES = ('water', 'medicine', 'neither')

# licence policy (fixed before any download): CC0, CC BY, CC BY-SA, public-domain marks.  NC / ND / GFDL-only / unknown are out.
LICENCE_OK = re.compile(r'^(CC0|CC[ -]BY[ -]\d\.\d|CC[ -]BY-SA[ -]\d\.\d|Public domain|PD\b)', re.I)
# titles that point at drawings, logos, maps, signs ... (not photographs of an object on a platform)
TITLE_BAD = re.compile(r'logo|icon|diagram|drawing|illustration|poster|advert|screenshot|\bmap\b|flag|stamp|label|vector|clipart|'
                       r'render|symbol|pictogram|\bsign\b|infographic|painting|cartoon|\bsvg\b', re.I)
MIN_W, MIN_H, MAX_RATIO = 480, 320, 2.5


def licence_ok(short: str | None) -> bool:
    return bool(short) and bool(LICENCE_OK.match(short.strip()))


def strip_html(s: str | None) -> str:
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', s or '')).split())[:200]


def usable(rec: dict) -> bool:
    """Deterministic pre-filter on the Commons metadata (no image is looked at)."""
    if rec.get('mime') != 'image/jpeg' or not licence_ok(rec.get('licence')):
        return False
    w, h = rec.get('width') or 0, rec.get('height') or 0
    if w < MIN_W or h < MIN_H or max(w / h, h / w) > MAX_RATIO:
        return False
    return not TITLE_BAD.search(rec.get('title', ''))


def draw(listings: dict, sources=SOURCES, seed: str = SEED) -> list:
    """listings: {category: [rec, ...]} -> the candidate list.  Pure and deterministic.
    A file listed under categories of two different classes is dropped everywhere; a file listed twice within a class
    stays with the first source in `sources` order.  Caps apply per category after the filters."""
    owner = {}
    for cls, _t, cat, _cap in sources:
        for r in listings.get(cat, []):
            owner.setdefault(r['pageid'], set()).add(cls)
    clash = {p for p, cs in owner.items() if len(cs) > 1}
    taken, out = set(), []
    for cls, typ, cat, cap in sources:
        pool = sorted((r for r in listings.get(cat, []) if r['pageid'] not in clash and r['pageid'] not in taken and usable(r)),
                      key=lambda r: r['pageid'])
        pick = random.Random(f'{seed}|cand|{cat}').sample(pool, min(cap, len(pool)))
        for r in sorted(pick, key=lambda r: r['pageid']):
            taken.add(r['pageid'])
            out.append({'id': r['pageid'], 'class': cls, 'type': typ, 'category': cat, **{k: r[k] for k in (
                'title', 'page_url', 'thumb_url', 'width', 'height', 'licence', 'licence_url', 'artist')}})
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
              'iiurlwidth': str(THUMB_WIDTH),
              'iiextmetadatafilter': 'LicenseShortName|LicenseUrl|Artist|Credit'}
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
        time.sleep(0.3)
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


def do_list():
    (CACHE / 'listing').mkdir(parents=True, exist_ok=True)
    for _c, _t, cat, _cap in SOURCES:
        f = CACHE / 'listing' / (re.sub(r'\W+', '_', cat) + '.json')
        if f.is_file():
            continue
        f.write_text(json.dumps(list_category(cat)))
        print('listed', cat, len(json.loads(f.read_text())), flush=True)
        time.sleep(0.5)


def load_listings() -> dict:
    out = {}
    for _c, _t, cat, _cap in SOURCES:
        f = CACHE / 'listing' / (re.sub(r'\W+', '_', cat) + '.json')
        if not f.is_file():
            sys.exit(f'missing listing for {cat}: run --list first')
        out[cat] = json.loads(f.read_text())
    return out


def do_draw():
    cands = draw(load_listings())
    old = {}
    if SAMPLE.is_file():
        old = {r['id']: r for r in json.loads(SAMPLE.read_text())['images']}
    for r in cands:
        if r['id'] in old and old[r['id']].get('sha256'):
            r.update({k: old[r['id']][k] for k in ('sha256', 'bytes', 'file') if k in old[r['id']]})
    write_sample(cands)
    print('drawn', len(cands), {c: sum(r['class'] == c for r in cands) for c in CLASSES})


def write_sample(cands: list):
    SAMPLE.write_text(json.dumps({
        'study': 'Q', 'prereg': 'experiments/PREREGISTRATION_Q.md', 'seed': SEED, 'source': 'Wikimedia Commons (per-image licence from the file page)',
        'thumb_width': THUMB_WIDTH, 'licence_policy': LICENCE_OK.pattern, 'n': len(cands),
        'note': 'images are not in the repository; ~/.cache/rescuemind/q/images/<id>.jpg; attribution = title + artist + licence below',
        'images': cands}, indent=1, ensure_ascii=False) + '\n')


def do_download():
    img = CACHE / 'images'
    img.mkdir(parents=True, exist_ok=True)
    cands = json.loads(SAMPLE.read_text())['images']
    for i, r in enumerate(cands):
        f = img / f'{r["id"]}.jpg'
        if not f.is_file():
            f.write_bytes(_get(r['thumb_url'], binary=True))
            time.sleep(0.4)
        b = f.read_bytes()
        r.update({'sha256': hashlib.sha256(b).hexdigest(), 'bytes': len(b), 'file': f'{r["id"]}.jpg'})
        if (i + 1) % 50 == 0:
            print('downloaded', i + 1, '/', len(cands), flush=True)
            write_sample(cands)
    # byte-identical duplicates: keep the lowest id
    seen, keep = {}, []
    for r in sorted(cands, key=lambda r: r['id']):
        if r['sha256'] in seen:
            print('duplicate bytes dropped:', r['id'], '=', seen[r['sha256']])
            continue
        seen[r['sha256']] = r['id']
        keep.append(r)
    write_sample(keep)
    tot = sum(r['bytes'] for r in keep)
    print('downloaded', len(keep), 'images,', round(tot / 1e6, 1), 'MB', {c: sum(r['class'] == c for r in keep) for c in CLASSES})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k in ('list', 'draw', 'download', 'all'):
        ap.add_argument('--' + k, action='store_true')
    a = ap.parse_args()
    if a.list or a.all:
        do_list()
    if a.draw or a.all:
        do_draw()
    if a.download or a.all:
        do_download()


if __name__ == '__main__':
    main()
