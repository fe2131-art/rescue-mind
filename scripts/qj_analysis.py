#!/usr/bin/env python3
"""Study QJ (I-90; experiments/PREREGISTRATION_QJ.md): claims QJ1-QJ3 from the frozen scoring path (needs devset_qj_{N0,NF,NB}_h36_tiles.json and qj_audit.json).

  python3 scripts/qj_analysis.py        # experiments/results/qj_summary.json
Image score = the largest hazard probability over both passes (fail-closed), ONE view (there is no robot): tau = 0.088 (XD rank rule over three views, frozen; a single view needs a lower value in principle, so the miss is, if anything, pessimistic), 0.05 reported.
QJ1: clean false stops <= 6 of 120 (5%).  QJ2 (positive control, large fire): miss <= 10% of the NB images.  QJ3 (hard class, small hidden fire): miss <= 20% of the NF images.
Amendment 1: the whole-frame flame-colour audit does not separate clean from fire images (pilot: N0 up to 0.081, NF 0.0013-0.0118), so the claims run over ALL images of a mode.  Registered stop rule (as QI2), from a by-eye sample:
40 images per fire mode drawn with a seeded RNG, classified fire-present / not BEFORE any gate score is read (`experiments/results/qj_byeye.json`: {"NF": {"n": 40, "present": k}, "NB": {...}}); if fewer than 85% of the sample show a fire, that mode's claim stops and does not hold.  Without that file the claims are not evaluated.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from scripts.x_analysis import cp_upper  # noqa: E402
from scripts.xd_analysis import hazard_score  # noqa: E402

RES = ROOT / 'experiments/results'
TAU, TAU_DEFAULT = 0.088, 0.05
QJ1_MAX_FALSE_STOPS = 6
QJ2_MAX_MISS_RATE = 0.10
QJ3_MAX_MISS_RATE = 0.20
MIN_AUDITED_SHARE = 0.85


def load(mode: str) -> list:
    f = RES / f'devset_qj_{mode}_h36_tiles.json'
    return json.loads(f.read_text())['records'] if f.is_file() else []


def count(scores: list, tau: float, miss: bool) -> dict:
    k = sum((s < tau) if miss else (s >= tau) for s in scores)
    return {'k': k, 'n': len(scores), 'rate': round(k / len(scores), 4) if scores else None, 'upper95': round(cp_upper(k, len(scores)), 4) if scores else None}


def main():
    out, cl = {}, {}
    recs = {m: load(m) for m in ('N0', 'NF', 'NB')}
    if recs['N0']:
        sc = [hazard_score(r) for r in recs['N0']]
        out['N0'] = {'false_stops': count(sc, TAU, False), 'false_stops_default': count(sc, TAU_DEFAULT, False)}
        cl['QJ1_clean_false_stops_at_most_5pct'] = out['N0']['false_stops']['k'] <= QJ1_MAX_FALSE_STOPS
    for mode, key, lim in (('NB', 'QJ2_large_fire_miss_at_most_10pct', QJ2_MAX_MISS_RATE), ('NF', 'QJ3_hard_fire_miss_at_most_20pct', QJ3_MAX_MISS_RATE)):
        if not recs[mode]:
            continue
        allsc = [hazard_score(r) for r in recs[mode]]
        bf = RES / 'qj_byeye.json'
        bye = json.loads(bf.read_text()).get(mode) if bf.is_file() else None
        share = (bye['present'] / bye['n']) if bye and bye.get('n') else None
        out[mode] = {'all': count(allsc, TAU, True), 'at_default': count(allsc, TAU_DEFAULT, True), 'byeye_sample': bye, 'byeye_present_share': round(share, 4) if share is not None else None,
                     'claim_stopped': share is not None and share < MIN_AUDITED_SHARE,
                     'by_template': {f'{i}/{li}': count([hazard_score(r) for r in recs[mode] if (r['qj_item'], r['qj_light']) == (i, li)], TAU, True) for i in ('water', 'medicine') for li in range(3)}}
        if share is not None:
            cl[key] = (not out[mode]['claim_stopped']) and out[mode]['all']['rate'] <= lim
    out['claims'] = cl
    (RES / 'qj_summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({'claims': cl, **{k: v for k, v in out.items() if k != 'claims'}}, ensure_ascii=False)[:1500])


if __name__ == '__main__':
    sys.exit(main())
