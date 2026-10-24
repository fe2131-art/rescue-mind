#!/usr/bin/env python3
"""Is the gate's deficit on hidden fires only a SIZE effect?  (I-118; POST HOC on registered image sets JI and XD; no new data; answers a reviewer question raised by SmokeBench, which finds that size matters more than contrast.)

  python3 scripts/size_vs_hidden.py      # -> experiments/results/size_vs_hidden.json

Unit: one fire image (a fire world seen from one view).  `fire_pixels` is the area of the fire-only render (what the fire would cover with no occluder), `hazard_visibility` says whether the fire is visible in the actual image
('visible') or occluded ('hidden' / 'ambiguous').  Flagged = the gate's per-image hazard score (both passes, tiles; scripts/xd_analysis.hazard_score) >= the frozen per-image threshold 0.088.
Stratified by fire-only area (12 equal-count bins over all fire images), the Mantel-Haenszel common odds ratio of 'flagged' for visible against hidden fires answers: at the same potential size, does visibility change the flag rate?
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from xd_analysis import hazard_score  # noqa: E402

RES = ROOT / 'experiments/results'
TAU = 0.088
NBINS = 12          # equal-count bins of the fire-only area over all fire images of the set (hidden fires all fall in the smallest ones, so the bins must be fine there)


def load(name):
    labels = {json.loads(l)['image']: json.loads(l) for l in (ROOT / f'experiments/vlm_testset_{name}/labels.jsonl').read_text(encoding='utf8').splitlines() if l.strip()}
    recs = json.loads((RES / f'devset_{name}_h36_tiles.json').read_text(encoding='utf8'))['records']
    out = []
    for r in recs:
        lab = labels.get(r['image'], r)
        if r.get('world_kind') != 'hazard' or not r.get('fire_pixels'):
            continue
        out.append({'pix': int(r['fire_pixels']), 'vis': r.get('hazard_visibility'), 'flag': hazard_score(r) >= TAU, 'view': r['view']})
    return out


def mh(strata):
    """Mantel-Haenszel common odds ratio (visible vs hidden, outcome flagged) with the Robins-Breslow-Greenland 95% CI; strata of (a,b,c,d) = (vis flagged, vis not, hid flagged, hid not)."""
    num = sum(a * d / (a + b + c + d) for a, b, c, d in strata)
    den = sum(b * c / (a + b + c + d) for a, b, c, d in strata)
    if den == 0 or num == 0:
        return None
    orr = num / den
    r_ = [a * d / (a + b + c + d) for a, b, c, d in strata]
    s_ = [b * c / (a + b + c + d) for a, b, c, d in strata]
    p_ = [(a + d) / (a + b + c + d) for a, b, c, d in strata]
    q_ = [(b + c) / (a + b + c + d) for a, b, c, d in strata]
    R, S = sum(r_), sum(s_)
    var = sum(p * r for p, r in zip(p_, r_)) / (2 * R * R) + sum(p * s + q * r for p, q, r, s in zip(p_, q_, r_, s_)) / (2 * R * S) + sum(q * s for q, s in zip(q_, s_)) / (2 * S * S)
    se = math.sqrt(var)
    return {'or': round(orr, 2), 'ci95': [round(orr * math.exp(-1.96 * se), 2), round(orr * math.exp(1.96 * se), 2)]}


def analyse(rows):
    pix = sorted(r['pix'] for r in rows)
    cuts = [pix[len(pix) * k // NBINS] for k in range(1, NBINS)]
    bin_of = lambda p: sum(p > c for c in cuts)
    table, strata = [], []
    for b in range(NBINS):
        row = {'bin': b, 'pixels_min': min([r['pix'] for r in rows if bin_of(r['pix']) == b] or [0]), 'pixels_max': max([r['pix'] for r in rows if bin_of(r['pix']) == b] or [0])}
        cell = {}
        for grp, test in (('visible', lambda r: r['vis'] == 'visible'), ('hidden_or_ambiguous', lambda r: r['vis'] != 'visible')):
            xs = [r for r in rows if bin_of(r['pix']) == b and test(r)]
            cell[grp] = {'n': len(xs), 'flagged': sum(r['flag'] for r in xs), 'rate': round(sum(r['flag'] for r in xs) / len(xs), 3) if xs else None}
        row.update(cell)
        table.append(row)
        a, bb = cell['visible']['flagged'], cell['visible']['n'] - cell['visible']['flagged']
        c, d = cell['hidden_or_ambiguous']['flagged'], cell['hidden_or_ambiguous']['n'] - cell['hidden_or_ambiguous']['flagged']
        if a + bb and c + d:
            strata.append((a + 0.5, bb + 0.5, c + 0.5, d + 0.5))          # 0.5 continuity correction (cells can be empty)
    allv = [r for r in rows if r['vis'] == 'visible']
    allh = [r for r in rows if r['vis'] != 'visible']
    return {'n_fire_images': len(rows), 'area_cuts_pixels': cuts, 'bins': table, 'mantel_haenszel_visible_vs_hidden': mh(strata),
            'overall': {'visible': {'n': len(allv), 'rate': round(sum(r['flag'] for r in allv) / len(allv), 3) if allv else None}, 'hidden_or_ambiguous': {'n': len(allh), 'rate': round(sum(r['flag'] for r in allh) / len(allh), 3) if allh else None}}}


def main():
    out = {'post_hoc': True, 'threshold': TAU, 'JI': analyse(load('ji')), 'XD': analyse(load('xd'))}
    (RES / 'size_vs_hidden.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    for ds in ('JI', 'XD'):
        r = out[ds]
        print(ds, r['n_fire_images'], 'overall', r['overall'], 'MH', r['mantel_haenszel_visible_vs_hidden'])
        for b in r['bins']:
            print('   ', b['pixels_min'], '-', b['pixels_max'], 'visible', b['visible'], 'hidden', b['hidden_or_ambiguous'])


if __name__ == '__main__':
    main()
