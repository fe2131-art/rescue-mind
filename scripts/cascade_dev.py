#!/usr/bin/env python3
"""JEV with divided roles (docs/design/jev_roles_plan.md), development on XD (POST HOC, image level; the registered replication on fresh worlds is scripts/ji_cascade.py).

  python3 scripts/cascade_dev.py        # experiments/results/cascade_dev.json
Roles: the gate (Qwen3.5-9B) decides; a fast judge from another family is only a SENTINEL on the three standard views F, L, R: if its score reaches s_j (rank rule at alpha_s on the clean
calibration worlds, loose on purpose) the robot spends the three extra views (L2, R2, N) and the gate decides on all six (threshold tau6); otherwise the gate decides on F, L, R (tau3).
The sentinel never refuses and never approves: a sentinel false alarm costs views (time), not a delivery.  Compared with always-three, always-six and the old veto (judge OR gate).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
import jh_analysis as ja  # noqa: E402
from calibration_sites import threshold  # noqa: E402

RES = ROOT / 'experiments/results'
STD, EXTRA = ('F', 'L', 'R'), ('L2', 'R2', 'N')
ALPHAS = (0.05, 0.10, 0.20, 0.30, 0.50)


def load_xd():
    labels = {}
    for r in (json.loads(x) for x in (ROOT / 'experiments/vlm_testset_xd/labels.jsonl').read_text(encoding='utf8').splitlines() if x.strip()):
        labels[r['image']] = r
    info = {}
    for r in labels.values():
        info.setdefault(r['world_id'], r)
    rows = {'qwen35': {}}
    for r in json.loads((RES / 'devset_xd_h36_tiles.json').read_text(encoding='utf8'))['records']:
        ps = [x for x in (((r['passes'].get(k) or {}).get('scores') or {}).get('hazard_prob') for k in ('1', '2')) if x is not None]
        if ps:
            rows['qwen35'][(r['world_id'], r['view'])] = max(ps)
    for j in ja.CANDIDATES:
        rows[j] = {}
        for r in ja.rows(RES / f'jev_scores_{j}_xd.jsonl'):
            lab = labels.get(r['key'])
            if lab:
                rows[j][(lab['world_id'], lab['view'])] = r['score']['max']
    return rows, info


def pmax(rows, views):
    out = {}
    for (w, v), s in rows.items():
        if v in views:
            out[w] = max(out.get(w, 0.0), s)
    return out


def evaluate(rows, fire, clean, tau3, tau6, sentinel_j, s_j, qwen_sus=None):
    q3, q6 = pmax(rows['qwen35'], STD), pmax(rows['qwen35'], STD + EXTRA)
    js = pmax(rows[sentinel_j], STD) if sentinel_j else {}

    def one(w):
        trig = (sentinel_j is not None and js.get(w, 0.0) >= s_j) or (qwen_sus is not None and q3.get(w, 0.0) >= qwen_sus)
        flagged = q6.get(w, 0.0) >= tau6 if trig else q3.get(w, 0.0) >= tau3
        return flagged, trig
    mf = [w for w in fire if not one(w)[0]]
    fs = [w for w in clean if one(w)[0]]
    views = lambda ws: sum(3 + (3 if one(w)[1] else 0) for w in ws) / len(ws)
    return {'miss': len(mf), 'false_stops': len(fs), 'trigger_fire': round(sum(one(w)[1] for w in fire) / len(fire), 3), 'trigger_clean': round(sum(one(w)[1] for w in clean) / len(clean), 3),
            'mean_views_clean': round(views(clean), 2), 'mean_views_fire': round(views(fire), 2)}


def main():
    rows, info = load_xd()
    kind = lambda w: 'fire' if (info[w]['world_kind'] == 'hazard' and info[w].get('world_perceivable_any_view')) else ('clean' if info[w]['world_kind'] in ('twin', 'ok') else 'other')
    base = lambda w: info[w].get('ablation_base') or w
    cal = [w for w in info if info[w]['split'] == 'cal' and kind(w) == 'clean']
    fire = [w for w in info if info[w]['split'] == 'test' and kind(w) == 'fire']
    clean = [w for w in info if info[w]['split'] == 'test' and kind(w) == 'clean']
    tau3 = ja.tau_of([pmax(rows['qwen35'], STD).get(w, 0.0) for w in cal])
    tau6 = ja.tau_of([pmax(rows['qwen35'], STD + EXTRA).get(w, 0.0) for w in cal])
    out = {'post_hoc': True, 'n_cal_clean': len(cal), 'n_test_fire': len(fire), 'n_test_clean': len(clean), 'tau3': tau3, 'tau6': tau6,
           'always3': evaluate(rows, fire, clean, tau3, tau6, None, 0.0, qwen_sus=1e9), 'always6': None, 'sentinel': {}}
    out['always6'] = {**evaluate(rows, fire, clean, tau3, tau6, None, 0.0, qwen_sus=-1.0), 'note': 'trigger always on'}
    for q in (0.005, 0.01, 0.02):         # the existing adaptive_views idea (I-20): the gate's own low score as the trigger
        out['gate_own_trigger_%g' % q] = evaluate(rows, fire, clean, tau3, tau6, None, 0.0, qwen_sus=q)
    for j in ja.CANDIDATES:
        out['sentinel'][j] = {}
        for a in ALPHAS:
            s_j = threshold([pmax(rows[j], STD).get(w, 0.0) for w in cal], a)[0]
            ev = evaluate(rows, fire, clean, tau3, tau6, j, s_j)
            ev['s_j'] = s_j
            ev['miss_bases'] = len({base(w) for w in fire if w in [x for x in fire]}) and None
            out['sentinel'][j][str(a)] = ev
    (RES / 'cascade_dev.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    print('tau3', tau3, 'tau6', tau6, 'always3', out['always3']['miss'], out['always3']['false_stops'], 'always6', out['always6']['miss'], out['always6']['false_stops'])
    for k in [k for k in out if k.startswith('gate_own')]:
        print(k, {x: out[k][x] for x in ('miss', 'false_stops', 'trigger_fire', 'trigger_clean', 'mean_views_clean')})
    for j, d in out['sentinel'].items():
        for a, ev in d.items():
            print(j, a, {x: ev[x] for x in ('miss', 'false_stops', 'trigger_fire', 'trigger_clean', 'mean_views_clean', 's_j')})


if __name__ == '__main__':
    main()
