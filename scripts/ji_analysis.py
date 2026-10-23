#!/usr/bin/env python3
"""Study JI (I-94; experiments/PREREGISTRATION_JI.md): the registered analysis.

  python3 scripts/ji_analysis.py        # -> experiments/results/ji_summary.json
Fresh set: 120 fire worlds (small partly hidden fire) and their 120 fire-free twins, six views each.  Scores: the frozen gate (devset_ji_h36_tiles.json, both passes, fail-closed) and the four judges
(jev_scores_<judge>_ji.jsonl).  Per-world score = the maximum over the views of a view set; thresholds are FROZEN from XD (experiments/ji_thresholds.json), nothing is fitted on JI.
Claims (registered):
  JI1  the gate alone on the six views misses at most 8 of the 120 fire worlds (exact one-sided 95% Clopper-Pearson upper bound reported).
  JI2  the six views miss fewer fires than the submitted three views (F, L, R at 0.4 m): exact ONE-sided McNemar over fire worlds p < 0.05 and fewer.
  JI3  the six-view gate stops at most 5 of the 120 fire-free twins.
  JI4  the gate with the InternVL3 veto on the six views: at most 3 of the 120 fire worlds missed by both, at most 6 of the 120 twins stopped by either (the judge and its threshold were chosen on XD).
Descriptive: the other view sets, the other judges and their unions, strata (particle smoke), the view that catches each fire.
"""
from __future__ import annotations
import json
import math
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from scripts.x_analysis import cp_upper  # noqa: E402
from scripts.xd_analysis import hazard_score  # noqa: E402

RES = ROOT / 'experiments/results'
JUDGES = ('internvl3', 'idefics3', 'qwen3vl', 'smolvlm2')
JI1_MAX_MISS, JI3_MAX_FS, JI4_MAX_JOINT, JI4_MAX_FS = 8, 5, 3, 6


def mcnemar_one_sided(b: int, c: int) -> float:
    d = b + c
    return 1.0 if d == 0 else sum(math.comb(d, i) for i in range(b, d + 1)) / 2 ** d


def load_scores(res: Path = RES) -> tuple:
    """-> (scores, kind): scores[scorer][(world, view)] = score; kind[world] = 'fire' | 'clean'."""
    sc = {'qwen35': {}}
    kind = {}
    for r in json.loads((res / 'devset_ji_h36_tiles.json').read_text(encoding='utf8'))['records']:
        sc['qwen35'][(r['world_id'], r['view'])] = hazard_score(r)
        kind[r['world_id']] = 'fire' if r['world_kind'] == 'hazard' else 'clean'
    for j in JUDGES:
        f = res / f'jev_scores_{j}_ji.jsonl'
        sc[j] = {}
        if f.is_file():
            for x in f.read_text(encoding='utf8').splitlines():
                if x.strip():
                    r = json.loads(x)
                    sc[j][(r['world'], r['view'])] = r['score']['max']
    return sc, kind


def analyse(sc: dict, kind: dict, thr: dict) -> dict:
    fire = sorted(w for w, k in kind.items() if k == 'fire')
    clean = sorted(w for w, k in kind.items() if k == 'clean')
    out = {'n_fire': len(fire), 'n_clean': len(clean), 'viewsets': {}}
    for vs, views in thr['viewsets'].items():
        tau = thr['tau'][vs]
        pw = {s: {} for s in sc}
        for s, d in sc.items():
            for (w, v), x in d.items():
                if v in views:
                    pw[s][w] = max(pw[s].get(w, 0.0), x)
        flag = lambda s, w: pw[s].get(w, 0.0) >= tau[s]
        res = {'tau': tau, 'scorers': {}}
        for names in [('qwen35',)] + [('qwen35', j) for j in JUDGES] + [('qwen35',) + JUDGES]:
            miss = [w for w in fire if not any(flag(n, w) for n in names)]
            fs = [w for w in clean if any(flag(n, w) for n in names)]
            res['scorers']['+'.join(names)] = {'miss': len(miss), 'miss_rate': round(len(miss) / len(fire), 4) if fire else None, 'miss_upper95': round(cp_upper(len(miss), len(fire)), 4) if fire else None,
                                               'false_stops': len(fs), 'false_stop_rate': round(len(fs) / len(clean), 4) if clean else None, 'missed_worlds': miss}
        out['viewsets'][vs] = res
    g6, g3 = out['viewsets']['all_six']['scorers']['qwen35'], out['viewsets']['v36_FLR']['scorers']['qwen35']
    m6, m3 = set(g6['missed_worlds']), set(g3['missed_worlds'])
    b, c = len(m3 - m6), len(m6 - m3)          # b: missed by three views only, c: missed by six views only
    out['paired_six_vs_three'] = {'three_only': b, 'six_only': c, 'mcnemar_one_sided_p': round(mcnemar_one_sided(b, c), 5) if (b + c) else 1.0}
    j4 = out['viewsets']['all_six']['scorers']['qwen35+internvl3']
    out['claims'] = {
        'JI1_gate_six_views_miss_at_most_8': g6['miss'] <= JI1_MAX_MISS,
        'JI2_six_views_fewer_misses_than_three': b > c and out['paired_six_vs_three']['mcnemar_one_sided_p'] < 0.05,
        'JI3_gate_six_views_false_stops_at_most_5': g6['false_stops'] <= JI3_MAX_FS,
        'JI4_internvl3_veto_joint_miss_at_most_3_and_false_stops_at_most_6': j4['miss'] <= JI4_MAX_JOINT and j4['false_stops'] <= JI4_MAX_FS}
    # descriptive: the view that catches each fire (largest score / tau among the six), by particle smoke is in the protocol (not in labels): counted by view only
    tau6 = thr['tau']['all_six']['qwen35']
    first = {}
    for w in fire:
        best = max(((sc['qwen35'].get((w, v), 0.0) / tau6, v) for v in thr['viewsets']['all_six']), default=(0, None))
        first[best[1]] = first.get(best[1], 0) + (1 if best[0] >= 1 else 0)
    out['gate_catching_view_counts'] = first
    return out


def main(argv=None):
    thr = json.loads((ROOT / 'experiments/ji_thresholds.json').read_text())
    sc, kind = load_scores()
    out = analyse(sc, kind, thr)
    (RES / 'ji_summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({'claims': out['claims'], 'paired': out['paired_six_vs_three'], 'gate_three': {k: out['viewsets']['v36_FLR']['scorers']['qwen35'][k] for k in ('miss', 'false_stops')},
                      'gate_six': {k: out['viewsets']['all_six']['scorers']['qwen35'][k] for k in ('miss', 'false_stops')}}))


if __name__ == '__main__':
    main()
