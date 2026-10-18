#!/usr/bin/env python3
"""Study XD-R (DRAFT): false alarms of the v3.6 hazard question on real, fire-free warehouse / storeroom photographs.

The images are public photographs that the investigator collects BEFORE scoring into a folder outside the repository:

  ~/.cache/rescuemind/warehouse_negatives/            image files (jpg / png / webp)
  ~/.cache/rescuemind/warehouse_negatives/manifest.jsonl   one JSON object per image:
      {"file": "a.jpg", "source_url": "...", "licence": "CC0 | CC-BY-4.0 | ...", "fire_free_checked": true,
       "kind": "warehouse | storeroom | shelves | loading_dock | other"}

  python3 scripts/xd_realphoto.py --sample           # validate the manifest, draw 200 images (seed XD-real-2026) -> xd_real_sample.json
  python3 scripts/xd_realphoto.py --run              # score via :8765 (server = v3.6: h36 + tiles); resumable
  python3 scripts/xd_realphoto.py --analyse          # false-alarm rate at the three registered thresholds -> xd_real_summary.json

Only file names, hashes, sources, licences and scores are written to the repository, never the images.  The images must have
no visible fire, smoke, haze from a fire, or open flame (the investigator checks each one, `fire_free_checked`); lookalikes
(orange safety vests, red crates, warning lights, sunlit dust) are welcome and are what makes the test.  Thresholds
(registered): the frozen tau_h = 0.05, the P2-calibrated tau for h36 (0.35, experiments/results/p2_summary.json) and the depot
tau* of study XD (experiments/results/xd_summary.json, if the calibration found one).
"""
from __future__ import annotations
import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RES = ROOT / 'experiments/results'
DATA = Path('~/.cache/rescuemind/warehouse_negatives').expanduser()
SAMPLE = RES / 'xd_real_sample.json'
SCORES = RES / 'xd_real_scores_h36_tiles.jsonl'
SUMMARY = RES / 'xd_real_summary.json'
SEED = 'XD-real-2026'
N = 200
FROZEN_TAU = 0.05
FA_MAX = 0.20
EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')
KINDS = ('warehouse', 'storeroom', 'shelves', 'loading_dock', 'other')
OPEN_LICENCES = ('CC0', 'CC-BY-4.0', 'CC-BY-SA-4.0', 'CC-BY-3.0', 'CC-BY-SA-3.0', 'PUBLIC-DOMAIN', 'UNSPLASH', 'PEXELS')


def read_manifest(folder: Path) -> list:
    path = folder / 'manifest.jsonl'
    if not path.is_file():
        sys.exit(f'{path} missing: every image needs a manifest row (source, licence, fire_free_checked)')
    rows = [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]
    return rows


def validate(rows: list, folder: Path) -> list:
    """Problems of the manifest (empty = fine): unknown / duplicate / missing files, no licence, not checked fire-free."""
    bad, seen = [], set()
    for r in rows:
        f = r.get('file', '')
        if f in seen:
            bad.append(f'{f}: duplicate row')
        seen.add(f)
        if not f.lower().endswith(EXTENSIONS):
            bad.append(f'{f}: not an image file name')
        elif not (folder / f).is_file():
            bad.append(f'{f}: file missing')
        if str(r.get('licence', '')).upper().replace(' ', '-') not in OPEN_LICENCES:
            bad.append(f'{f}: licence {r.get("licence")!r} not in the registered list')
        if not r.get('source_url'):
            bad.append(f'{f}: no source_url')
        if r.get('fire_free_checked') is not True:
            bad.append(f'{f}: fire_free_checked is not true')
        if r.get('kind') not in KINDS:
            bad.append(f'{f}: kind {r.get("kind")!r}')
    return bad


