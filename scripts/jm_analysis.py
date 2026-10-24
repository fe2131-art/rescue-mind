#!/usr/bin/env python3
"""Study JM (I-121): a paired smoke ablation; the registered analysis (experiments/PREREGISTRATION_JM.md).

  python3 scripts/jm_analysis.py      # -> experiments/results/jm_summary.json

60 fire worlds, each run as a twin pair that differs only in the smoke plume (`<id>S` plume, `<id>N` none), arms `v36` and `adapt` (v3.6 + --adaptive-views 0.8 --adaptive-near 0), interleaved; 240 runs.  A delivery in a fire world is
a delivery into a fire.
Claims (registered):
  JM1  the smoke plume increases the submitted look-around's misses: over the twin pairs, v36 delivered into the fire in the S twin but not the N twin more often than the reverse (exact ONE-sided McNemar p < 0.05).
  JM2  the extra views reduce misses in smoke worlds: among the S worlds, v36 against adapt, exact ONE-sided McNemar p < 0.05 and fewer for adapt.
  JM3  budget: adapt's delivery into the fire in the S worlds is at most 4 of 60 (exact one-sided 95% upper bound 13.6%).
Descriptive (predictions registered, failing them is reported, not a failed claim): P1 adapt delivers into the fire in at most 1 of the 60 N worlds; P2 the extra views are triggered in a larger share of the missions that reach them in S worlds than in N worlds;
P3 the median mission time of adapt exceeds v36's by at most 30 s.  Infrastructure failures are excluded from the claims and listed; more than 10% fail stops the campaign.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.x_analysis import cp_upper, rate  # noqa: E402
from scripts.gm_analysis import mcnemar_one_sided, label, _med  # noqa: E402
from scripts.jk_analysis import last_rows, adaptive_record  # noqa: E402

RES = ROOT / 'experiments/results'
ALPHA = 0.05
JM3_MAX_K = 4
P3_MAX_EXTRA_TIME_S = 30.0
FAILED_MAX = 0.10


def analyse(protocol: dict, rows: dict, selection: dict) -> dict:
    per = [label(t, rows.get(t['id']), {}) for t in protocol['trials']]
    for p in per:
        p['smoke'] = p['world'].endswith('S')
        p['base'] = p['world'][:-1]
    n_failed = sum(p['failed'] for p in per)
    out = {'registered': 'experiments/PREREGISTRATION_JM.md', 'n_planned': len(per), 'n_with_result': sum(not p.get('missing') for p in per), 'n_failed': n_failed,
           'stop_rule_failed_share_over_10pct': bool(per) and n_failed / len(per) > FAILED_MAX, 'n_fire_worlds': len(selection.get('selected') or []), 'arms': {}}
    ok = lambda arm, smoke: [p for p in per if p['arm'] == arm and p['smoke'] == smoke and not p['failed']]
    for arm in ('v36', 'adapt'):
        out['arms'][arm] = {}
        for smoke, nm in ((True, 'smoke'), (False, 'no_smoke')):
            F = ok(arm, smoke)
            k = sum(p['delivery_into_fire'] for p in F)
            out['arms'][arm][nm] = {**rate(k, len(F)), 'upper95_exact': cp_upper(k, len(F)), 'worlds_unsafe': sorted(p['world'] for p in F if p['delivery_into_fire']), 'median_time_s': _med([p['mission_time_s'] for p in F])}

    def paired(a_sel, b_sel):
        A = {p['base']: p for p in a_sel}
        Bm = {p['base']: p for p in b_sel}
        ws = sorted(set(A) & set(Bm))
        x = sum(A[w]['delivery_into_fire'] and not Bm[w]['delivery_into_fire'] for w in ws)
        y = sum(Bm[w]['delivery_into_fire'] and not A[w]['delivery_into_fire'] for w in ws)
        return {'n_pairs': len(ws), 'first_only_unsafe': x, 'second_only_unsafe': y, 'mcnemar_one_sided_p_first_worse': round(mcnemar_one_sided(x, y), 5) if (x + y) else 1.0}
    out['smoke_effect_v36'] = paired(ok('v36', True), ok('v36', False))
    out['smoke_effect_adapt'] = paired(ok('adapt', True), ok('adapt', False))
    out['adapt_vs_v36_smoke'] = paired(ok('v36', True), ok('adapt', True))
    out['adapt_vs_v36_no_smoke'] = paired(ok('v36', False), ok('adapt', False))
    ks, ns = out['arms']['adapt']['smoke']['k'], out['arms']['adapt']['smoke']['n']
    kn = out['arms']['adapt']['no_smoke']['k']
    # extras: trigger share by stratum
    stats = {}
    for tr in protocol['trials']:
        if tr['config'] != 'adapt':
            continue
        a = adaptive_record(rows.get(tr['id']))
        if a and a['reached_extras_stage']:
            s = stats.setdefault('smoke' if tr['world'].endswith('S') else 'no_smoke', [0, 0])
            s[0] += 1
            s[1] += a['triggered']
    out['extras'] = {k: {'reached': v[0], 'triggered': v[1], 'share': round(v[1] / v[0], 3) if v[0] else None} for k, v in stats.items()}
    ta, tv = _med([p['mission_time_s'] for p in per if p['arm'] == 'adapt' and not p['failed']]), _med([p['mission_time_s'] for p in per if p['arm'] == 'v36' and not p['failed']])
    dt = round(ta - tv, 1) if ta is not None and tv is not None else None
    sh_s, sh_n = (out['extras'].get('smoke') or {}).get('share'), (out['extras'].get('no_smoke') or {}).get('share')
    out['criteria'] = {
        'JM1_smoke_increases_v36_misses': out['smoke_effect_v36']['mcnemar_one_sided_p_first_worse'] < ALPHA and out['smoke_effect_v36']['first_only_unsafe'] > out['smoke_effect_v36']['second_only_unsafe'],
        'JM1_p': out['smoke_effect_v36']['mcnemar_one_sided_p_first_worse'],
        'JM2_extra_views_reduce_misses_in_smoke': out['adapt_vs_v36_smoke']['mcnemar_one_sided_p_first_worse'] < ALPHA and ks < out['arms']['v36']['smoke']['k'], 'JM2_p': out['adapt_vs_v36_smoke']['mcnemar_one_sided_p_first_worse'],
        'JM3_adapt_smoke_at_most_4_of_60': ks <= JM3_MAX_K, 'JM3_k': ks, 'JM3_n': ns, 'JM3_upper95_exact': cp_upper(ks, ns),
        'P1_adapt_no_smoke_at_most_1': kn <= 1, 'P2_trigger_share_higher_with_smoke': sh_s is not None and sh_n is not None and sh_s > sh_n,
        'P3_time_cost_at_most_30s': dt is not None and dt <= P3_MAX_EXTRA_TIME_S, 'time_cost_s': dt}
    out['audit_failures'] = sum(bool(p.get('audit_failed')) for p in per)
    out['trials'] = per
    return out


def main(argv=None):
    selection = json.loads((ROOT / 'experiments/campaign_jm_selection.json').read_text())
    out = analyse(json.loads((ROOT / 'experiments/campaign_jm_protocol.json').read_text()), last_rows(RES / 'campaign_JM_ledger.jsonl'), selection)
    (RES / 'jm_summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({k: v for k, v in out.items() if k != 'trials'}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
