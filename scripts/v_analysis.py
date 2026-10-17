#!/usr/bin/env python3
"""Study V analysis exactly as pre-registered (experiments/PREREGISTRATION_V.md).

  python3 scripts/v_analysis.py      # -> experiments/results/v_summary.json

Labels as in campaign H (scripts/h_analysis.label): ground truth from the scene and the design fire masks
(experiments/campaign_v_protocol_design_fire_masks.json, >= 614 px in any of the three views).  The predictions the
observations are compared with are experiments/results/v_predictions.json, committed before the first V trial.
"""
from __future__ import annotations
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.t1_analysis import wilson, mcnemar_exact  # noqa: E402
from scripts.h_analysis import label, wilcoxon_exact  # noqa: E402

RES = ROOT / 'experiments/results'
ARMS = ('M0', 'M1', 'M2')


def inside(x, iv):
    return iv['p2.5'] <= x <= iv['p97.5']


def main():
    proto = json.loads((ROOT / 'experiments/campaign_v_protocol.json').read_text())
    pred = json.loads((RES / 'v_predictions.json').read_text())
    trials = {t['id']: t for t in proto['trials']}
    rows = [r for r in (json.loads(x) for x in (RES / 'campaign_V_ledger.jsonl').read_text().splitlines() if x.strip())
            if r.get('final', True)]
    design = {m['key']: m['fire_pixels'] for m in json.loads((ROOT / 'experiments/campaign_v_protocol_design_fire_masks.json').read_text())}
    perceivable = {w: max(design.get(w, 0), design.get(w + 'L', 0), design.get(w + 'R', 0)) >= 614
                   for w in {k.rstrip('LR') for k in design}}
    per = [label(trials[r['trial_id']], r, perceivable) for r in rows]
    scored = [p for p in per if p['k'] > 1]
    out = {'registered': 'experiments/PREREGISTRATION_V.md', 'n_trials': len(per), 'n_planned': proto['planned_n'],
           'complete': len(per) == proto['planned_n'], 'failed': sum(p['failed'] for p in per)}

    arm = {}
    for a in ARMS:
        ps = [p for p in scored if p['arm'] == a]
        ok = [p for p in ps if not p['failed'] and p['mission_time_s'] is not None]
        mean_t = sum(p['mission_time_s'] for p in ok) / len(ok) if ok else None
        unsafe = sum(p['unsafe_delivery'] for p in ps)
        fr = sum(p['false_refusal'] for p in ps)
        arm[a] = {'n': len(ps), 'n_timed': len(ok), 'mean_time_s': None if mean_t is None else round(mean_t, 2),
                  'median_time_s': statistics.median([p['mission_time_s'] for p in ok]) if ok else None,
                  'unsafe': unsafe, 'unsafe_wilson': [round(x, 4) for x in wilson(unsafe, len(ps))] if ps else None,
                  'false_refusals': fr,
                  'searches': sum(p['observed'] in ('ALLOW_AFTER_SEARCH', 'DENY_HAZARD_AFTER_SEARCH') for p in ps),
                  'pred_searches': pred['arms'][a]['searches'],
                  'wrong_supply': sum(p['wrong_supply_delivery'] for p in ps), 'into_fire': sum(p['delivery_into_fire'] for p in ps),
                  'pred_mean_time': pred['arms'][a]['mean_time'], 'pred_unsafe': pred['arms'][a]['unsafe'],
                  'pred_false_refusals': pred['arms'][a]['false_refusals']}
        arm[a]['time_inside'] = mean_t is not None and inside(mean_t, pred['arms'][a]['mean_time'])
        arm[a]['unsafe_inside'] = inside(unsafe, pred['arms'][a]['unsafe'])
    out['arms'] = arm

    # paired by (sequence, mission)
    by = defaultdict(dict)
    for p in scored:
        by[(p['sequence'], p['k'])][p['arm']] = p
    pairs = [(v['M0'], v['M2']) for v in by.values() if 'M0' in v and 'M2' in v and not v['M0']['failed'] and not v['M2']['failed']
             and v['M0']['mission_time_s'] is not None and v['M2']['mission_time_s'] is not None]
    d = [a['mission_time_s'] - b['mission_time_s'] for a, b in pairs]
    mean_d = sum(d) / len(d) if d else None
    out['V1_time_diff'] = {'n_pairs': len(d), 'mean_M0_minus_M2_s': None if mean_d is None else round(mean_d, 2),
                           'pred': pred['paired_mean_time_diff_s']['M0-M2'],
                           'supported': mean_d is not None and inside(mean_d, pred['paired_mean_time_diff_s']['M0-M2'])}
    out['V2_unsafe_inside'] = {a: arm[a]['unsafe_inside'] for a in ARMS}
    # Amendment 1: the mechanism behind the time saving -- searches per arm within +-3 of the model (M0, M2)
    out['V2_searches_within_3'] = {a: abs(arm[a]['searches'] - pred['arms'][a]['searches']['p50']) <= 3 for a in ('M0', 'M2')}
    out['V2_supported'] = all(out['V2_unsafe_inside'].values()) and all(out['V2_searches_within_3'].values())

    # V3: speed-up replicates without scripted stories (sequence means, exact Wilcoxon)
    seq_d = defaultdict(list)
    for (a, b) in pairs:
        seq_d[a['sequence']].append(a['mission_time_s'] - b['mission_time_s'])
    sd = [sum(v) / len(v) for v in seq_d.values()]
    out['V3_speed'] = {'n_sequences': len(sd), 'median_seq_mean_diff_s': statistics.median(sd) if sd else None,
                       'wilcoxon_exact_p': float(f'{wilcoxon_exact(sd):.3g}') if sd else None}
    out['V3_speed']['supported'] = bool(sd) and statistics.median(sd) > 0 and out['V3_speed']['wilcoxon_exact_p'] < 0.05

    # V4: safety (M2 <= M0; M2 < M1 at sequence level)
    seq_unsafe = defaultdict(lambda: {a: False for a in ARMS})
    for p in scored:
        if p['unsafe_delivery']:
            seq_unsafe[p['sequence']][p['arm']] = True
    seqs = sorted({p['sequence'] for p in scored})
    b = sum(seq_unsafe[s]['M1'] and not seq_unsafe[s]['M2'] for s in seqs)
    c = sum(seq_unsafe[s]['M2'] and not seq_unsafe[s]['M1'] for s in seqs)
    margin = pred['unsafe_diff_M2_minus_M0']['p97.5']                 # Amendment 1: chance margin from the model
    out['V4_safety'] = {'M2_le_M0': arm['M2']['unsafe'] <= arm['M0']['unsafe'],
                        'M2_minus_M0': arm['M2']['unsafe'] - arm['M0']['unsafe'], 'margin': margin,
                        'M2_within_margin_of_M0': arm['M2']['unsafe'] - arm['M0']['unsafe'] <= margin,
                        'seq_unsafe': {a: sum(seq_unsafe[s][a] for s in seqs) for a in ARMS}, 'n_sequences': len(seqs),
                        'seq_mcnemar_M1_vs_M2_p': float(f'{mcnemar_exact(b, c):.3g}'), 'discordant': [b, c]}
    out['V4_safety']['supported'] = out['V4_safety']['M2_within_margin_of_M0'] and b > c and out['V4_safety']['seq_mcnemar_M1_vs_M2_p'] < 0.05
    out['claim_model_predicts'] = out['V1_time_diff']['supported'] and out['V2_supported']
    out['claim_memory_under_random_change'] = out['V3_speed']['supported'] and out['V4_safety']['supported']
    out['secondary_time_inside'] = {a: arm[a]['time_inside'] for a in ARMS}
    out['trials'] = per
    (RES / 'v_summary.json').write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n')
    print(json.dumps({k: v for k, v in out.items() if k != 'trials'}, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
