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


def simulate(policy, q, r, n_seq=4000, n_missions=6, seed=1):
    rng = random.Random(seed)
    unsafe = refusals_false = missions = 0
    t_total = 0.0
    T = r['time_s']
    for _ in range(n_seq):
        reloc, fire = rng.random() < .5, rng.random() < .3      # requested supply away from its own station? fire there?
        mem_loc = mem_fire = None                                 # memory: where the supply was seen; fire seen there?
        for k in range(n_missions):
            if k:
                reloc ^= rng.random() < q
                fire ^= rng.random() < q
            at = 'other' if reloc else 'own'
            missions += 1
            safe_exists = not fire

            def check():           # v3.6 check at the station that holds the supply
                if fire:
                    return 'deny' if rng.random() < r['p_det'] else 'deliver_unsafe'
                return 'deny_false' if rng.random() < r['p_fs'] else 'deliver'
            first = mem_loc if (policy != 'M0' and mem_loc) else 'own'
            if policy == 'M1' and mem_loc and mem_fire:
                out, t = ('deny_false' if safe_exists else 'deny'), T['deny_memory']
            elif policy == 'M1' and mem_loc and not mem_fire:
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
                mem_loc, mem_fire = at, out in ('deny', 'deny_false')    # what the robot saw this time
            unsafe += out == 'deliver_unsafe'
            refusals_false += out == 'deny_false'
            t_total += t
    return {'unsafe_per_100': round(100 * unsafe / missions, 2), 'false_refusals_per_100': round(100 * refusals_false / missions, 2),
            'mean_time_s': round(t_total / missions, 1)}


def main():
    r = rates()
    qs = [0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5]
    out = {'rates': r, 'q': qs, 'policies': {p: [simulate(p, q, r) for q in qs] for p in ('M0', 'M1', 'M2')}}
    (RES / 'h_change_rate.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(7, 2.6))
        style = {'M0': ('#7a7a7a', 'o', 'no memory (v3.6)'), 'M1': ('#c0392b', 's', 'naive memory'), 'M2': ('#1f6feb', '^', 'verified memory (ours)')}
        for p, (c, m, lab) in style.items():
            ax[0].plot(qs, [x['unsafe_per_100'] for x in out['policies'][p]], color=c, marker=m, ms=4, lw=1.6, label=lab)
            ax[1].plot(qs, [x['mean_time_s'] for x in out['policies'][p]], color=c, marker=m, ms=4, lw=1.6, label=lab)
        ax[0].set_ylabel('unsafe deliveries / 100 missions'); ax[1].set_ylabel('mean mission time [s]')
        for a in ax:
            a.set_xlabel('change probability between missions q'); a.grid(alpha=.3, lw=.5)
            a.spines[['top', 'right']].set_visible(False)
        ax[0].legend(fontsize=7, frameon=False)
        fig.tight_layout()
        fig.savefig(ROOT / 'docs/paper/fig_h_change_rate.pdf')
    except ImportError:
        pass


if __name__ == '__main__':
    main()
