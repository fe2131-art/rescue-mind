#!/usr/bin/env python3
"""Analyse the held-out test set T1 exactly as pre-registered (experiments/PREREGISTRATION_T1.md).

  python3 scripts/t1_analysis.py            # -> experiments/results/t1_summary.json (+ printed tables)

Inputs: experiments/results/devset_t1_<tag>.json written by scripts/vlm_devset_eval.py.
Primary: frozen system (Qwen3.5-9B, v35, tau_s = tau_h = 0.50) on non-ambiguous images.
"""
from __future__ import annotations
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'
TAU_S = TAU_H = 0.50
MODELS = {'Qwen3.5-9B': 't1_qwen35_9b', 'Qwen3.5-4B': 't1_qwen35_4b', 'Qwen3-VL-8B': 't1_qwen3vl8b',
          'Qwen2.5-VL-3B': 't1_qwen25vl3b'}
JSON_RUNS = {'Qwen3.5-9B': 't1_json_qwen35_9b', 'Qwen2.5-VL-3B': 't1_json_qwen25vl3b'}
PRIMARY = 'Qwen3.5-9B'


def wilson(k: int, n: int, z: float = 1.959964) -> list:
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def _pass_ok(p: dict, station: str, *, tau_s, tau_h, use_hazard=True):
    if 'error' in p:
        return False                      # fail-closed
    sc = p.get('scores')
    if not sc or sc.get('method') != 'closed_set_logprob':
        # free-form JSON generation: labels only
        return p.get('supply') == station and (not use_hazard or p.get('scene') != 'hazard')
    probs = sc['supply_probs']
    if max(probs, key=probs.get) != station or probs[station] < tau_s:
        return False
    return not use_hazard or sc['hazard_prob'] < tau_h


RULES = {
    'full': dict(passes='12'),
    'A1_pass1_only': dict(passes='1'),
    'A2_pass2_only': dict(passes='2'),
    'A3_no_hazard_question': dict(passes='12', use_hazard=False),
    'A4_no_confidence_threshold': dict(passes='12', tau_s=0.0),
    # amendment 3: v3.5 configuration (I-10), pre-specified secondary
    'v35_tau_h_0.05': dict(passes='12', tau_h=0.05),
}


def decide(r: dict, passes='12', tau_s=TAU_S, tau_h=TAU_H, use_hazard=True) -> bool:
    return all(_pass_ok(r['passes'][k], r['station'], tau_s=tau_s, tau_h=tau_h, use_hazard=use_hazard) for k in passes)


def stratum(r: dict) -> str:
    if r['hazard_visibility'] == 'visible':
        return 'fire_visible_correct_supply' if r['truth_supply'] == r['station'] else 'fire_visible_wrong_supply'
    if r.get('distractor_at') == r['station']:
        return f"{r['distractor_kind']}_{r['scene']}"
    return f"{r['scene']}_plain"


def metrics(rows: list, allow: list) -> dict:
    neg = [a for r, a in zip(rows, allow) if r['expected'] == 'deny']
    pos = [a for r, a in zip(rows, allow) if r['expected'] == 'allow']
    fa, ca = sum(neg), sum(pos)
    return {'n_deny': len(neg), 'false_approvals': fa, 'fa_rate': round(fa / len(neg), 4), 'fa_ci95': wilson(fa, len(neg)),
            'n_allow': len(pos), 'correct_approvals': ca, 'ca_rate': round(ca / len(pos), 4), 'ca_ci95': wilson(ca, len(pos)),
            'accuracy': round((len(neg) - fa + ca) / (len(neg) + len(pos)), 4)}


def paired(rows, a, b) -> dict:
    ok_a = [x == (r['expected'] == 'allow') for r, x in zip(rows, a)]
    ok_b = [x == (r['expected'] == 'allow') for r, x in zip(rows, b)]
    bb = sum(x and not y for x, y in zip(ok_a, ok_b))
    cc = sum(y and not x for x, y in zip(ok_a, ok_b))
    return {'reference_only_correct': bb, 'variant_only_correct': cc, 'mcnemar_p': round(mcnemar_exact(bb, cc), 5)}


def load(tag: str):
    f = RES / f'devset_{tag}.json'
    if not f.is_file():
        return None
    return json.loads(f.read_text())['records']


