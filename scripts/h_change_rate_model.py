#!/usr/bin/env python3
"""Campaign H secondary analysis (pre-registered, descriptive): how do the three memory policies behave as the world
changes more or less often between missions?

  python3 scripts/h_change_rate_model.py      # -> experiments/results/h_change_rate.json (+ docs/paper/fig_h_change_rate.pdf)

A Monte-Carlo model of repeated resupply missions.  Between missions, with probability q each, the supplies swap
stations and the fire behind the station that holds the requested supply appears/disappears.  The per-check behaviour
is MEASURED, not assumed:
  * p_det:  a perceivable fire is caught by the v3.6 check with look-around (campaign G config C + campaign H, M0/M2)
  * p_fs:   a fire-free check stops falsely (campaigns G, H)
  * supply identification is taken as perfect (T1: 0/332 supply false approvals; E: 0/60 wrong deliveries)
  * mission times by outcome type: medians from campaign H (fall back to G when H has no such run)
The policies are exactly those of rescuemind/mission_memory.py (M0 off, M1 naive, M2 verified).  Caution (tau_h=0.01)
is modelled with the same p_det unless H measured it separately (conservative: no credit for caution).

Extra policy M1age (added as a reviewer-requested baseline, same random streams for M0/M1/M2 as before):
  M1age is the naive memory with a recency gate.  It trusts memory only if the memory was *observed* (by a real check) in
  the immediately previous mission (age 1).  Older memory is ignored: the robot does M0's full check at its own station
  and then refreshes the memory.  A skipped mission does not refresh memory, so M1age can never skip two missions in a row.
  This is the natural "recency-gated" baseline a reviewer asks for: "just expire the memory" is the cheapest fix for the
  naive-memory failure (a stale 'no fire' record), needs no extra sensing, and bounds the age of any trusted record to one
  mission.  It still trusts that one-mission-old record blindly, so its unsafe rate stays well above M0/M2 for q > 0
  (a change in the last mission is unseen); it only limits how long a wrong record persists.
  Note: for n_missions = 2 M1age is identical to M1 (the gate cannot bite before mission 3).  For longer sequences the
  two are close at q = 0 (M1age re-checks a missed fire, but also re-exposes a correctly denied fire to a new miss) and
  M1age is clearly safer than M1 for q > 0.

Additional outputs (do not alter 'q' / 'policies'):
  fine_grid    : all four policies on q = 0, 0.025, ..., 0.5
  break_even   : per policy the q* at which mean mission time equals M0's (linear interpolation on the fine grid; None if
                 no crossing in [0, 0.5], with the sign of the difference) and unsafe deliveries / 100 missions at
                 q = 0.05, 0.1, 0.2
  bound_check  : for M0 and M2 every mission is gated by one baseline check, so P(unsafe) <= (1 - p_det) * P(fire at the
                 delivering station); empirical rate vs bound per q (sanity check of the paper's corollary)
"""
from __future__ import annotations
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RES = ROOT / 'experiments/results'


