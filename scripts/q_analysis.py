#!/usr/bin/env python3
"""Study Q analysis, exactly as pre-registered (experiments/PREREGISTRATION_Q.md).

  python3 scripts/q_analysis.py        # -> experiments/results/q_summary.json (+ printed tables)

Inputs (experiments/results/): q_scores_qwen9b_v35.jsonl, q_scores_siglip.json, q_scores_clip.json (the last two optional).
Decision of the VLM check (supply part of Eq. 1, hazard ignored): approve iff in BOTH option-permuted passes the arg-max supply is
the requested one and its closed-set probability is >= tau_s = 0.5.  A pass with an error counts as a refusal.
Baselines: Z's rule with Z's frozen thresholds (arg-max is the requested supply and its probability >= 0.34; no hazard term).
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.t1_analysis import wilson, mcnemar_exact  # noqa: E402

RES = ROOT / 'experiments/results'
VLM = RES / 'q_scores_qwen9b_v35.jsonl'
ZS = {'siglip': RES / 'q_scores_siglip.json', 'clip': RES / 'q_scores_clip.json'}
TAU_S = 0.5
TAU_S_ZS = 0.34                    # study Z, selected on development data only (z_thresholds.json)
SENSITIVITY = (0.5, 0.7, 0.9)      # descriptive only
# pre-registered criteria
FA_UPPER_MAX = 0.05                # safety: Wilson 95% upper bound of the false-approval rate on all must-refuse images
CA_MIN = 0.70                      # availability: point estimate of the correct-approval rate on must-approve images
TYPE_ALERT = 3                     # a confuser type with at least this many false approvals is named


def vlm_approves(rec: dict, tau_s: float = TAU_S) -> bool:
    for k in ('1', '2'):
        p = (rec.get('passes') or {}).get(k) or {}
        if 'error' in p or 'scores' not in p:
            return False
        probs = p['scores']['supply_probs']
        if max(probs, key=probs.get) != rec['requested'] or probs[rec['requested']] < tau_s:
            return False
    return True


def zs_approves(probs: dict, requested: str, tau_s: float = TAU_S_ZS) -> bool:
    return max(probs, key=probs.get) == requested and probs[requested] >= tau_s


def counts(approved: dict, recs: list) -> dict:
    deny = [r for r in recs if r['expected'] == 'deny']
    allow = [r for r in recs if r['expected'] == 'allow']
    fa, ca = sum(approved[r['id']] for r in deny), sum(approved[r['id']] for r in allow)
    return {'FA': fa, 'n_deny': len(deny), 'FA_rate': round(fa / len(deny), 4) if deny else None, 'FA_ci': wilson(fa, len(deny)),
            'CA': ca, 'n_allow': len(allow), 'CA_rate': round(ca / len(allow), 4) if allow else None, 'CA_ci': wilson(ca, len(allow))}


def breakdown(approved: dict, recs: list) -> dict:
    """False approvals by kind of refusal (wrong supply, each neither type) and correct approvals by class."""
    out = {'false_approvals': {}, 'correct_approvals': {}}
    kinds = sorted({r['refusal_kind'] for r in recs if r['expected'] == 'deny'})
    for k in kinds:
        sel = [r for r in recs if r['expected'] == 'deny' and r['refusal_kind'] == k]
        out['false_approvals'][k] = {'k': sum(approved[r['id']] for r in sel), 'n': len(sel),
                                     'ci95': wilson(sum(approved[r['id']] for r in sel), len(sel))}
    for c in ('water', 'medicine'):
        sel = [r for r in recs if r['expected'] == 'allow' and r['class'] == c]
        out['correct_approvals'][c] = {'k': sum(approved[r['id']] for r in sel), 'n': len(sel),
                                       'ci95': wilson(sum(approved[r['id']] for r in sel), len(sel))}
    neither = [r for r in recs if r['class'] == 'neither']
    out['false_approvals']['neither_all'] = {'k': sum(approved[r['id']] for r in neither), 'n': len(neither),
                                             'ci95': wilson(sum(approved[r['id']] for r in neither), len(neither))}
    out['types_at_or_above_alert'] = [k for k, v in out['false_approvals'].items() if k not in ('neither_all',) and v['k'] >= TYPE_ALERT]
    return out


def paired(recs: list, a: dict, b: dict) -> dict:
    """Exact McNemar, system a vs baseline b, on must-refuse and must-approve images."""
    out = {}
    for label in ('deny', 'allow'):
        sel = [r['id'] for r in recs if r['expected'] == label]
        only_a = sum(a[i] and not b[i] for i in sel)
        only_b = sum(b[i] and not a[i] for i in sel)
        out[label] = {'ours_only_approved': only_a, 'baseline_only_approved': only_b, 'p': round(mcnemar_exact(only_a, only_b), 6)}
    return out


def claims(c: dict) -> dict:
    """Pre-registered criteria on the Qwen3.5-9B check."""
    safe = c['FA_ci'][1] is not None and c['FA_ci'][1] <= FA_UPPER_MAX
    avail = c['CA_rate'] is not None and c['CA_rate'] >= CA_MIN
    return {'safety_FA_upper_bound_le_0.05': bool(safe), 'availability_CA_ge_0.70': bool(avail),
            'supply_check_transfers': bool(safe and avail),
            'verdict': ('supported: the supply check transfers to real photographs' if safe and avail else
                        'not supported: ' + ', '.join(n for n, ok in (('false approvals too frequent (upper bound > 5%)', safe),
                                                                      ('correct approvals < 70%', avail)) if not ok))}


def compare_outcome(c_ours: dict, c_base: dict, pair: dict) -> str:
    """Study Z's claim rule, applied to this test set."""
    res = []
    if c_ours['FA'] < c_base['FA'] and pair['deny']['p'] < 0.05 and not (c_ours['CA'] < c_base['CA'] and pair['allow']['p'] < 0.05):
        res.append('the VLM check is safer than the baseline')
    if c_ours['CA'] > c_base['CA'] and pair['allow']['p'] < 0.05 and not (c_ours['FA'] > c_base['FA'] and pair['deny']['p'] < 0.05):
        res.append('the VLM check is more available than the baseline')
    return '; '.join(res) if res else 'no significant difference (counts reported)'


