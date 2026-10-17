#!/usr/bin/env python3
"""I-24 descriptive model (not registered): the price of advice over a horizon of missions, with and without credit.

  python3 scripts/advice_credit_horizon.py   # -> experiments/results/advice_credit_horizon.json, docs/paper/fig_advice_credit.pdf

Drives the REAL rule (rescuemind.advice.plan through rescuemind.advice_credit.plan_with_credit, and settle) with
synthetic station outcomes.  Per-check behaviour and times come from campaigns G/H (h_change_rate.json) and study K
(per-view false-alarm rate delta at the caution threshold).
World per mission: k stations, one holds the requested supply (uniform); fire at that station with prob p_fire.
Sources (one per run, channel 'peer'):
  honest    : location advice always right (names the supply station)
  noisy     : right with prob 0.7, else a uniformly wrong station
  liar      : always names a wrong station
  farmer    : adaptive; reads the ledger and lies whenever its location credit can pay for a lie, else tells the truth
  flooder   : names the supply station as burning at every mission (hazard advice; costs only false refusals)
A wrong reorder costs one visit; a caution-only refusal happens with prob 1-(1-delta)^3 (three views at the caution
threshold); with soft refusal it costs a visit and the robot goes on (a refused unique supply ends the mission).
Unsafe deliveries are computed for completeness: credit only removes advice, so they cannot differ from the
no-credit monotone rule (same random stream).
"""
from __future__ import annotations
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind import advice_credit as ac            # noqa: E402
from rescuemind.stations import StationSet           # noqa: E402

RES = ROOT / 'experiments/results'
SOURCES = ('honest', 'noisy', 'liar', 'farmer', 'flooder')


def station_set(k):
    if k == 2:
        return None, ('water', 'medicine')
    ids = [f'S{i + 1}' for i in range(k)]
    return StationSet.build(ids, {s: ('water' if i % 2 == 0 else 'medicine') for i, s in enumerate(ids)}), tuple(ids)


def run(source, k, credit, rates, delta, m=100, p_fire=0.2, seed=3, **params):
    rng = random.Random(seed)
    ss, ids = station_set(k)
    T = rates['time_s']
    W = T['deliver_search'] - T['deliver_direct']
    led = ac.new_ledger(**params)
    cum_extra, cum_refusal, unsafe, series = 0.0, 0, 0, []
    p_false = 1 - (1 - delta) ** 3
    for _ in range(m):
        item = 'water'
        true = rng.choice(ids)                         # the station really holding the request (inventory may be stale)
        fire = rng.random() < p_fire
        u_det, u_fa, u_adv = rng.random(), rng.random(), rng.random()
        wrong = [s for s in ids if s != true]
        if source == 'honest':
            items = [{'source': 'peer', 'kind': 'location', 'station': true, 'text': ''}]
        elif source == 'noisy':
            rng.random()
            items = [{'source': 'peer', 'kind': 'location', 'station': true if u_adv < .7 else rng.choice(wrong), 'text': ''}]
        elif source == 'liar':
            items = [{'source': 'peer', 'kind': 'location', 'station': rng.choice(wrong), 'text': ''}]
        elif source == 'farmer':
            acc = led['sources'].get('peer') or {'loc': led['params']['c_loc']}
            lie = acc['loc'] >= 1.0 if credit else True
            w = rng.choice(wrong)                      # drawn either way: keeps the world stream identical across arms
            items = [{'source': 'peer', 'kind': 'location', 'station': w if lie else true, 'text': ''}]
        else:
            items = [{'source': 'peer', 'kind': 'hazard', 'station': true, 'text': ''}]
        base_order = list(ss.default_order(item)) if ss else ['water', 'medicine']
        if credit:
            plan = ac.plan_with_credit(led, item, items, 'monotone', stations=ss)
        else:
            from rescuemind import advice
            plan = advice.plan(item, items, 'monotone', stations=ss)
        order = plan.get('order') or [plan['first_station']] + [s for s in ids if s != plan['first_station']]
        # cost relative to the no-advice inventory order, in wasted visits
        extra_visits = order.index(true) - base_order.index(true)
        caution = true in (plan.get('caution') or {})
        visits = []
        for st in order[:order.index(true) + 1]:
            if st != true:
                visits.append(dict(station=st, supply_match=False, refused=False, refused_base=False))
            else:
                refused_fire = fire and u_det < rates['p_det']
                false_ref = caution and not fire and u_fa < p_false
                visits.append(dict(station=st, supply_match=True, refused=refused_fire or false_ref, refused_base=refused_fire))
                unsafe += fire and not refused_fire
                cum_refusal += false_ref
        cum_extra += extra_visits * W
        if credit:
            ac.settle(led, plan, visits)
        series.append({'extra_s': round(cum_extra, 1), 'false_refusals': cum_refusal})
    return {'series': series, 'unsafe': unsafe,
            'throttled_missions': sum(1 for h in led['history'] if not h['charges']) if credit else None}


