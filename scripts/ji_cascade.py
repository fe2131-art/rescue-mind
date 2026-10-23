#!/usr/bin/env python3
"""Study JC (experiments/PREREGISTRATION_JC.md): JEV with a divided role, on study JI's fresh worlds (image level, no GPU).

  python3 scripts/ji_cascade.py        # -> experiments/results/ji_cascade_summary.json   (after JI_DONE)
The gate (Qwen3.5-9B) decides; a fast judge of another family is a SENTINEL on the standard views F, L, R: at or above its frozen threshold the robot spends the three extra views (L2, R2, N) and the gate decides
on all six views (tau6), otherwise on F, L, R (tau3).  The sentinel never refuses and never approves.  Thresholds: experiments/ji_thresholds.json (gate) and experiments/ji_cascade_thresholds.json (sentinels),
both frozen from XD.  Primary sentinel = the judge with the lowest median scoring latency in JI among internvl3, idefics3, smolvlm2 (a rule, not a choice).
"""
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
import ji_analysis as jia  # noqa: E402
from x_analysis import cp_upper  # noqa: E402

RES = ROOT / 'experiments/results'
STD, EXTRA = ('F', 'L', 'R'), ('L2', 'R2', 'N')
SENTINELS = ('internvl3', 'idefics3', 'smolvlm2')
DRIVE_S_PER_EXTRA_VIEW = 8.4         # GL: median mission 43.8 s with two 0.4 m peeks vs 35.4 s with one 0.8 m peek (experiments/results/gl_summary.json)
JC1_MARGIN = 3                       # sentinel misses at most (always-six misses + 3)
JC2_MAX_MEAN_VIEWS_CLEAN = 4.0       # mean views per clean world (3 = no extra view, 6 = always six)
JC3_MAX_FALSE_STOPS = 5              # of 120 (the same limit as JI3)


def pmax(d, views):
    out = {}
    for (w, v), s in d.items():
        if v in views:
            out[w] = max(out.get(w, 0.0), s)
    return out


def latencies(res=RES):
    out = {}
    for j in SENTINELS:
        f = res / f'jev_scores_{j}_ji.jsonl'
        ls = [json.loads(x)['score'].get('latency_s') for x in f.read_text(encoding='utf8').splitlines() if x.strip()] if f.is_file() else []
        ls = [x for x in ls if x is not None]
        out[j] = round(statistics.median(ls), 3) if ls else None
    return out


def policy(sc, fire, clean, tau3, tau6, trig):
    """trig(world) -> bool: spend the extra views."""
    q3, q6 = pmax(sc['qwen35'], STD), pmax(sc['qwen35'], STD + EXTRA)
    flagged = lambda w: (q6.get(w, 0.0) >= tau6) if trig(w) else (q3.get(w, 0.0) >= tau3)
    miss = [w for w in fire if not flagged(w)]
    fs = [w for w in clean if flagged(w)]
    mean = lambda ws: round(sum(3 + (3 if trig(w) else 0) for w in ws) / len(ws), 3)
    return {'miss': len(miss), 'miss_rate': round(len(miss) / len(fire), 4), 'miss_upper95': round(cp_upper(len(miss), len(fire)), 4), 'false_stops': len(fs),
            'trigger_fire': round(sum(trig(w) for w in fire) / len(fire), 3), 'trigger_clean': round(sum(trig(w) for w in clean) / len(clean), 3),
            'mean_views_clean': mean(clean), 'mean_views_fire': mean(fire), 'missed_worlds': miss}


def analyse(sc, kind, thr, cthr, lat, qwen_view_s):
    fire = sorted(w for w, k in kind.items() if k == 'fire')
    clean = sorted(w for w, k in kind.items() if k == 'clean')
    tau3, tau6 = thr['tau']['v36_FLR']['qwen35'], thr['tau']['all_six']['qwen35']
    a = str(cthr['primary_alpha'])
    out = {'n_fire': len(fire), 'n_clean': len(clean), 'tau3': tau3, 'tau6': tau6, 'sentinel_latency_median_s': lat, 'policies': {}}
    out['policies']['always3'] = policy(sc, fire, clean, tau3, tau6, lambda w: False)
    out['policies']['always6'] = policy(sc, fire, clean, tau3, tau6, lambda w: True)
    q3 = pmax(sc['qwen35'], STD)
    out['policies']['gate_own_trigger'] = policy(sc, fire, clean, tau3, tau6, lambda w: q3.get(w, 0.0) >= cthr['gate_own_trigger'])
    for j in SENTINELS:
        s_j = cthr['sentinel_alpha'][j][a]
        jm = pmax(sc[j], STD)
        out['policies']['sentinel_' + j] = {**policy(sc, fire, clean, tau3, tau6, lambda w, jm=jm, s_j=s_j: jm.get(w, 0.0) >= s_j), 's_j': s_j, 'alpha_s': float(a)}
    cand = {j: lat[j] for j in SENTINELS if lat.get(j) is not None}
    primary = min(cand, key=cand.get) if cand else None
    out['primary_sentinel'] = primary
    for name, p in out['policies'].items():          # time model (descriptive): extra views driven + their gate calls + the sentinel's calls on F, L, R
        extra = (p['mean_views_clean'] - 3)
        sj = name.replace('sentinel_', '') if name.startswith('sentinel_') else None
        p['est_extra_seconds_per_clean_mission'] = round(extra * (DRIVE_S_PER_EXTRA_VIEW + qwen_view_s) + (3 * (lat.get(sj) or 0.0) if sj else 0.0), 1)
    if primary:
        P, A3, A6 = out['policies']['sentinel_' + primary], out['policies']['always3'], out['policies']['always6']
        out['claims'] = {'JC1_primary_sentinel_misses_within_3_of_always_six': P['miss'] <= A6['miss'] + JC1_MARGIN,
                         'JC2_primary_sentinel_mean_views_clean_at_most_4': P['mean_views_clean'] <= JC2_MAX_MEAN_VIEWS_CLEAN,
                         'JC3_primary_sentinel_false_stops_at_most_5': P['false_stops'] <= JC3_MAX_FALSE_STOPS,
                         'P1_primary_sentinel_fewer_misses_than_always_three': P['miss'] < A3['miss'],
                         'P2_primary_sentinel_faster_than_always_six_estimate': P['est_extra_seconds_per_clean_mission'] < A6['est_extra_seconds_per_clean_mission']}
    return out


def main():
    thr = json.loads((ROOT / 'experiments/ji_thresholds.json').read_text())
    cthr = json.loads((ROOT / 'experiments/ji_cascade_thresholds.json').read_text())
    sc, kind = jia.load_scores()
    d = json.loads((RES / 'devset_ji_h36_tiles.json').read_text(encoding='utf8'))
    ql = [r['passes']['1']['latency_s'] for r in d['records'] if '1' in r['passes'] and 'latency_s' in r['passes']['1']]
    out = analyse(sc, kind, thr, cthr, latencies(), round(statistics.median(ql), 2) if ql else 0.0)
    (RES / 'ji_cascade_summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({'primary': out.get('primary_sentinel'), 'claims': out.get('claims'),
                      'policies': {k: (v['miss'], v['false_stops'], v['mean_views_clean'], v['est_extra_seconds_per_clean_mission']) for k, v in out['policies'].items()}}))


if __name__ == '__main__':
    main()
