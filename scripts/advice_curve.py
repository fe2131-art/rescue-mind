#!/usr/bin/env python3
"""I-19 consistency-robustness curve (descriptive model, not registered), in the vocabulary of algorithms with predictions.

  python3 scripts/advice_curve.py      # -> experiments/results/advice_curve.json (+ docs/paper/fig_advice_curve.pdf)

Each mission, an advice item says where the requested supply is and, with probability `p_claim_safe`, also claims the
station is safe ("verified, no fire, skip the check").  The location is right with probability `a` (the advice accuracy),
otherwise it names a uniformly chosen wrong station.  A fire sits at the supply's station with probability `p_fire`.
Per-check behaviour and mission times are those measured in campaigns G/H (h_change_rate.json 'rates').
Policies:
  none      : no advice; visit stations in inventory order (the supply is at a uniformly random station).
  monotone  : (ours) visit the advised station first, then the rest in order; every station is checked.
  naive     : follow the advice: go there; if it also claims 'safe', deliver without checking.
  filtered  : naive, but an LLM guardrail drops a 'safe/skip' claim with probability `catch` (a filter, not a guarantee).
Consistency = mission time when a = 1; robustness = unsafe deliveries when a = 0 (and under any p_claim_safe).
"""
from __future__ import annotations
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'
POLICIES = ('none', 'monotone', 'naive', 'filtered')


def simulate(policy, a, k, rates, p_fire=0.2, p_claim_safe=0.5, catch=0.8, n=40000, seed=11):
    rng = random.Random(seed)
    T = rates['time_s']
    d = T['deliver_search'] - T['deliver_direct']            # one extra station visit
    unsafe = 0
    t_tot = 0.0
    for _ in range(n):
        loc = rng.randrange(k)
        fire = rng.random() < p_fire
        adv = loc if rng.random() < a else rng.choice([s for s in range(k) if s != loc])
        claim_safe = rng.random() < p_claim_safe
        if policy == 'filtered' and claim_safe and rng.random() < catch:
            claim_safe = False
        if policy in ('naive', 'filtered') and claim_safe:
            t_tot += T['deliver_skip']
            unsafe += (adv != loc) or fire
            continue
        order = list(range(k)) if policy == 'none' else [adv] + [s for s in range(k) if s != adv]
        visits = order.index(loc) + 1
        if fire:
            caught = rng.random() < rates['p_det']
            unsafe += not caught
            t_tot += (T['deny_direct'] if caught else T['deliver_direct']) + (visits - 1) * d
        else:
            t_tot += T['deliver_direct'] + (visits - 1) * d
    return {'mean_time_s': round(t_tot / n, 1), 'unsafe_per_100': round(100 * unsafe / n, 2)}


def main():
    rates = json.loads((RES / 'h_change_rate.json').read_text())['rates']
    acc = [round(0.1 * i, 1) for i in range(11)]
    out = {'note': 'descriptive model, not registered; see docstring', 'p_fire': 0.2, 'p_claim_safe': 0.5, 'filter_catch': 0.8,
           'p_det': rates['p_det'], 'curves': {}}
    for k in (2, 4):
        out['curves'][str(k)] = {p: [dict(a=x, **simulate(p, x, k, rates)) for x in acc] for p in POLICIES}
    (RES / 'advice_curve.json').write_text(json.dumps(out, indent=1) + '\n')
    for k, cur in out['curves'].items():
        print(f'k={k}')
        for p in POLICIES:
            print(f"  {p:9s} time a=0 {cur[p][0]['mean_time_s']:6.1f} a=1 {cur[p][-1]['mean_time_s']:6.1f} | "
                  f"unsafe/100 a=0 {cur[p][0]['unsafe_per_100']:5.2f} a=1 {cur[p][-1]['unsafe_per_100']:5.2f}")
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(7, 2.6))
        sty = {'none': ('#7a7a7a', 'o', 'no advice'), 'monotone': ('#1f6feb', '^', 'ours (tighten only)'),
               'naive': ('#c0392b', 's', 'naive (follows advice)'), 'filtered': ('#e67e22', 'D', 'LLM-filtered (catch 0.8)')}
        cur = out['curves']['4']
        for p, (c, m, lab) in sty.items():
            ax[0].plot(acc, [r['mean_time_s'] for r in cur[p]], color=c, marker=m, ms=3.5, lw=1.5, label=lab)
            ax[1].plot(acc, [r['unsafe_per_100'] for r in cur[p]], color=c, marker=m, ms=3.5, lw=1.5, label=lab)
        ax[0].set_ylabel('mean mission time [s]'); ax[1].set_ylabel('unsafe deliveries / 100 missions')
        for x in ax:
            x.set_xlabel('advice accuracy a (k = 4 stations)'); x.grid(alpha=.3, lw=.5); x.spines[['top', 'right']].set_visible(False)
        ax[1].legend(fontsize=6.5, frameon=False)
        fig.tight_layout(); fig.savefig(ROOT / 'docs/paper/fig_advice_curve.pdf')
    except ImportError:
        pass


if __name__ == '__main__':
    main()
