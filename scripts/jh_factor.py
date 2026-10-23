#!/usr/bin/env python3
"""Study JH factor analysis (I-93; POST HOC, development: the registered claim JH1 stays failed).  Why does a second judge of another family remove only 4 of the gate's 14 misses?

  python3 scripts/jh_factor.py        # experiments/results/jh_factor.json
Reads the same score files as jh_analysis.py.  Four questions:
  (1) which test worlds does the gate (tau_Q 0.088) miss, what are they (class, size, smoke type, ablation variant), and does any judge flag them at its registered tau_J;
  (2) how far below tau_J do the judges' scores of those worlds lie (a near miss is a threshold problem, a far miss is a perception problem);
  (3) what would the test worlds say if tau_J were scaled (a sensitivity curve, post hoc: it uses the test labels, so it is a diagnosis, not a tuned rule);
  (4) the union of all four judges, and of pairs, at the registered taus.
"""
import json
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
import jh_analysis as ja  # noqa: E402

RES = ROOT / 'experiments/results'


def main():
    ws = ja.xd_world_scores()
    jh = json.loads((RES / 'jh_summary.json').read_text())['xd']
    tq = jh['tau_Q']
    q = ws['qwen35']
    tf = [w for w, e in q.items() if e['split'] == 'test' and e['kind'] == 'fire']
    tc = [w for w, e in q.items() if e['split'] == 'test' and e['kind'] == 'clean']
    tau = {j: jh['candidates'][j]['tau_J'] for j in ja.CANDIDATES}
    labels = {}
    for r in (json.loads(x) for x in (ROOT / 'experiments/vlm_testset_xd/labels.jsonl').read_text(encoding='utf8').splitlines() if x.strip()):
        labels.setdefault(r['world_id'], r)
    missed = sorted(w for w in tf if q[w]['score'] < tq)
    rows = []
    for w in missed:
        lab = labels.get(w, {})
        row = {'world': w, 'cls': lab.get('cls'), 'size_class': lab.get('size_class'), 'hazard_style': lab.get('hazard_style'), 'particle_smoke': lab.get('particle_smoke'),
               'variant': lab.get('variant'), 'ablation_base': lab.get('ablation_base'), 'score_Q': round(q[w]['score'], 4), 'ratio_Q': round(q[w]['score'] / tq, 2)}
        for j in ja.CANDIDATES:
            s = (ws.get(j) or {}).get(w, {}).get('score')
            row[j] = None if s is None else {'score': round(s, 4), 'ratio_to_tau_J': round(s / tau[j], 2), 'flagged': s >= tau[j]}
        row['rescued_by'] = [j for j in ja.CANDIDATES if row[j] and row[j]['flagged']]
        rows.append(row)
    never = [r['world'] for r in rows if not r['rescued_by']]
    out = {'post_hoc': True, 'tau_Q': tq, 'tau_J': tau, 'n_test_fire': len(tf), 'n_test_clean': len(tc), 'gate_missed': rows, 'missed_by_gate_and_all_four_judges': never,
           'rescued_counts': {j: sum(1 for r in rows if j in r['rescued_by']) for j in ja.CANDIDATES}}
    # (2) near vs far: ratio score/tau_J of the worlds that stay missed by the selected judge
    sel = jh['selected']
    stay = [r[sel]['ratio_to_tau_J'] for r in rows if r[sel] and not r[sel]['flagged']]
    out['selected_judge_ratio_of_remaining_misses'] = {'judge': sel, 'ratios': sorted(stay), 'median': sorted(stay)[len(stay) // 2] if stay else None, 'n_below_half_tau': sum(x < 0.5 for x in stay)}
    # (3) sensitivity: scale tau_J (Q fixed): joint miss and union false stops on the test worlds
    sens = {}
    for j in ja.CANDIDATES:
        curve = []
        for f in (1.0, 0.75, 0.5, 0.35, 0.25, 0.15, 0.1):
            tj = tau[j] * f
            joint = sum(1 for w in tf if q[w]['score'] < tq and (ws[j].get(w) or {}).get('score', 0) < tj)
            fs = sum(1 for w in tc if q[w]['score'] >= tq or (ws[j].get(w) or {}).get('score', 0) >= tj)
            curve.append({'scale': f, 'tau_J': round(tj, 4), 'joint_miss': joint, 'union_false_stops': fs, 'union_false_stop_rate': round(fs / len(tc), 4)})
        sens[j] = curve
    out['sensitivity_post_hoc'] = sens
    # (4) unions at the registered taus
    def flagged(w, js):
        return q[w]['score'] >= tq or any((ws[j].get(w) or {}).get('score', 0) >= tau[j] for j in js)
    unions = {}
    for k in (1, 2, 3, 4):
        for js in combinations(ja.CANDIDATES, k):
            unions['+'.join(js)] = {'miss': sum(1 for w in tf if not flagged(w, js)), 'false_stops': sum(1 for w in tc if flagged(w, js))}
    out['unions_at_registered_taus'] = unions
    base = lambda w: (labels[w].get('ablation_base') or w)
    out['clusters'] = {'test_fire_worlds': len(tf), 'test_fire_bases': len({base(w) for w in tf}), 'gate_missed_worlds': len(rows), 'gate_missed_bases': len({base(r['world']) for r in rows}),
                       'rescued_worlds_any_judge': sum(1 for r in rows if r['rescued_by']), 'rescued_bases_any_judge': len({base(r['world']) for r in rows if r['rescued_by']}),
                       'rescued_bases_by_judge': {j: len({base(r['world']) for r in rows if j in r['rescued_by']}) for j in ja.CANDIDATES},
                       'unrescued_bases': len({base(w) for w in never}), 'all_four_union_miss_bases': len({base(w) for w in tf if not flagged(w, ja.CANDIDATES)})}
    qs = json.loads((RES / 'qi_summary.json').read_text()) if (RES / 'qi_summary.json').is_file() else None
    if qs:
        out['clusters'].update({'qi_baseline_miss_worlds': len(qs['xd_baseline']['miss']['worlds']), 'qi_baseline_miss_bases': len({base(w) for w in qs['xd_baseline']['miss']['worlds']}),
                                'qi_realised_miss_worlds': len(qs['R']['miss']['worlds']), 'qi_realised_miss_bases': len({base(w) for w in qs['R']['miss']['worlds']})})
    (RES / 'jh_factor.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    print('gate misses:', len(rows), '| rescued by (count):', out['rescued_counts'], '| missed by gate and all four:', len(never), never)
    print('remaining misses of', sel, '(score / tau_J):', out['selected_judge_ratio_of_remaining_misses'])
    print('clusters:', out['clusters'])
    print('unions: all four', unions['+'.join(ja.CANDIDATES)])
    for j in ja.CANDIDATES:
        print(j, [(c['scale'], c['joint_miss'], c['union_false_stops']) for c in sens[j]])
    for r in rows:
        print(r['world'], r['cls'], r['size_class'], r['hazard_style'], r['particle_smoke'], r['variant'], r['score_Q'], r['rescued_by'])


if __name__ == '__main__':
    main()
