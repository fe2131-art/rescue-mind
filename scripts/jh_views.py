#!/usr/bin/env python3
"""Study JH factor analysis, part 2 (I-93; POST HOC, development, image level): does a better OBSERVATION help the judges where a second opinion on the same image did not?

  python3 scripts/jh_views.py        # experiments/results/jh_views.json
XD's image set also holds the 0.8 m side views (L2, R2) of every world.  For each view set (v36 views F+L+R at 0.4 m; the GL arm's F + L2; the wide F + L2 + R2) and each scorer (the gate Qwen3.5-9B, each judge, unions)
the threshold is the rank rule at alpha = 2% (scripts/calibration_sites.threshold, rounded up to the next thousandth) over the per-world MAXIMUM of the view set on the clean CALIBRATION worlds; misses and false stops are counted
on the TEST worlds (126 fire, 104 clean).  Worlds are XD worlds (ablation copies of a base world included); counts by base world are reported next to them.  No label of the test split enters a threshold.
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
VIEWSETS = {'v36_FLR_0.4m': ('F', 'L', 'R'), 'GL_F+L2_0.8m': ('F', 'L2'), 'wide_F+L2+R2': ('F', 'L2', 'R2'), 'all_six': ('F', 'L', 'R', 'L2', 'R2', 'N')}


def per_world(rows_by_scorer: dict, views: tuple) -> dict:
    out = {}
    for sc, rows in rows_by_scorer.items():
        d = {}
        for (w, v), s in rows.items():
            if v in views:
                d[w] = max(d.get(w, 0.0), s)
        out[sc] = d
    return out


def main():
    labels = {}
    for r in (json.loads(x) for x in (ROOT / 'experiments/vlm_testset_xd/labels.jsonl').read_text(encoding='utf8').splitlines() if x.strip()):
        labels[r['image']] = r
    info = {}
    for r in labels.values():
        info.setdefault(r['world_id'], r)
    rows = {'qwen35': {}}
    for r in json.loads((RES / 'devset_xd_h36_tiles.json').read_text(encoding='utf8'))['records']:
        p = ((r['passes'].get('1') or {}).get('scores') or {}).get('hazard_prob')
        p2 = ((r['passes'].get('2') or {}).get('scores') or {}).get('hazard_prob')
        ps = [x for x in (p, p2) if x is not None]
        if ps:
            rows['qwen35'][(r['world_id'], r['view'])] = max(ps)
    for j in ja.CANDIDATES:
        rows[j] = {}
        for r in ja.rows(RES / f'jev_scores_{j}_xd.jsonl'):
            lab = labels.get(r['key'])
            if lab:
                rows[j][(lab['world_id'], lab['view'])] = r['score']['max']
    kind = lambda w: 'fire' if (info[w]['world_kind'] == 'hazard' and info[w].get('world_perceivable_any_view')) else ('clean' if info[w]['world_kind'] in ('twin', 'ok') else 'other')
    base = lambda w: info[w].get('ablation_base') or w
    worlds = {s: [w for w in info if info[w]['split'] == s] for s in ('cal', 'test')}
    cal_clean = [w for w in worlds['cal'] if kind(w) == 'clean']
    tf = [w for w in worlds['test'] if kind(w) == 'fire']
    tc = [w for w in worlds['test'] if kind(w) == 'clean']
    out = {'post_hoc': True, 'n_cal_clean': len(cal_clean), 'n_test_fire': len(tf), 'n_test_clean': len(tc), 'viewsets': {}}
    for vs, views in VIEWSETS.items():
        pw = per_world(rows, views)
        tau = {sc: ja.tau_of([pw[sc].get(w, 0.0) for w in cal_clean]) for sc in pw}
        flag = lambda sc, w: pw[sc].get(w, 0.0) >= tau[sc]
        res = {'tau': tau, 'scorers': {}}
        for k in (0, 1, 4):
            for js in ([()] if k == 0 else (list(combinations(ja.CANDIDATES, 1)) if k == 1 else [tuple(ja.CANDIDATES)])):
                names = ('qwen35',) + js
                miss = [w for w in tf if not any(flag(n, w) for n in names)]
                fs = [w for w in tc if any(flag(n, w) for n in names)]
                res['scorers']['+'.join(names)] = {'miss': len(miss), 'miss_bases': len({base(w) for w in miss}), 'false_stops': len(fs), 'false_stop_rate': round(len(fs) / len(tc), 4)}
        for j in ja.CANDIDATES:        # judges alone, for the AUC-like picture
            miss = [w for w in tf if not flag(j, w)]
            res['scorers'][j + '_alone'] = {'miss': len(miss), 'miss_bases': len({base(w) for w in miss}), 'false_stops': sum(flag(j, w) for w in tc)}
        out['viewsets'][vs] = res
    (RES / 'jh_views.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    for vs, res in out['viewsets'].items():
        print(vs, {k: (v['miss'], v['miss_bases'], v['false_stops']) for k, v in res['scorers'].items()})


if __name__ == '__main__':
    main()
