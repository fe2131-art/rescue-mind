#!/usr/bin/env python3
"""Multiplicity over the registered primary paired closed-loop tests (I-118; POST HOC reporting, no new data).

  python3 scripts/multiplicity.py      # -> experiments/results/multiplicity.json

A statistics-minded reviewer asks what ~40 studies at p < 0.05 are worth.  The family declared here is ONE primary paired test per closed-loop study that registered one (the exact McNemar p-value of its own
summary file; one-sided where the study registered a direction): A (A1), F, G, GR, GC, GD, GL, GM, H (P2), V (V4), J (P3), JK, and JL once it exists.  Holm-Bonferroni (family-wise error 5%) and
Benjamini-Hochberg (false discovery rate 5%) are applied over the family.  Tests that were not significant before the correction are listed with their raw p-value and stay failed claims where they were claims.
Dependence: GM, JK and JL share worlds (JK and GM) or design (JL); JL is the fresh-world, interleaved confirmation of JK.  The correction treats the tests as exchangeable p-values; it is a stress test, not a model of that dependence.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'
SPECS = [  # (study, file, path of the p-value inside the summary, what it compares)
    ('A', 'a_summary.json', ('A1_unsafe_naive_vs_monotone', 'mcnemar_p'), 'unsafe worlds, naive advice against ours'),
    ('F', 'f_summary.json', ('primary', 'mcnemar_p'), 'first closed-loop look-around comparison'),
    ('G', 'g_summary.json', ('primary', 'mcnemar_p'), 'deliveries into fire, no look-around against look-around'),
    ('GR', 'gr_summary.json', ('paired', 'mcnemar_p'), 'same, fresh worlds'),
    ('GC', 'gc_summary.json', ('paired', 'mcnemar_p'), 'site-calibrated threshold against default, arena'),
    ('GD', 'gd_summary.json', ('paired', 'mcnemar_p'), 'site-calibrated threshold against default, depot'),
    ('GL', 'gl_summary.json', ('paired', 'mcnemar_one_sided_p'), 'left-only 0.8 m look-around against v3.6, depot'),
    ('GM', 'gm_summary.json', ('paired', 'mcnemar_one_sided_p'), 'the same under changed rendering'),
    ('H', 'h_summary.json', ('P2_safety_naive_vs_verified', 'mcnemar_p'), 'unsafe missions, naive memory against verified memory'),
    ('V', 'v_summary.json', ('V4_safety', 'seq_mcnemar_M1_vs_M2_p'), 'unsafe missions, verified memory against none'),
    ('J', 'j_summary.json', ('P3_correct_paired', 'mcnemar_p'), 'two-model check against one model'),
    ('JK', 'jk_summary.json', ('paired_v36_vs_adapt', 'mcnemar_one_sided_p_a_worse'), 'suspicion-triggered extra views against v3.6, depot'),
    ('JL', 'jl_summary.json', ('paired', 'mcnemar_one_sided_p'), 'the same on fresh worlds, interleaved'),
]
ALPHA = 0.05


def get(d, path):
    for k in path:
        d = d[k]
    return d


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    m, out, running = len(ps), [None] * len(ps), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * ps[i]))
        out[i] = running
    return out


def bh(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i], reverse=True)
    m, out, running = len(ps), [None] * len(ps), 1.0
    for k, i in enumerate(order):
        rank = m - k
        running = min(running, min(1.0, ps[i] * m / rank))
        out[i] = running
    return out


def main():
    rows = []
    for study, f, path, what in SPECS:
        p = RES / f
        if not p.is_file():
            continue
        rows.append({'study': study, 'file': f, 'p_raw': float(get(json.loads(p.read_text(encoding='utf8')), path)), 'compares': what})
    ps = [r['p_raw'] for r in rows]
    for r, h, b in zip(rows, holm(ps), bh(ps)):
        r['p_holm'], r['q_bh'] = round(h, 5), round(b, 5)
        r['significant_raw'], r['significant_holm'], r['significant_bh'] = r['p_raw'] < ALPHA, h < ALPHA, b < ALPHA
    out = {'post_hoc': True, 'alpha': ALPHA, 'm': len(rows), 'raw_significant': sum(r['significant_raw'] for r in rows), 'holm_significant': sum(r['significant_holm'] for r in rows),
           'bh_significant': sum(r['significant_bh'] for r in rows), 'tests': rows,
           'lost_by_holm': [r['study'] for r in rows if r['significant_raw'] and not r['significant_holm']]}
    (RES / 'multiplicity.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    for r in rows:
        print(f"{r['study']:3s} p={r['p_raw']:<9.5g} holm={r['p_holm']:<8.5g} bh={r['q_bh']:<8.5g} {'RAW' if r['significant_raw'] else '   '} {'HOLM' if r['significant_holm'] else '    '} {r['compares']}")
    print({k: out[k] for k in ('m', 'raw_significant', 'holm_significant', 'bh_significant', 'lost_by_holm')})


if __name__ == '__main__':
    main()