def main():
    rates = json.loads((RES / 'h_change_rate.json').read_text())['rates']
    fa = (json.loads((RES / 'k_summary.json').read_text()).get('caution') or {}).get('heldout_false_alarm')
    delta = fa['k'] / fa['n'] if fa else 4 / 193      # study K: per-view false alarms at the caution threshold (S10)
    out = {'note': 'descriptive model, not registered; drives rescuemind.advice_credit with synthetic outcomes',
           'delta': delta, 'params': ac.new_ledger()['params'], 'runs': {}}
    for k in (2, 4):
        for src in SOURCES:
            for credit in (False, True):
                r = run(src, k, credit, rates, delta)
                out['runs'][f'k{k}/{src}/{"credit" if credit else "monotone"}'] = r
                last = r['series'][-1]
                print(f'k={k} {src:8s} {"credit  " if credit else "monotone"} extra {last["extra_s"]:8.1f} s '
                      f'false refusals {last["false_refusals"]:3d} unsafe {r["unsafe"]}')
    for k in (2, 4):
        for src in SOURCES:
            a, b = out['runs'][f'k{k}/{src}/monotone'], out['runs'][f'k{k}/{src}/credit']
            assert a['unsafe'] == b['unsafe'], 'credit changed safety'
    # hazard flooding in the real-photograph regime: P2's calibrated threshold still flags 18/100 fire-free photos
    out['delta_real'] = 0.18
    for credit in (False, True):
        r = run('flooder', 4, credit, rates, 0.18)
        out['runs'][f'k4/flooder_real/{"credit" if credit else "monotone"}'] = r
        print('k=4 flooder (real-photo delta)', 'credit' if credit else 'monotone', r['series'][-1])
    # consistency-robustness trade-off of the recovery rate (k = 4, mean over 20 seeds)
    out['rho_shadow_sweep'] = []
    for rs in (0.0, 0.1, 0.25, 0.5, 1.0):
        row = {'rho_shadow': rs}
        for src in ('noisy', 'farmer', 'honest'):
            row[src + '_extra_s'] = round(sum(run(src, 4, True, rates, delta, seed=s_, rho_shadow=rs)['series'][-1]['extra_s']
                                              for s_ in range(20)) / 20, 1)
        for src in ('noisy', 'farmer'):
            row[src + '_extra_s_no_credit'] = round(sum(run(src, 4, False, rates, delta, seed=s_)['series'][-1]['extra_s']
                                                        for s_ in range(20)) / 20, 1)
        out['rho_shadow_sweep'].append(row)
        print('rho_shadow', row)
    (RES / 'advice_credit_horizon.json').write_text(json.dumps(out, indent=1) + '\n')
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        return
    fig, ax = plt.subplots(1, 3, figsize=(9.6, 2.6))
    col = {'honest': '#1f6feb', 'noisy': '#6f42c1', 'liar': '#c0392b', 'farmer': '#e67e22', 'flooder': '#2e7d32'}
    x = range(1, 101)
    for src in ('honest', 'noisy', 'liar', 'farmer'):
        for credit, ls in ((False, ':'), (True, '-')):
            s = out['runs'][f'k4/{src}/{"credit" if credit else "monotone"}']['series']
            ax[0].plot(x, [r['extra_s'] / 60 for r in s], ls=ls, color=col[src], lw=1.5,
                       label=src if credit else None)
    for name, c, lab in (('flooder', col['flooder'], 'sim. views'), ('flooder_real', '#8d6e63', 'photo regime')):
        for credit, ls in ((False, ':'), (True, '-')):
            s = out['runs'][f'k4/{name}/{"credit" if credit else "monotone"}']['series']
            ax[1].plot(x, [r['false_refusals'] for r in s], ls=ls, color=c, lw=1.5,
                       label=f'{lab}, {"credit" if credit else "none"}')
    sw = out['rho_shadow_sweep']
    ax[2].plot([-r['noisy_extra_s'] / 60 for r in sw], [r['farmer_extra_s'] / 60 for r in sw], marker='o', ms=4,
               color='#1f6feb', lw=1.5, label='credit, varying recovery')
    for r in sw:
        ax[2].annotate(f"{r['rho_shadow']:g}", (-r['noisy_extra_s'] / 60, r['farmer_extra_s'] / 60), fontsize=6,
                       xytext=(3, 3), textcoords='offset points')
    ax[2].plot([-sw[0]['noisy_extra_s_no_credit'] / 60], [sw[0]['farmer_extra_s_no_credit'] / 60], marker='s', ms=5,
               color='#c0392b', ls='none', label='no credit')
    ax[2].set_xlabel('time saved by a 70%-right source [min]'); ax[2].set_ylabel('time lost to adaptive liar [min]')
    ax[2].legend(fontsize=6.5, frameon=False)
    ax[1].plot(x, [ac.C_HAZ + ac.RHO * i for i in x], color='#999', lw=.8, ls='--', label=r'bound $C_h+\rho m$')
    ax[0].set_ylabel('extra time vs no advice [min]'); ax[1].set_ylabel('false refusals (hazard flooding)')
    for a in ax[:2]:
        a.set_xlabel('missions (k = 4)')
    for a in ax:
        a.grid(alpha=.3, lw=.5); a.spines[['top', 'right']].set_visible(False)
    ax[0].axhline(0, color='#999', lw=.6)
    ax[0].legend(fontsize=6.5, frameon=False, title='solid: credit, dotted: none', title_fontsize=6.5)
    ax[1].legend(fontsize=6.5, frameon=False)
    fig.tight_layout()
    fig.savefig(ROOT / 'docs/paper/fig_advice_credit.pdf')
    (ROOT / 'docs/figures').mkdir(exist_ok=True)
    fig.savefig(ROOT / 'docs/figures/advice_credit.png', dpi=160)


if __name__ == '__main__':
    main()
