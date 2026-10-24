#!/usr/bin/env python3
"""Study IJ (experiments/PREREGISTRATION_IJ.md): can a probe on the model's hidden states tell an UNKNOWN destination from the known shelter B, on name families it has never seen?

  python3 scripts/ij_analysis.py        # -> experiments/results/ij_summary.json     (needs ij_features.npz and ij_closed_set.jsonl)

Texts: experiments/intent_eval/ij_v1.jsonl (label unknown | known | none; 'unknown' is the positive class; split dev | test; family).  Everything is chosen on the DEV families only:
 * probe = standardised logistic regression on the last-token hidden state, layer and C chosen by leave-one-group-out AUROC over the dev groups (5 unknown families, the known shelter, no destination);
 * the decision threshold of every scorer = the rank rule (ceil(0.95 (m + 1))-th smallest negative score, scripts/calibration_sites.threshold, alpha 5%) over the DEV negatives' out-of-fold scores;
 * the TEST families (5 unknown families, test spelling variants of B, test no-destination texts) are scored once.
Baselines: the list rule (rescuemind.intent_llm.names_other_destination), the zero-shot yes-probability of the same model, the closed-set destination probability P(other) of the submitted parser, difference-in-means on the chosen layer.
Metrics on TEST: AUROC (unknown against known+none), unknown pass-through (share of unknown texts NOT flagged), false refusal (share of known+none texts flagged); family-bootstrap 95% intervals (resampling the 5 test families).
Claims (registered):
  IJ1  probe AUROC >= max(AUROC of the zero-shot yes-probability, AUROC of P(other)) + 0.05.
  IJ2  probe unknown pass-through <= 15% (IH's list rule leaked 9 of 20 unlisted places and 1 of 10 oriented shelters).
  IJ3  probe false refusal of known and no-destination texts <= 8% (the threshold is fixed on the dev families).
Descriptive predictions: P1 the probe passes fewer unknown texts than the list rule; P2 at least 4 of the 5 test families have pass-through <= 25%.
"""
import json
import math
import random
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from calibration_sites import threshold  # noqa: E402

RES = ROOT / 'experiments/results'
ALPHA = 0.05
IJ1_MARGIN, IJ2_MAX_PASS, IJ3_MAX_FALSE_REFUSE, P2_FAMILY_PASS = 0.05, 0.15, 0.08, 0.25
CS = (0.001, 0.01, 0.1, 1.0)
B = 2000


