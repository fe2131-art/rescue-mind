#!/usr/bin/env python3
"""How independent are the gate's misses and a second judge's misses?  (I-118; POST HOC on registered data: JI (fresh worlds) and XD (JH test split, by base world); no new data.)

  python3 scripts/diversity_measures.py      # -> experiments/results/diversity_measures.json

For every pair (gate, judge) and each view set, on the perceivable fire worlds, with the registered thresholds (ji_thresholds.json for JI; the XD calibration of jh_views.json logic for XD), the classical oracle-based measures of
classifier-ensemble diversity (Kuncheva and Whitaker, 2003): the double-fault rate P(both miss), the independence prediction P(gate misses) x P(judge misses), the Q statistic and the disagreement.
Confidence intervals: bootstrap over worlds (JI) or over BASE worlds (XD: ablation copies are not independent).  No claim; it makes the finding 'a second judge adds almost nothing' quantitative.
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
import ji_analysis as jia  # noqa: E402
import cascade_dev as cd  # noqa: E402
import jh_analysis as ja  # noqa: E402

RES = ROOT / 'experiments/results'
JUDGES = ('internvl3', 'idefics3', 'qwen3vl', 'smolvlm2')
B = 4000


def measures(a, b):
    """a, b: lists of 0/1 'missed' flags over clusters."""
    n = len(a)
    n11 = sum(x and y for x, y in zip(a, b))
    n00 = sum((not x) and (not y) for x, y in zip(a, b))
    n10 = sum(x and (not y) for x, y in zip(a, b))
    n01 = sum((not x) and y for x, y in zip(a, b))
    pa, pb = (n11 + n10) / n, (n11 + n01) / n
    q = ((n11 * n00 - n10 * n01) / (n11 * n00 + n10 * n01)) if (n11 * n00 + n10 * n01) else None
    return {'p_gate_miss': pa, 'p_judge_miss': pb, 'double_fault': n11 / n, 'independence': pa * pb, 'Q': q, 'disagreement': (n10 + n01) / n,
            'n_both_miss': n11, 'n_gate_only': n10, 'n_judge_only': n01}


def boot(a, b, key, seed=1):
    rnd = random.Random(seed)
    n = len(a)
    vals = []
    for _ in range(B):
        idx = [rnd.randrange(n) for _ in range(n)]
        m = measures([a[i] for i in idx], [b[i] for i in idx])
        if m[key] is not None:
            vals.append(m[key])
    vals.sort()
    return [round(vals[int(0.025 * len(vals))], 4), round(vals[int(0.975 * len(vals)) - 1], 4)] if vals else None


def summarize(miss, clusters):
    """miss[scorer][world] -> 0/1; clusters: list of lists of worlds (one list per independent unit)."""
    out = {}
    flags = lambda s: [int(sum(miss[s][w] for w in c) > 0) if False else int(all(miss[s][w] for w in c)) for c in clusters]   # a base world is 'missed' when every copy is missed
    g = flags('qwen35')
    for j in JUDGES:
        jf = flags(j)
        m = measures(g, jf)
        m['double_fault_ci95'] = boot(g, jf, 'double_fault')
        m['excess_double_fault_over_independence'] = round(m['double_fault'] - m['independence'], 4)
        out[j] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in m.items()}
    return out


def ji():
    thr = json.loads((ROOT / 'experiments/ji_thresholds.json').read_text())
    sc, kind = jia.load_scores()
    fire = sorted(w for w, k in kind.items() if k == 'fire')
    res = {}
    for vs in ('v36_FLR', 'all_six'):
        views, tau = thr['viewsets'][vs], thr['tau'][vs]
        miss = {}
        for s in ('qwen35',) + JUDGES:
            pw = {}
            for (w, v), x in sc[s].items():
                if v in views:
                    pw[w] = max(pw.get(w, 0.0), x)
            miss[s] = {w: int(pw.get(w, 0.0) < tau[s]) for w in fire}
        res[vs] = {'n_clusters': len(fire), 'pairs': summarize(miss, [[w] for w in fire])}
    return res


def xd():
    rows, info = cd.load_xd()
    kind = lambda w: 'fire' if (info[w]['world_kind'] == 'hazard' and info[w].get('world_perceivable_any_view')) else ('clean' if info[w]['world_kind'] in ('twin', 'ok') else 'other')
    cal = [w for w in info if info[w]['split'] == 'cal' and kind(w) == 'clean']
    fire = [w for w in info if info[w]['split'] == 'test' and kind(w) == 'fire']
    base = lambda w: info[w].get('ablation_base') or w
    groups = {}
    for w in fire:
        groups.setdefault(base(w), []).append(w)
    res = {}
    for name, views in (('v36_FLR', ('F', 'L', 'R')), ('all_six', ('F', 'L', 'R', 'L2', 'R2', 'N'))):
        miss = {}
        for s in ('qwen35',) + JUDGES:
            pw = cd.pmax(rows[s], views)
            tau = ja.tau_of([pw.get(w, 0.0) for w in cal])
            miss[s] = {w: int(pw.get(w, 0.0) < tau) for w in fire}
        res[name] = {'n_clusters': len(groups), 'n_images_worlds': len(fire), 'pairs': summarize(miss, list(groups.values()))}
    return res


def main():
    out = {'post_hoc': True, 'bootstrap': B, 'JI': ji(), 'XD_by_base_world': xd()}
    (RES / 'diversity_measures.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    for ds in ('JI', 'XD_by_base_world'):
        for vs, r in out[ds].items():
            print(ds, vs, 'clusters', r['n_clusters'])
            for j, m in r['pairs'].items():
                print('   ', j, {k: m[k] for k in ('p_gate_miss', 'p_judge_miss', 'double_fault', 'independence', 'Q', 'disagreement', 'double_fault_ci95')})


if __name__ == '__main__':
    main()