def rates():
    g = json.loads((RES / 'g_summary.json').read_text())
    h = json.loads((RES / 'h_summary.json').read_text()) if (RES / 'h_summary.json').is_file() else None
    det_n = g['primary']['n_world_pairs_fire_perceivable']
    det_k = det_n - g['primary']['wrong_deliveries_C']
    fs_n, fs_k = g['per_config']['C']['fire_free_trials'], g['per_config']['C']['false_hazard_stops']
    times = {}
    if h:
        for p in h['trials']:
            if p['failed'] or p['arm'] not in ('M0', 'M2', 'seed') or p['mission_time_s'] is None:
                continue
            fire_missions = p['fire_perceivable_at'] is not None
            # a checked station with a perceivable fire: caught (refusal) or missed (delivery)
            if fire_missions and p['delivered_from'] == p['fire_perceivable_at']:
                det_n += 1
            elif fire_missions and not p['delivered']:
                det_n += 1; det_k += 1
            if not fire_missions:
                fs_n += 1; fs_k += (not p['delivered'] and p['observed'].startswith('DENY_HAZARD'))
            kind = ('deliver_search' if p['observed'] == 'ALLOW_AFTER_SEARCH' else 'deliver_direct' if p['observed'] == 'ALLOW'
                    else 'deny_search' if p['observed'] == 'DENY_HAZARD_AFTER_SEARCH' else 'deny_direct' if p['observed'] == 'DENY_HAZARD' else None)
            if kind:
                times.setdefault(kind, []).append(p['mission_time_s'])
        for p in h['trials']:
            if p['arm'] == 'M1' and not p['failed'] and p['mission_time_s'] is not None:
                kind = {'ALLOW_MEMORY': 'deliver_skip', 'DENY_MEMORY': 'deny_memory'}.get(p['observed'])
                if kind:
                    times.setdefault(kind, []).append(p['mission_time_s'])
    med = {k: sorted(v)[len(v) // 2] for k, v in times.items()}
    default = {'deliver_direct': 122.0, 'deliver_search': 150.0, 'deny_direct': 35.0, 'deny_search': 75.0,
               'deliver_skip': 75.0, 'deny_memory': 3.0}       # G medians / estimates, used only without H data
    return {'p_det': det_k / det_n, 'p_det_n': det_n, 'p_fs': fs_k / fs_n, 'p_fs_n': fs_n,
            'time_s': {k: med.get(k, v) for k, v in default.items()}, 'time_source': {k: ('H' if k in med else 'default') for k in default}}


POLICIES = ('M0', 'M1', 'M2', 'M1age')


def _run(policy, q, r, n_seq=4000, n_missions=6, seed=1):
    rng = random.Random(seed)
    unsafe = refusals_false = missions = fires = 0
    t_total = 0.0
    T = r['time_s']
    for _ in range(n_seq):
        reloc, fire = rng.random() < .5, rng.random() < .3      # requested supply away from its own station? fire there?
        mem_loc = mem_fire = None                                 # memory: where the supply was seen; fire seen there?
        mem_k = None                                              # mission index at which memory was last observed
        for k in range(n_missions):
            if k:
                reloc ^= rng.random() < q
                fire ^= rng.random() < q
            at = 'other' if reloc else 'own'
            missions += 1
            fires += fire
            safe_exists = not fire
            # M1 always trusts memory; M1age only if it was observed in the previous mission
            trust = policy == 'M1' or (policy == 'M1age' and mem_k == k - 1)

            def check():           # v3.6 check at the station that holds the supply
                if fire:
                    return 'deny' if rng.random() < r['p_det'] else 'deliver_unsafe'
                return 'deny_false' if rng.random() < r['p_fs'] else 'deliver'
            first = mem_loc if ((trust or policy == 'M2') and mem_loc) else 'own'
            if trust and mem_loc and mem_fire:
                out, t = ('deny_false' if safe_exists else 'deny'), T['deny_memory']
            elif trust and mem_loc and not mem_fire:
                ok_supply = first == at
                out = 'deliver' if (ok_supply and not fire) else 'deliver_unsafe'
                t = T['deliver_skip']
            else:
                searched = first != at
                out = check()
                t = {('deliver', False): T['deliver_direct'], ('deliver', True): T['deliver_search'],
                     ('deliver_unsafe', False): T['deliver_direct'], ('deliver_unsafe', True): T['deliver_search'],
                     ('deny', False): T['deny_direct'], ('deny', True): T['deny_search'],
                     ('deny_false', False): T['deny_direct'], ('deny_false', True): T['deny_search']}[(out, searched)]
                mem_loc, mem_fire, mem_k = at, out in ('deny', 'deny_false'), k    # what the robot saw this time
            unsafe += out == 'deliver_unsafe'
            refusals_false += out == 'deny_false'
            t_total += t
    return {'unsafe': unsafe, 'false_refusals': refusals_false, 'missions': missions, 'fires': fires, 't_total': t_total}


def simulate(policy, q, r, n_seq=4000, n_missions=6, seed=1):
    c = _run(policy, q, r, n_seq, n_missions, seed)
    m = c['missions']
    return {'unsafe_per_100': round(100 * c['unsafe'] / m, 2), 'false_refusals_per_100': round(100 * c['false_refusals'] / m, 2),
            'mean_time_s': round(c['t_total'] / m, 1)}


def fine_analysis(r, n_seq=4000, n_missions=6, seed=1):
    """fine q grid, break-even q* (mean time = M0's) and the per-mission bound check for M0 / M2."""
    qf = [round(0.025 * i, 3) for i in range(21)]
    raw = {p: [_run(p, q, r, n_seq, n_missions, seed) for q in qf] for p in POLICIES}
    fine = {'q': qf, 'policies': {p: [{'unsafe_per_100': round(100 * c['unsafe'] / c['missions'], 2),
                                       'false_refusals_per_100': round(100 * c['false_refusals'] / c['missions'], 2),
                                       'mean_time_s': round(c['t_total'] / c['missions'], 1)} for c in raw[p]] for p in POLICIES}}
    mt = {p: [c['t_total'] / c['missions'] for c in raw[p]] for p in POLICIES}
    be = {}
    for p in POLICIES:
        d = [a - b for a, b in zip(mt[p], mt['M0'])]
        qstar, note = None, 'no crossing in [0, 0.5]'
        if p == 'M0':
            note = 'reference'
        elif d[0] >= 0:
            qstar, note = 0.0, 'not faster than M0 even at q = 0'
        else:
            for i in range(1, len(qf)):
                if d[i] >= 0:
                    qstar = round(qf[i - 1] + (qf[i] - qf[i - 1]) * (-d[i - 1]) / (d[i] - d[i - 1]), 4)
                    note = 'interpolated'
                    break
            else:
                note = 'faster than M0 over all of [0, 0.5]'
        be[p] = {'q_star': qstar, 'note': note, 'time_diff_vs_M0_at_q0_s': round(d[0], 1) + 0.0, 'time_diff_vs_M0_at_q05_s': round(d[-1], 1) + 0.0,
                 'unsafe_per_100': {str(q): fine['policies'][p][qf.index(q)]['unsafe_per_100'] for q in (0.05, 0.1, 0.2)}}
    bc = {}
    for p in ('M0', 'M2'):
        rows = []
        for q, c in zip(qf, raw[p]):
            m = c['missions']
            rate, fire_rate = c['unsafe'] / m, c['fires'] / m
            bound = (1 - r['p_det']) * fire_rate
            se = (max(rate, 1e-12) * (1 - rate) / m) ** .5
            rows.append({'q': q, 'unsafe_rate': round(rate, 5), 'fire_rate': round(fire_rate, 4), 'bound': round(bound, 5),
                         'bound_theory_p_fire_0.3': round((1 - r['p_det']) * 0.3, 5), 'holds_within_4se': rate <= bound + 4 * se})
        bc[p] = rows
    return fine, be, bc


def main():
    r = rates()
    qs = [0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5]
    out = {'rates': r, 'q': qs, 'policies': {p: [simulate(p, q, r) for q in qs] for p in POLICIES}}
    out['fine_grid'], out['break_even'], out['bound_check'] = fine_analysis(r)
    (RES / 'h_change_rate.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(7, 2.6))
        style = {'M0': ('#7a7a7a', 'o', 'no memory (v3.6)'), 'M1': ('#c0392b', 's', 'naive memory'), 'M2': ('#1f6feb', '^', 'verified memory (ours)'),
                 'M1age': ('#2f3e4e', 'D', 'naive memory, age <= 1')}
        for p, (c, m, lab) in style.items():
            ax[0].plot(qs, [x['unsafe_per_100'] for x in out['policies'][p]], color=c, marker=m, ms=4 if p != 'M1age' else 3.2, lw=1.6, ls='--' if p == 'M1age' else '-', label=lab)
            ax[1].plot(qs, [x['mean_time_s'] for x in out['policies'][p]], color=c, marker=m, ms=4 if p != 'M1age' else 3.2, lw=1.6, ls='--' if p == 'M1age' else '-', label=lab)
        ax[0].set_ylabel('unsafe deliveries / 100 missions'); ax[1].set_ylabel('mean mission time [s]')
        for a in ax:
            a.set_xlabel('change probability between missions q'); a.grid(alpha=.3, lw=.5)
            a.spines[['top', 'right']].set_visible(False)
        ax[0].legend(fontsize=6.5, frameon=False, loc='upper left', handlelength=2.2, labelspacing=.3)
        fig.tight_layout()
        fig.savefig(ROOT / 'docs/paper/fig_h_change_rate.pdf')
    except ImportError:
        pass


if __name__ == '__main__':
    main()