def auroc(pos, neg):
    if not len(pos) or not len(neg):
        return float('nan')
    allv = np.concatenate([pos, neg])
    ranks = allv.argsort().argsort() + 1.0
    # average ranks for ties
    order = allv.argsort()
    sv = allv[order]
    i = 0
    while i < len(sv):
        j = i
        while j + 1 < len(sv) and sv[j + 1] == sv[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return float((ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def load():
    rows = [json.loads(l) for l in (ROOT / 'experiments/intent_eval/ij_v1.jsonl').read_text(encoding='utf8').splitlines() if l.strip()]
    z = np.load(RES / 'ij_features.npz', allow_pickle=True)
    assert [str(t) for t in z['texts']] == [r['text'] for r in rows], 'feature file does not match the text set'
    cs = {}
    for l in (RES / 'ij_closed_set.jsonl').read_text(encoding='utf8').splitlines():
        if l.strip():
            x = json.loads(l)
            cs[x['text']] = x
    pother = np.array([cs[r['text']]['p_other'] for r in rows])
    return rows, z['H'].astype(np.float32), z['layers'], z['yes_prob'].astype(np.float64), pother


def fit_scores(Xtr, ytr, Xte, C):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    sc = StandardScaler().fit(Xtr)
    clf = LogisticRegression(C=C, max_iter=2000).fit(sc.transform(Xtr), ytr)
    return clf.decision_function(sc.transform(Xte))


def oof_scores(X, y, groups, C):
    out = np.zeros(len(y))
    for g in sorted(set(groups)):
        te = np.array([x == g for x in groups])
        out[te] = fit_scores(X[~te], y[~te], X[te], C)
    return out


def metrics(score, y, fam, thr):
    pos, neg = score[y == 1], score[y == 0]
    flagged = score >= thr
    out = {'auroc': round(auroc(pos, neg), 4), 'unknown_pass_through': round(float((~flagged[y == 1]).mean()), 4), 'false_refusal': round(float(flagged[y == 0].mean()), 4), 'threshold': float(thr), 'by_family_pass_through': {}}
    for f in sorted(set(fam[y == 1])):
        m = (fam == f) & (y == 1)
        out['by_family_pass_through'][f] = round(float((~flagged[m]).mean()), 4)
    return out


def boot_ci(score, y, fam, thr, key):
    rnd = random.Random(7)
    fams = sorted(set(fam[y == 1]))
    vals = []
    for _ in range(B):
        pick = [rnd.choice(fams) for _ in fams]
        idx = np.concatenate([np.where((fam == f) & (y == 1))[0] for f in pick] + [np.where(y == 0)[0]])
        m = metrics(score[idx], y[idx], fam[idx], thr)
        vals.append(m[key])
    vals.sort()
    return [round(vals[int(0.025 * B)], 4), round(vals[int(0.975 * B) - 1], 4)]


def analyse():
    from rescuemind.intent_llm import names_other_destination
    rows, H, layers, yes, pother = load()
    y = np.array([1 if r['label'] == 'unknown' else 0 for r in rows])
    split = np.array([r['split'] for r in rows])
    fam = np.array([r['family'] for r in rows])
    dev, test = split == 'dev', split == 'test'
    rule = np.array([1.0 if names_other_destination(r['text']) else 0.0 for r in rows])
    out = {'n_dev': int(dev.sum()), 'n_test': int(test.sum()), 'dev_groups': sorted(set(fam[dev])), 'test_groups': sorted(set(fam[test])), 'layers': [int(x) for x in layers], 'selection': {}, 'scorers': {}}
    # choose layer and C by leave-one-group-out AUROC on dev
    best = None
    for li, L in enumerate(layers):
        for C in CS:
            s = oof_scores(H[dev][:, li], y[dev], list(fam[dev]), C)
            a = auroc(s[y[dev] == 1], s[y[dev] == 0])
            out['selection'][f'layer{int(L)}_C{C}'] = round(a, 4)
            if best is None or a > best[0]:
                best = (a, li, C, s)
    a, li, C, s_dev = best
    out['chosen'] = {'layer': int(layers[li]), 'C': C, 'dev_leave_one_group_out_auroc': round(a, 4)}
    probe_test = fit_scores(H[dev][:, li], y[dev], H[test][:, li], C)
    # difference-in-means direction on the same layer (dev), standardised by dev spread
    Xd = H[dev][:, li]
    mu1, mu0 = Xd[y[dev] == 1].mean(0), Xd[y[dev] == 0].mean(0)
    w = mu1 - mu0
    dim_all = H[:, li] @ w
    scorers = {'probe': (np.concatenate([s_dev, probe_test]), None)}
    full = np.zeros(len(rows))
    full[dev], full[test] = s_dev, probe_test
    candidates = {'probe': full, 'zero_shot_yes': yes, 'closed_set_p_other': pother, 'diff_in_means': dim_all, 'list_rule': rule}
    for name, sc in candidates.items():
        # dev threshold by the rank rule over the dev negatives' (out-of-fold for the probe) scores
        neg_dev = sc[dev & (y == 0)]
        thr = threshold(list(neg_dev), ALPHA)[0] if name != 'list_rule' else 0.5
        if name != 'list_rule':
            thr = np.nextafter(thr, np.inf)          # flagged iff strictly above the rank-rule threshold (a negative at the threshold is not refused)
        m = metrics(sc[test], y[test], fam[test], thr)
        m['auroc_ci95'] = boot_ci(sc[test], y[test], fam[test], thr, 'auroc')
        m['unknown_pass_through_ci95'] = boot_ci(sc[test], y[test], fam[test], thr, 'unknown_pass_through')
        out['scorers'][name] = m
    P, ZS, PO = out['scorers']['probe'], out['scorers']['zero_shot_yes'], out['scorers']['closed_set_p_other']
    out['criteria'] = {'IJ1_probe_auroc_beats_best_baseline_by_0.05': P['auroc'] >= max(ZS['auroc'], PO['auroc']) + IJ1_MARGIN,
                       'IJ2_probe_pass_through_at_most_15pct': P['unknown_pass_through'] <= IJ2_MAX_PASS,
                       'IJ3_probe_false_refusal_at_most_8pct': P['false_refusal'] <= IJ3_MAX_FALSE_REFUSE,
                       'P1_probe_passes_fewer_than_list_rule': P['unknown_pass_through'] < out['scorers']['list_rule']['unknown_pass_through'],
                       'P2_at_least_4_of_5_test_families_pass_through_at_most_25pct': sum(v <= P2_FAMILY_PASS for v in P['by_family_pass_through'].values()) >= 4}
    (RES / 'ij_summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({'chosen': out['chosen'], 'criteria': out['criteria'], **{k: {x: v[x] for x in ('auroc', 'unknown_pass_through', 'false_refusal')} for k, v in out['scorers'].items()}}))


if __name__ == '__main__':
    analyse()
