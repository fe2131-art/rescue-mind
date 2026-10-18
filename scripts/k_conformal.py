#!/usr/bin/env python3
"""Study K (experiments/PREREGISTRATION_K.md): split-conformal calibration of the hazard threshold on stored scores.
Offline: no GPU, no inference.  Output: experiments/results/k_summary.json"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

from scipy.stats import beta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from i13_select import q_allows  # noqa: E402
from t1_analysis import wilson  # noqa: E402

RES = ROOT / 'experiments/results'
ALPHAS = (0.05, 0.10)
DELTA = 0.10
TAU_H = 0.05
TAU_CAUTION = 0.01      # the memory / advice caution threshold (rescuemind.mission_memory.CAUTION_TAU_H)


def load(tag):
    return json.loads((RES / f'devset_{tag}_i11_h36_tiles.json').read_text())['records']


def ph(r):
    return r['passes']['1']['scores']['hazard_prob']


def tau_marginal(scores, alpha, conservative=False):
    n = len(scores)
    k = math.floor(alpha * (n + 1)) + (0 if conservative else 1)
    s = sorted(scores)
    return (s[k - 1], k) if 1 <= k <= n else (0.0, k)


def tau_pac(scores, alpha, delta=DELTA):
    n = len(scores)
    ks = [k for k in range(1, n + 1) if beta.cdf(alpha, k, n + 1 - k) >= 1 - delta]
    if not ks:
        return 0.0, 0
    k = max(ks)
    return sorted(scores)[k - 1], k


def rate(k, n):
    return {'k': k, 'n': n, 'rate': round(k / n, 4) if n else None, 'ci95': wilson(k, n)}


def evaluate(tau, cal, fire, free, allow_all, deny_all):
    out = {'tau': tau,
           'cal_miss': rate(sum(p < tau for p in cal), len(cal)),
           'heldout_miss': rate(sum(ph(r) < tau for r in fire), len(fire)),
           'heldout_false_alarm': rate(sum(ph(r) >= tau for r in free), len(free)),
           'heldout_correct_approval': rate(sum(q_allows(r, tau) for r in allow_all), len(allow_all)),
           'heldout_false_approvals': rate(sum(q_allows(r, tau) for r in deny_all), len(deny_all))}
    return out


def main():
    dev = load('dh') + load('dh2')
    cal = [ph(r) for r in dev if r.get('hazard_visibility') == 'visible']
    t2 = load('t2')
    fire = [r for r in t2 if r.get('hazard_visibility') == 'visible']
    free = [r for r in t2 if r.get('hazard_visibility') == 'hidden' and r['expected'] == 'allow']
    allow_all = [r for r in t2 if r['expected'] == 'allow']
    deny_all = [r for r in t2 if r['expected'] == 'deny']
    small = lambda rs: sum(r['fire_pixels'] < 10000 for r in rs)
    dev_fire = [r for r in dev if r.get('hazard_visibility') == 'visible']
    out = {'n_cal': len(cal), 'n_fire': len(fire), 'n_free': len(free), 'n_allow': len(allow_all), 'n_deny': len(deny_all),
           'delta': DELTA, 'small_fire_frac': {'cal': round(small(dev_fire) / len(dev_fire), 4),
                                              'heldout': round(small(fire) / len(fire), 4)},
           'frozen': {'tau_h': TAU_H, **evaluate(TAU_H, cal, fire, free, allow_all, deny_all)}, 'alphas': {}}
    # I-19 proof review: the per-view false-alarm rate delta of the CAUTION threshold itself (not of the conformal tau 0.0113)
    out['caution'] = {'tau': TAU_CAUTION, 'heldout_false_alarm': rate(sum(ph(r) >= TAU_CAUTION for r in free), len(free)),
                      'n_fire_visible_missed': sum(ph(r) < TAU_CAUTION for r in fire)}
    for a in ALPHAS:
        res = {}
        for name, (tau, k) in (('K_PAC', tau_pac(cal, a)), ('K_marginal', tau_marginal(cal, a)),
                               ('K_marginal_1', tau_marginal(cal, a, True))):
            e = evaluate(tau, cal, fire, free, allow_all, deny_all)
            e['k'] = k
            e['guarantee_holds_heldout'] = e['heldout_miss']['rate'] <= a
            res[name] = e
        out['alphas'][str(a)] = res
    (RES / 'k_summary.json').write_text(json.dumps(out, indent=1) + '\n')
    f = out['frozen']
    print(f"cal n={len(cal)} fire n={len(fire)} free n={len(free)}  small-fire frac cal/heldout {out['small_fire_frac']}")
    print(f"frozen tau 0.05: miss {f['heldout_miss']['k']}/{len(fire)}  FA {f['heldout_false_alarm']['k']}/{len(free)}  "
          f"CA {f['heldout_correct_approval']['k']}/{len(allow_all)}  FApprov {f['heldout_false_approvals']['k']}/{len(deny_all)}")
    for a, res in out['alphas'].items():
        for name, e in res.items():
            print(f"alpha {a} {name:12s} k={e['k']:3d} tau={e['tau']:.4f} cal-miss {e['cal_miss']['k']}/{len(cal)} "
                  f"heldout-miss {e['heldout_miss']['k']}/{len(fire)} ({e['heldout_miss']['rate']}) holds={e['guarantee_holds_heldout']} "
                  f"FA {e['heldout_false_alarm']['k']}/{len(free)} CA {e['heldout_correct_approval']['k']}/{len(allow_all)} "
                  f"FApprov {e['heldout_false_approvals']['k']}/{len(deny_all)}")


if __name__ == '__main__':
    main()