def draw(rows: list, n: int = N, seed: str = SEED) -> list:
    """The first n rows of a seeded shuffle of the file-name-sorted manifest (reproducible from the manifest alone)."""
    pool = sorted(rows, key=lambda r: r['file'])
    if len(pool) < n:
        sys.exit(f'only {len(pool)} valid images, {n} registered')
    return random.Random(seed).sample(pool, n)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sample(folder: Path):
    rows = read_manifest(folder)
    bad = validate(rows, folder)
    if bad:
        sys.exit('manifest problems:\n  ' + '\n  '.join(bad[:30]) + (f'\n  ... {len(bad)} in all' if len(bad) > 30 else ''))
    out = [{'file': r['file'], 'sha256': sha256(folder / r['file']), 'source_url': r['source_url'], 'licence': r['licence'],
            'kind': r['kind']} for r in draw(rows)]
    SAMPLE.write_text(json.dumps({'seed': SEED, 'n': len(out), 'folder': str(DATA), 'images': out}, indent=1) + '\n')
    print('sample', len(out))


def run(folder: Path, port: int):
    from rescuemind.local_vision import _client_call
    done = {json.loads(x)['file'] for x in SCORES.read_text().splitlines()} if SCORES.is_file() else set()
    for r in json.loads(SAMPLE.read_text())['images']:
        if r['file'] in done:
            continue
        blob = (folder / r['file']).read_bytes()
        if hashlib.sha256(blob).hexdigest() != r['sha256']:
            sys.exit(f"{r['file']} changed since the sample was drawn")
        resp = _client_call(f'http://127.0.0.1:{port}/v1/classify', 'Qwen/Qwen3.5-9B', blob, 1, timeout=180)
        sc = resp.get('scores') or {}
        if sc.get('hazard_prompt') != 'h36' or sc.get('hazard_views') != 'tiles':
            sys.exit(f'server is not configured as v3.6 (h36 + tiles): {sc}')
        with SCORES.open('a') as f:
            f.write(json.dumps({**r, 'hazard_prob': sc.get('hazard_prob'), 'hazard_view_probs': sc.get('hazard_view_probs')}) + '\n')
    print('scored', len(json.loads(SAMPLE.read_text())['images']))


def thresholds(res: Path = RES) -> dict:
    """The registered thresholds that exist: frozen, P2 (h36) and the depot tau* of XD."""
    out = {'frozen': FROZEN_TAU}
    try:
        out['p2_h36'] = json.loads((res / 'p2_summary.json').read_text())['calibration']['h36']['tau']
    except (OSError, KeyError, ValueError):
        pass
    try:
        t = json.loads((res / 'xd_summary.json').read_text())['XD_recalibration']['calibration']['tau_star']
        if t is not None:
            out['xd_depot'] = t
    except (OSError, KeyError, ValueError):
        pass
    return out


def analyse_scores(recs: list, taus: dict) -> dict:
    """False-alarm rate (hazard flagged on a fire-free photograph; a missing / failed score counts as a flag) per threshold,
    Wilson CI, by kind.  Claim (registered): at the depot tau* the rate is <= 0.20."""
    from scripts.t1_analysis import wilson
    flag = lambda r, t: (r.get('hazard_prob') is None) or r['hazard_prob'] >= t
    out = {'n': len(recs), 'thresholds': taus, 'false_alarm': {}}
    for name, t in taus.items():
        k = sum(flag(r, t) for r in recs)
        out['false_alarm'][name] = {'tau': t, 'k': k, 'n': len(recs), 'rate': round(k / len(recs), 4) if recs else None,
                                    'ci95': wilson(k, len(recs)),
                                    'by_kind': {kd: f"{sum(flag(r, t) for r in recs if r['kind'] == kd)}/{sum(r['kind'] == kd for r in recs)}"
                                                for kd in KINDS if any(r['kind'] == kd for r in recs)}}
    fa = out['false_alarm'].get('xd_depot')
    out['claim_false_alarm_at_depot_tau_at_most_0.20'] = bool(fa and fa['n'] and fa['rate'] <= FA_MAX)
    return out


def analyse():
    recs = [json.loads(x) for x in SCORES.read_text().splitlines()]
    out = {'registered': 'experiments/PREREGISTRATION_XD.md (DRAFT), part XD-R', **analyse_scores(recs, thresholds())}
    SUMMARY.write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dir', type=Path, default=DATA)
    ap.add_argument('--sample', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--analyse', action='store_true')
    ap.add_argument('--port', type=int, default=8765)
    a = ap.parse_args(argv)
    folder = a.dir.expanduser()
    if a.sample:
        sample(folder)
    if a.run:
        run(folder, a.port)
    if a.analyse:
        analyse()


if __name__ == '__main__':
    main()