def load_vlm(path: Path = VLM) -> list:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def analyse(recs: list, zs_scores: dict | None = None) -> dict:
    ours = {r['id']: vlm_approves(r) for r in recs}
    out = {'registered': 'experiments/PREREGISTRATION_Q.md', 'n': len(recs),
           'classes': {c: sum(r['class'] == c for r in recs) for c in ('water', 'medicine', 'neither')},
           'n_pass_errors': sum('error' in (r['passes'].get(k) or {}) for r in recs for k in ('1', '2')),
           'qwen9b_v35': counts(ours, recs), 'breakdown': breakdown(ours, recs)}
    out['qwen9b_v35']['claim'] = claims(out['qwen9b_v35'])
    out['tau_s_sensitivity'] = {str(t): {k: v for k, v in counts({r['id']: vlm_approves(r, t) for r in recs}, recs).items()
                                         if k in ('FA', 'n_deny', 'CA', 'n_allow')} for t in SENSITIVITY}
    for name, scores in (zs_scores or {}).items():
        base = {r['id']: zs_approves(scores[str(r['id'])], r['requested']) for r in recs}
        out[name] = {'counts': counts(base, recs), 'breakdown': breakdown(base, recs), 'mcnemar_vs_qwen': paired(recs, ours, base)}
        out[name]['outcome'] = compare_outcome(out['qwen9b_v35'], out[name]['counts'], out[name]['mcnemar_vs_qwen'])
    return out


def main():
    recs = load_vlm()
    zs = {}
    for name, f in ZS.items():
        if f.is_file():
            zs[name] = json.loads(f.read_text())['scores']
    out = analyse(recs, zs)
    (RES / 'q_summary.json').write_text(json.dumps(out, indent=1) + '\n')
    c = out['qwen9b_v35']
    print(f"n={out['n']}  Qwen3.5-9B  FA {c['FA']}/{c['n_deny']} {c['FA_ci']}  CA {c['CA']}/{c['n_allow']} {c['CA_ci']}")
    print(c['claim']['verdict'])
    print('false approvals by kind:', {k: f"{v['k']}/{v['n']}" for k, v in out['breakdown']['false_approvals'].items()})
    for name in zs:
        v = out[name]
        print(f"{name}: FA {v['counts']['FA']}/{v['counts']['n_deny']}  CA {v['counts']['CA']}/{v['counts']['n_allow']}  {v['outcome']}")


if __name__ == '__main__':
    main()
