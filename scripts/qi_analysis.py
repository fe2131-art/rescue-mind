#!/usr/bin/env python3
"""Study QI (I-82; experiments/PREREGISTRATION_QI.md): claims QI1-QI3 from the frozen XD scoring path.

  python3 scripts/qi_analysis.py       # experiments/results/qi_summary.json   (needs devset_qi_{R,G,C}_h36_tiles.json from vlm_devset_eval.py; XD's own file is the baseline)
World score = the largest hazard score (both passes, fail-closed) over the views F, L, R (the same rule as JH and XD).  tau = 0.088 (XD rank rule, alpha = 2%, frozen), 0.05 reported (the v3.6 default).
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.x_analysis import cp_upper  # noqa: E402
from scripts.xd_analysis import hazard_score  # noqa: E402

RES = ROOT / 'experiments/results'
TAU = 0.088
TAU_DEFAULT = 0.05
VIEWS = ('F', 'L', 'R')
QI1_MAX_MISS = 20          # of 126 perceivable hard-class test worlds (XD's own: 14)
QI2_MAX_MISS_RATE = 0.20   # generated fires, per world
QI3_MAX_FALSE_STOPS = 5    # of 104 realised clean test worlds (XD's own: 0)
QI3C_MAX_FLIPS = 0.05      # control edits: share of clean twins pushed over the threshold


def world_scores(path: Path, key=lambda r: r['world_id']) -> dict:
    recs = json.loads(path.read_text())['records']
    by: dict = {}
    for r in recs:
        if r['view'] in VIEWS:
            by.setdefault(key(r), {})[r['view']] = r
    return {w: {'score': max(hazard_score(r) for r in v.values()), 'views': sorted(v), 'rec': next(iter(v.values()))} for w, v in by.items() if set(v) == set(VIEWS)}


def hard_fire(rec) -> bool:
    return rec['world_kind'] == 'hazard' and bool(rec.get('world_perceivable_any_view')) and rec['split'] == 'test'


def clean(rec) -> bool:
    return rec['world_kind'] in ('twin', 'ok') and rec['split'] == 'test'


def count(ws: dict, tau: float, fire: bool, pred) -> dict:
    sel = [w for w, x in ws.items() if pred(x['rec'])]
    bad = [w for w in sel if (x := ws[w]['score']) < tau] if fire else [w for w in sel if ws[w]['score'] >= tau]
    return {'n': len(sel), 'k': len(bad), 'upper95': round(cp_upper(len(bad), len(sel)), 4) if sel else None, 'worlds': sorted(bad)[:40]}


def main():
    out = {'registered': 'experiments/PREREGISTRATION_QI.md', 'tau': TAU}
    xd = world_scores(RES / 'devset_xd_h36_tiles.json')
    base = {'miss': count(xd, TAU, True, hard_fire), 'false_stops': count(xd, TAU, False, clean)}
    out['xd_baseline'] = base                                      # must read 14 of 126 and 0 of 104 (the JH numbers); a different number means the scoring path differs
    for tag, name in (('R', 'devset_qi_R_h36_tiles.json'), ('G', 'devset_qi_G_h36_tiles.json'), ('C', 'devset_qi_C_h36_tiles.json')):
        f = RES / name
        if not f.is_file():
            out[tag] = {'status': 'not scored'}
            continue
        ws = world_scores(f)
        if tag == 'R':
            out['R'] = {'miss': count(ws, TAU, True, hard_fire), 'false_stops': count(ws, TAU, False, clean), 'miss_at_default': count(ws, TAU_DEFAULT, True, hard_fire)}
        elif tag == 'G':
            sel = list(ws)
            k = sum(1 for w in sel if ws[w]['score'] < TAU)
            out['G'] = {'n': len(sel), 'k_miss': k, 'miss_rate': round(k / len(sel), 4) if sel else None, 'upper95': round(cp_upper(k, len(sel)), 4) if sel else None, 'worlds': sorted(w for w in sel if ws[w]['score'] < TAU)}
        else:
            sel = list(ws)
            fl = sum(1 for w in sel if ws[w]['score'] >= TAU)
            out['C'] = {'n': len(sel), 'flips': fl, 'rate': round(fl / len(sel), 4) if sel else None}
    cl = {}
    if 'miss' in out.get('R', {}):
        cl['QI1_realised_miss_not_much_worse'] = out['R']['miss']['k'] <= QI1_MAX_MISS
        cl['QI3_realised_false_stops_small'] = out['R']['false_stops']['k'] <= QI3_MAX_FALSE_STOPS
    if 'miss_rate' in out.get('G', {}):
        cl['QI2_generated_fire_miss_rate'] = out['G']['miss_rate'] <= QI2_MAX_MISS_RATE
    if out.get('C', {}).get('rate') is not None:
        cl['QI3c_control_edits_do_not_create_hazards'] = out['C']['rate'] <= QI3C_MAX_FLIPS
    # P3 (descriptive, added after the registration; no score had been seen): the judges of study JH on the generated fires and the control edits, at their own JH thresholds
    jh = json.loads((RES / 'jh_summary.json').read_text())['xd']['candidates']
    p3 = {}
    for j, c in jh.items():
        for tag in ('G', 'C'):
            f = RES / f'jev_scores_{j}_qi_{tag}.jsonl'
            if not f.is_file() or 'tau_J' not in c:
                continue
            by: dict = {}
            for line in f.read_text().splitlines():
                r = json.loads(line)
                by.setdefault(r['world'], {})[r['view']] = r['score']['max']
            ws = [max(v.values()) for v in by.values() if set(v) == set(VIEWS)]
            hit = sum(1 for x in ws if x >= c['tau_J'])
            p3.setdefault(j, {})[tag] = {'n': len(ws), 'flagged': hit, 'rate': round(hit / len(ws), 4) if ws else None, 'tau_J': c['tau_J']}
    out['P3_judges'] = p3
    out['claims'] = cl
    (RES / 'qi_summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({'xd_baseline': base['miss'] | {'worlds': '...'}, 'claims': cl}, ensure_ascii=False))


if __name__ == '__main__':
    sys.exit(main())
