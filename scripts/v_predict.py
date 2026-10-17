#!/usr/bin/env python3
"""Study V: the repeated-mission model's predictions for the registered V sequences, computed BEFORE any V trial.

  python3 scripts/v_predict.py [--protocol experiments/campaign_v_protocol.json]   # -> experiments/results/v_predictions.json

Campaign H measured per-check behaviour and mission times; scripts/h_change_rate_model.py turned them into a model of
repeated missions in a world that changes with probability q.  Study V tests that model in closed loop: the world states of
the V sequences are drawn from the model's own change process (make_protocol_v.py), and here the model predicts, for exactly
those drawn states, the distribution of each arm's outcomes.  Only the check outcomes and the mission times are random:
  * a check at a station with a fire catches it with p_det, a fire-free check stops falsely with p_fs (Beta posteriors
    from the H/G counts, so the interval includes the uncertainty of the rates themselves);
  * mission times are resampled from campaign H's observed times of the same outcome type.
The policy logic is that of h_change_rate_model._run (M0 no memory, M1 naive, M2 verified; caution gets no credit).
Output: per arm the 2.5/50/97.5% points of the mean mission time, unsafe deliveries and false refusals, and of the paired
mean-time difference M0 - M2 and M0 - M1.  These are the registered predictive intervals of study V.
"""
from __future__ import annotations
import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RES = ROOT / 'experiments/results'
from scripts.h_change_rate_model import rates  # noqa: E402

ARMS = ('M0', 'M1', 'M2')


def observed_times():
    """campaign H mission times by outcome type (the empirical distributions behind the model's medians)."""
    h = json.loads((RES / 'h_summary.json').read_text())
    kinds = {'ALLOW': 'deliver_direct', 'ALLOW_AFTER_SEARCH': 'deliver_search', 'DENY_HAZARD': 'deny_direct',
             'DENY_HAZARD_AFTER_SEARCH': 'deny_search', 'ALLOW_MEMORY': 'deliver_skip', 'DENY_MEMORY': 'deny_memory'}
    out = {}
    for p in h['trials']:
        if not p['failed'] and p['mission_time_s'] is not None and p['observed'] in kinds:
            out.setdefault(kinds[p['observed']], []).append(p['mission_time_s'])
    extra = json.loads((RES / 'v_time_pool_extra.json').read_text())   # Amendment 1: H has no deny-after-search run
    for kind in ('deny_search',):
        if not out.get(kind):
            out[kind] = [x['mission_time_s'] for x in extra[kind]]
    missing = [k for k in kinds.values() if not out.get(k)]
    if missing:
        raise SystemExit(f'no measured mission times for {missing}: refusing to predict with defaults')
    return out


def mission(policy, state, mem, rng, p_det, p_fs):
    """One mission in a given world state.  Returns (outcome, time kind, new memory).  Mirrors h_change_rate_model._run."""
    at = 'other' if state['relocated'] else 'own'
    fire = state['fire']
    mem_loc, mem_fire = mem
    trust = policy == 'M1'
    first = mem_loc if (policy in ('M1', 'M2') and mem_loc) else 'own'
    if trust and mem_loc and mem_fire:
        return ('deny_false' if not fire else 'deny'), 'deny_memory', mem
    if trust and mem_loc and not mem_fire:
        return ('deliver' if (first == at and not fire) else 'deliver_unsafe'), 'deliver_skip', mem
    searched = first != at
    if fire:
        out = 'deny' if rng.random() < p_det else 'deliver_unsafe'
    else:
        out = 'deny_false' if rng.random() < p_fs else 'deliver'
    kind = ('deliver_search' if searched else 'deliver_direct') if out.startswith('deliver') else (
        'deny_search' if searched else 'deny_direct')
    return out, kind, (at, out in ('deny', 'deny_false'))


