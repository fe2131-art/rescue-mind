#!/usr/bin/env python3
"""T2 analysis exactly as pre-registered (experiments/PREREGISTRATION_T2.md): v3.5 vs the selected I13* config."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.i13_select import q_allows, j_allows  # noqa: E402
from scripts.t1_analysis import wilson, mcnemar_exact  # noqa: E402

RES = ROOT / 'experiments/results'


def load(tag):
    f = RES / f'devset_{tag}.json'
    return {r['image']: r for r in json.loads(f.read_text())['records']} if f.is_file() else None


def configs():
    q = {f'{p}_{v}': load(f't2_i11_{p}_{v}') for p in ('h35', 'h36') for v in ('full', 'tiles')}
    q4, j = load('t2_q4b'), load('t2_clef')
    c = {}
    for name, d in q.items():
        if d:
            c[f'Q9B[{name}] tau_h=0.05'] = (d, lambda r, im, d=d: q_allows(d[im], 0.05))
    if q4:
        c['Q4B tau_h=0.05'] = (q4, lambda r, im: q_allows(q4[im], 0.05))
    if j:
        for t in (0.35, 0.10, 0.05):
            c[f'J(Clef) tau_h={t}'] = (j, lambda r, im, t=t: j_allows(j[im], t))
        for name, d in q.items():
            if d:
                for t in (0.35, 0.05):
                    c[f'J(Clef,{t})+Q9B[{name}]'] = (d, lambda r, im, d=d, t=t: q_allows(d[im], 0.05) and j_allows(j[im], t))
        if q4:
            for t in (0.35, 0.05):
                c[f'J(Clef,{t})+Q4B'] = (q4, lambda r, im, t=t: q_allows(q4[im], 0.05) and j_allows(j[im], t))
    return c


def main():
    sel = json.loads((RES / 'i13_selection.json').read_text())['selected']['config']
    labels = {json.loads(x)['image']: json.loads(x) for x in (ROOT / 'experiments/vlm_testset_t2/labels.jsonl').read_text().splitlines()}
    imgs = [im for im, r in labels.items() if r['expected'] != 'ambiguous']
    res, dec = {}, {}
    for name, (d, rule) in configs().items():
        a = [rule(labels[im], im) for im in imgs]
        dec[name] = a
        neg = [x for x, im in zip(a, imgs) if labels[im]['expected'] == 'deny']
        pos = [x for x, im in zip(a, imgs) if labels[im]['expected'] == 'allow']
        fire = [(x, labels[im]['fire_pixels']) for x, im in zip(a, imgs) if labels[im]['hazard_visibility'] == 'visible']
        small = [x for x, px in fire if px < 10000]; large = [x for x, px in fire if px >= 10000]
        res[name] = {'false_approvals': sum(neg), 'n_deny': len(neg), 'fa_ci95': wilson(sum(neg), len(neg)),
                     'correct_approvals': sum(pos), 'n_allow': len(pos), 'ca_ci95': wilson(sum(pos), len(pos)),
                     'fire_small_refused': [len(small) - sum(small), len(small)],
                     'fire_large_refused': [len(large) - sum(large), len(large)]}
    ref = 'Q9B[h35_full] tau_h=0.05'
    for name in res:
        if name != ref and ref in dec:
            ok_ref = [x == (labels[im]['expected'] == 'allow') for x, im in zip(dec[ref], imgs)]
            ok = [x == (labels[im]['expected'] == 'allow') for x, im in zip(dec[name], imgs)]
            b = sum(r and not o for r, o in zip(ok_ref, ok)); c = sum(o and not r for r, o in zip(ok_ref, ok))
            fa_ref = [x for x, im in zip(dec[ref], imgs) if labels[im]['expected'] == 'deny']
            fa = [x for x, im in zip(dec[name], imgs) if labels[im]['expected'] == 'deny']
            bf = sum(r and not o for r, o in zip(fa_ref, fa)); cf = sum(o and not r for r, o in zip(fa_ref, fa))
            res[name]['vs_v35_correctness_mcnemar'] = [b, c, round(mcnemar_exact(b, c), 5)]
            res[name]['vs_v35_false_approval_mcnemar'] = [bf, cf, round(mcnemar_exact(bf, cf), 5)]
    out = {'registered': 'experiments/PREREGISTRATION_T2.md', 'reference': ref, 'selected': sel, 'results': res}
    (RES / 't2_summary.json').write_text(json.dumps(out, indent=1) + '\n')
    for name, r in sorted(res.items(), key=lambda kv: kv[0]):
        mark = ' <== SELECTED' if name == sel else (' <== v3.5' if name == ref else '')
        print(f"{name:34s} FA {r['false_approvals']}/{r['n_deny']}  CA {r['correct_approvals']}/{r['n_allow']}  "
              f"small fires refused {r['fire_small_refused']}  large {r['fire_large_refused']}  "
              f"FA McNemar vs v3.5 {r.get('vs_v35_false_approval_mcnemar')}{mark}")


if __name__ == '__main__':
    main()
