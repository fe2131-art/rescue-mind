#!/usr/bin/env python3
"""Study R analysis exactly as pre-registered (experiments/PREREGISTRATION_R.md).

  python3 scripts/r_analysis.py      # -> experiments/results/r_summary.json (+ docs/paper/tab_r.tex)
"""
from __future__ import annotations
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.i13_select import q_allows  # noqa: E402
from scripts.t1_analysis import wilson, mcnemar_exact  # noqa: E402
from rescuemind.corruptions import CONDITIONS  # noqa: E402

RES = ROOT / 'experiments/results'
NAMES = {'gaussian_noise': 'Sensor noise', 'motion_blur': 'Motion blur', 'defocus_blur': 'Defocus',
         'underexposure': 'Under-exposure', 'overexposure': 'Over-exposure', 'jpeg': 'JPEG'}


def decide(r):
    """Gate rejection or any pass error = refusal (fail-closed), otherwise the v3.6 offline rule."""
    if not (r.get('quality') or {}).get('quality_ok', True):
        return False
    return q_allows(r, 0.05)


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = run
    return adj


def main():
    clean = {r['image']: r for r in json.loads((RES / 'devset_t2_i11_h36_tiles.json').read_text())['records']}
    conds = {c: json.loads((RES / f'devset_r_{c}.json').read_text())['records'] for c in CONDITIONS
             if (RES / f'devset_r_{c}.json').is_file()}
    if len(conds) != len(CONDITIONS):
        print('WARNING: missing conditions', sorted(set(CONDITIONS) - set(conds)))
    imgs = [r['image'] for r in next(iter(conds.values())) if r['expected'] != 'ambiguous']
    lab = {im: clean[im] for im in imgs}
    deny = [im for im in imgs if lab[im]['expected'] == 'deny']
    allow = [im for im in imgs if lab[im]['expected'] == 'allow']
    fire = [im for im in deny if lab[im].get('truth_hazard_visible')]
    c_dec = {im: q_allows(clean[im], 0.05) for im in imgs}
    out = {'registered': 'experiments/PREREGISTRATION_R.md', 'n_images': len(imgs), 'n_deny': len(deny), 'n_allow': len(allow),
           'n_visible_fire': len(fire), 'n_worlds': len({lab[im]['world_id'] for im in imgs}),
           'clean': {'false_approvals': sum(c_dec[im] for im in deny), 'correct_approvals': sum(c_dec[im] for im in allow),
                     'fire_missed': sum(c_dec[im] for im in fire)}, 'conditions': {}}
    pooled = []                   # (world, is_fa) over every condition x deny image
    ps = []
    for c, recs in conds.items():
        by = {r['image']: r for r in recs}
        d = {im: decide(by[im]) for im in imgs}
        fa = sum(d[im] for im in deny); ca = sum(d[im] for im in allow)
        b = sum(d[im] and not c_dec[im] for im in deny)      # newly approved under degradation
        cc = sum(c_dec[im] and not d[im] for im in deny)
        p = mcnemar_exact(b, cc)
        ps.append(p)
        lat = sorted(by[im]['passes']['1'].get('latency_s', 0) + by[im]['passes']['2'].get('latency_s', 0) for im in imgs)
        out['conditions'][c] = {'false_approvals': fa, 'fa_ci95': wilson(fa, len(deny)), 'correct_approvals': ca,
                                'ca_rate': round(ca / len(allow), 4), 'ca_ci95': wilson(ca, len(allow)),
                                'fire_missed': sum(d[im] for im in fire), 'supply_false_approvals': sum(d[im] for im in deny if im not in fire),
                                'gate_rejected': sum(not (by[im].get('quality') or {}).get('quality_ok', True) for im in imgs),
                                'errors': sum(any('error' in by[im]['passes'][k] for k in '12') for im in imgs),
                                'fa_newly_approved_vs_clean': b, 'fa_newly_refused_vs_clean': cc, 'mcnemar_p': round(p, 5),
                                'latency_median_s': lat[len(lat) // 2]}
        pooled += [(lab[im]['world_id'], d[im]) for im in deny]
    for c, a in zip(conds, holm(ps)):
        o = out['conditions'][c]
        o['mcnemar_p_holm'] = round(a, 5)
        o['unsafe_degradation'] = o['fa_newly_approved_vs_clean'] > o['fa_newly_refused_vs_clean'] and a < .05
    # P1: pooled FA with a world-cluster bootstrap (4000 draws, seed 7)
    worlds = sorted({w for w, _ in pooled})
    agg = {w: [0, 0] for w in worlds}
    for w, x in pooled:
        agg[w][0] += x; agg[w][1] += 1
    rng = random.Random(7)
    boots = []
    for _ in range(4000):
        s = [agg[worlds[rng.randrange(len(worlds))]] for _ in worlds]
        boots.append(sum(x[0] for x in s) / sum(x[1] for x in s))
    boots.sort()
    k = sum(x for _, x in pooled)
    ci = [round(boots[int(.025 * 4000)], 5), round(boots[int(.975 * 4000) - 1], 5)]
    out['P1_pooled'] = {'false_approvals': k, 'n': len(pooled), 'rate': round(k / len(pooled), 5), 'cluster_ci95': ci,
                        'wilson_ci95': wilson(k, len(pooled)), 'supported': ci[1] < .02}
    out['P2_unsafe_conditions'] = [c for c, o in out['conditions'].items() if o['unsafe_degradation']]
    (RES / 'r_summary.json').write_text(json.dumps(out, indent=1) + '\n')
    rows = []
    for fam in NAMES:
        for sev in ('M', 'S'):
            o = out['conditions'].get(f'{fam}_{sev}')
            if o:
                rows.append(f"{NAMES[fam]} & {sev} & {o['false_approvals']}/{len(deny)} & {o['fire_missed']}/{len(fire)} & "
                            f"{o['correct_approvals']}/{len(allow)} & {o['gate_rejected']} \\\\")
    cl = out['clean']
    tex = ('\\begin{tabular}{llrrrr}\\toprule\nDegradation & Sev. & False appr. & Fire missed & Correct appr. & Gate rej. \\\\\\midrule\n'
           f"None (clean) & -- & {cl['false_approvals']}/{len(deny)} & {cl['fire_missed']}/{len(fire)} & {cl['correct_approvals']}/{len(allow)} & 0 \\\\\\midrule\n"
           + '\n'.join(rows) + '\n\\bottomrule\\end{tabular}\n')
    (ROOT / 'docs/paper/tab_r.tex').write_text(tex)
    print(json.dumps({k: v for k, v in out.items() if k != 'conditions'}, indent=1))
    for c, o in out['conditions'].items():
        print(f"{c:18s} FA {o['false_approvals']:3d}  fire_missed {o['fire_missed']:2d}  CA {o['correct_approvals']:3d}/{len(allow)}  gate {o['gate_rejected']:3d}  p_holm {o['mcnemar_p_holm']}")


if __name__ == '__main__':
    main()