def predict(sequences, n_draws=20000, seed=7):
    """sequences: {seq_id: [state_mission1, ..., state_missionK]}; state = {'relocated': bool, 'fire': bool}."""
    r = rates()
    times = observed_times()
    det_k, det_n = round(r['p_det'] * r['p_det_n']), r['p_det_n']
    fs_k, fs_n = round(r['p_fs'] * r['p_fs_n']), r['p_fs_n']
    rng = random.Random(seed)
    draws = {a: {'mean_time': [], 'unsafe': [], 'false_refusals': [], 'searches': []} for a in ARMS}
    diffs = {'M0-M2': [], 'M0-M1': []}
    unsafe_diff = []                                                 # M2 - M0 unsafe deliveries (V4a margin)
    n_missions = sum(len(s) - 1 for s in sequences.values())        # mission 1 is the shared seed, not scored per arm
    for _ in range(n_draws):
        p_det = rng.betavariate(det_k + 1, det_n - det_k + 1)
        p_fs = rng.betavariate(fs_k + 1, fs_n - fs_k + 1)
        tot = {a: [0.0, 0, 0, 0] for a in ARMS}
        for states in sequences.values():
            _, _, seed_mem = mission('M0', states[0], (None, None), rng, p_det, p_fs)
            for a in ARMS:
                mem = seed_mem
                for st in states[1:]:
                    out, kind, mem = mission(a, st, mem, rng, p_det, p_fs)
                    pool = times.get(kind)
                    tot[a][0] += rng.choice(times[kind])
                    tot[a][1] += out == 'deliver_unsafe'
                    tot[a][2] += out == 'deny_false'
                    tot[a][3] += kind in ('deliver_search', 'deny_search')
        for a in ARMS:
            draws[a]['mean_time'].append(tot[a][0] / n_missions)
            draws[a]['unsafe'].append(tot[a][1]); draws[a]['false_refusals'].append(tot[a][2])
            draws[a]['searches'].append(tot[a][3])
        unsafe_diff.append(tot['M2'][1] - tot['M0'][1])
        diffs['M0-M2'].append((tot['M0'][0] - tot['M2'][0]) / n_missions)
        diffs['M0-M1'].append((tot['M0'][0] - tot['M1'][0]) / n_missions)

    def q(xs):
        xs = sorted(xs)
        pick = lambda f: xs[min(len(xs) - 1, int(f * len(xs)))]
        return {'p2.5': round(pick(.025), 2), 'p50': round(pick(.5), 2), 'p97.5': round(pick(.975), 2)}
    return {'n_sequences': len(sequences), 'n_scored_missions_per_arm': n_missions, 'n_draws': n_draws, 'seed': seed,
            'rates': {'p_det': [det_k, det_n], 'p_fs': [fs_k, fs_n]},
            'time_pools_n': {k: len(v) for k, v in times.items()},
            'arms': {a: {k: q(v) for k, v in d.items()} for a, d in draws.items()},
            'paired_mean_time_diff_s': {k: q(v) for k, v in diffs.items()},
            'unsafe_diff_M2_minus_M0': q(unsafe_diff),
            'time_pools': {k: sorted(v) for k, v in times.items()}}


def perceivable_states(proto, masks: Path):
    """The drawn states with every fire that no design view (front, +-0.4 m) shows with >= 614 px set to no fire, as in H/G."""
    design = {m['key']: m['fire_pixels'] for m in json.loads(masks.read_text())} if masks.is_file() else None
    out = {}
    for seq, sts in proto['sequence_states'].items():
        row = []
        for k, s in enumerate(sts, 1):
            w = f'{seq}m{k}'
            if s['fire'] and design is not None:
                absent = [x for x in (w, w + 'L', w + 'R') if x not in design]
                if absent:
                    raise SystemExit(f'design fire mask missing for {absent}: a fire must never silently become no fire')
            fire = s['fire'] and (design is None or max(design.get(w, 0), design.get(w + 'L', 0), design.get(w + 'R', 0)) >= 614)
            row.append({'relocated': s['relocated'], 'fire': fire})
        out[seq] = row
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--protocol', type=Path, default=ROOT / 'experiments/campaign_v_protocol.json')
    ap.add_argument('--out', type=Path, default=RES / 'v_predictions.json')
    ap.add_argument('--draws', type=int, default=20000)
    ap.add_argument('--dry-run', action='store_true', help='no masks needed, print only (development)')
    a = ap.parse_args()
    proto = json.loads(a.protocol.read_text())
    masks = a.protocol.with_name(a.protocol.stem + '_design_fire_masks.json')
    if not masks.is_file() and not a.dry_run:
        sys.exit(f'{masks.name} missing: render the design fire masks first (labels decide which drawn fires are perceivable)')
    seqs = perceivable_states(proto, masks)
    pred = predict(seqs, n_draws=a.draws)
    pred['n_fire_missions_drawn'] = sum(s['fire'] for v in proto['sequence_states'].values() for s in v)
    pred['n_fire_missions_perceivable'] = sum(s['fire'] for v in seqs.values() for s in v)
    if a.dry_run:
        print(json.dumps(pred, indent=1)); return
    pred['protocol'] = str(a.protocol.relative_to(ROOT)) if a.protocol.is_relative_to(ROOT) else str(a.protocol)
    if a.out.is_file() and json.loads(a.out.read_text()) != json.loads(json.dumps(pred)):
        sys.exit('registered predictions differ; refusing to overwrite')
    a.out.write_text(json.dumps(pred, indent=1) + '\n')
    print(json.dumps(pred, indent=1))


if __name__ == '__main__':
    main()