def main():
    spec = {w['id']: w for w in json.loads((ROOT / 'experiments/vlm_testset_t1/spec.json').read_text())}
    out = {'registered': 'experiments/PREREGISTRATION_T1.md', 'tau_s': TAU_S, 'tau_h': TAU_H, 'models': {}, 'json_method': {}}
    primary_allow = None
    all_rows = None
    for name, tag in MODELS.items():
        recs = load(tag)
        if recs is None:
            continue
        rows = [r for r in recs if r['expected'] != 'ambiguous']
        amb = [r for r in recs if r['expected'] == 'ambiguous']
        errors = sum('error' in p for r in recs for p in r['passes'].values())
        m = {'n_images': len(recs), 'n_ambiguous': len(amb), 'inference_errors': errors, 'rules': {}}
        decisions = {k: [decide(r, **v) for r in rows] for k, v in RULES.items()}
        for k, d in decisions.items():
            m['rules'][k] = metrics(rows, d)
            if k != 'full':
                m['rules'][k]['vs_full'] = paired(rows, decisions['full'], d)
        full = decisions['full']
        strata = {}
        for r, a in zip(rows, full):
            s = strata.setdefault(stratum(r), {'n': 0, 'allowed': 0, 'expected': r['expected']})
            s['n'] += 1; s['allowed'] += a
        m['strata_full'] = strata
        m['ambiguous_allowed'] = sum(decide(r) for r in amb)
        # hazard detector alone (any pass >= tau_h) on correct-supply images
        haz = lambda r: max(r['passes'][k]['scores']['hazard_prob'] for k in '12' if 'scores' in r['passes'][k])
        fire = [r for r in rows if r['hazard_visibility'] == 'visible']
        cone = [r for r in rows if r.get('distractor_kind') == 'cone' and r.get('distractor_at') == r['station']]
        nofire = [r for r in rows if r['hazard_visibility'] == 'hidden']
        m['hazard_recall'] = [sum(haz(r) >= TAU_H for r in fire), len(fire)]
        m['hazard_false_alarm_cone'] = [sum(haz(r) >= TAU_H for r in cone), len(cone)]
        m['hazard_false_alarm_all_no_fire'] = [sum(haz(r) >= TAU_H for r in nofire), len(nofire)]
        # amendment 3: the same counts at the v3.5 threshold
        m['hazard_recall_tau_h_0.05'] = [sum(haz(r) >= 0.05 for r in fire), len(fire)]
        m['hazard_false_alarm_cone_tau_h_0.05'] = [sum(haz(r) >= 0.05 for r in cone), len(cone)]
        m['hazard_false_alarm_all_no_fire_tau_h_0.05'] = [sum(haz(r) >= 0.05 for r in nofire), len(nofire)]
        m['hazard_prob_fire_sorted'] = sorted(round(haz(r), 4) for r in fire)
        m['hazard_prob_no_fire_top10'] = sorted(round(haz(r), 4) for r in nofire)[-10:]
        # lighting / distance tertiles (frozen rule)
        for key, val in (('lighting_intensity', lambda r: float(spec[r['world_id']]['lighting_params']['intensity'])),
                         ('distance_m', lambda r: r['distance_m'])):
            vals = sorted(val(r) for r in rows)
            cuts = [vals[len(vals) // 3], vals[2 * len(vals) // 3]]
            bins = {}
            for r, a in zip(rows, full):
                b = 'low' if val(r) < cuts[0] else 'mid' if val(r) < cuts[1] else 'high'
                e = bins.setdefault(b, {'n': 0, 'errors': 0})
                e['n'] += 1; e['errors'] += a != (r['expected'] == 'allow')
            m[f'tertiles_{key}'] = {'cuts': [round(c, 3) for c in cuts], **bins}
        # risk-coverage over tau_s (descriptive only; thresholds stay frozen)
        curve = []
        for i in range(0, 101, 2):
            t = i / 100
            d = [decide(r, tau_s=t) for r in rows]
            mm = metrics(rows, d)
            curve.append([t, mm['fa_rate'], mm['ca_rate']])
        m['risk_coverage'] = curve
        lat = [p['latency_s'] for r in recs for p in r['passes'].values() if 'latency_s' in p]
        m['latency_per_pass_s'] = {'median': round(sorted(lat)[len(lat) // 2], 3), 'mean': round(sum(lat) / len(lat), 3)}
        m['errors_full'] = [(r['image'], stratum(r), 'FALSE_APPROVAL' if a else 'false_denial')
                            for r, a in zip(rows, full) if a != (r['expected'] == 'allow')]
        out['models'][name] = m
        if name == PRIMARY:
            primary_allow, all_rows = full, rows
    if primary_allow is not None:
        for name, m in out['models'].items():
            if name != PRIMARY:
                d = [decide(r) for r in [r for r in load(MODELS[name]) if r['expected'] != 'ambiguous']]
                m['vs_primary'] = paired(all_rows, primary_allow, d)
    for name, tag in JSON_RUNS.items():
        recs = load(tag)
        if recs is None:
            out['json_method'][name] = 'not run'
            continue
        rows = [r for r in recs if r['expected'] != 'ambiguous']
        d = [decide(r) for r in rows]
        mm = metrics(rows, d)
        mm['parse_or_inference_errors'] = sum('error' in p for r in recs for p in r['passes'].values())
        if primary_allow is not None:
            mm['vs_primary'] = paired(all_rows, primary_allow, d)
        out['json_method'][name] = mm
    (RES / 't1_summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    for name, m in out['models'].items():
        f = m['rules']['full']
        print(f"{name:14s} FA {f['false_approvals']}/{f['n_deny']} {f['fa_ci95']}  CA {f['correct_approvals']}/{f['n_allow']} "
              f"{f['ca_ci95']}  hazard {m['hazard_recall']} cone-alarm {m['hazard_false_alarm_cone']} err {m['inference_errors']}")
        for k, v in m['rules'].items():
            if k != 'full':
                print(f"    {k:28s} FA {v['false_approvals']:3d}  CA {v['correct_approvals']:3d}  p={v['vs_full']['mcnemar_p']}")
    for name, v in out['json_method'].items():
        print('json', name, v if isinstance(v, str) else
              f"FA {v['false_approvals']}/{v['n_deny']} CA {v['correct_approvals']}/{v['n_allow']} errors {v['parse_or_inference_errors']}")


if __name__ == '__main__':
    main()
