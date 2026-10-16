#!/usr/bin/env python3
"""I-11 + I-13: choose the checkpoint configuration on DEVELOPMENT data only (rule fixed beforehand,
docs/IMPROVEMENT_LOG.md I-13).

Inputs (experiments/results/):
  devset_{v1,v2,dh}_i11_{h35,h36}_{full,tiles}.json   Qwen3.5-9B variants (h35_full = v3.5)
  devset_{v1,v2}_v35_qwen35_4b.json, devset_dh_q4b.json  Qwen3.5-4B
  devset_{v1,v2,dh}_clef.json                          Clef-Flash answering the original Jev request
Output: experiments/results/i13_selection.json
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind.clef_local import jev_role_allows  # noqa: E402

RES = ROOT / 'experiments/results'
SETS = ('v1', 'v2', 'dh')


def load(tag):
    f = RES / f'devset_{tag}.json'
    return {r['image'] + '|' + tag.split('_')[0]: r for r in json.loads(f.read_text())['records']} if f.is_file() else None


def expected(r):
    if 'expected' in r:
        return r['expected']
    return 'allow' if r['truth_supply'] == r['station'] and not r.get('truth_hazard_visible') else 'deny'


def q_allows(r, tau_h):
    for k in '12':
        p = r['passes'][k]
        if 'error' in p:
            return False
        sc = p['scores']
        probs = sc['supply_probs']
        if max(probs, key=probs.get) != r['station'] or probs[r['station']] < 0.5 or sc['hazard_prob'] >= tau_h:
            return False
    return True


def j_allows(r, tau_h):
    c = r.get('clef') or {}
    if 'error' in c or 'supply' not in c:
        return False
    return jev_role_allows(c, r['station'], hazard=tau_h)[0]


def sources(name):
    out = {}
    for s in SETS:
        d = load(f'{s}_{name}') if not name.startswith('v35_') else load(f'{s}_{name}')
        if d is None:
            return None
        out.update(d)
    return out


def main():
    q = {f'{p}_{v}': sources(f'i11_{p}_{v}') for p in ('h35', 'h36') for v in ('full', 'tiles')}
    q4 = {}
    for s, tag in (('v1', 'v1_v35_qwen35_4b'), ('v2', 'v2_v35_qwen35_4b'), ('dh', 'dh_q4b')):
        d = load(tag)
        q4 = None if d is None or q4 is None else {**q4, **{k.split('|')[0] + '|' + s: v for k, v in d.items()}}
    j = sources('clef')
    configs = {}
    for name, d in q.items():
        if d:
            for t in (0.05,):
                configs[f'Q9B[{name}] tau_h={t}'] = (d, lambda r, d=d, t=t: q_allows(r, t), name == 'h35_full', 18.3, 1 + (3 if 'tiles' in name else 0))
    if q4:
        configs['Q4B tau_h=0.05'] = (q4, lambda r: q_allows(r, 0.05), True, 9.1, 1)
    if j:
        for t in (0.35, 0.10, 0.05):
            configs[f'J(Clef) tau_h={t}'] = (j, lambda r, t=t: j_allows(r, t), True, 19.0, 0)
        for name, d in q.items():
            if d:
                for t in (0.35, 0.05):
                    configs[f'J(Clef,{t})+Q9B[{name}]'] = (
                        d, lambda r, d=d, t=t: q_allows(r, 0.05) and j_allows(j[r['_key']], t), False, 37.3,
                        1 + (3 if 'tiles' in name else 0))
        if q4:
            for t in (0.35, 0.05):
                configs[f'J(Clef,{t})+Q4B'] = (q4, lambda r, t=t: q_allows(r, 0.05) and j_allows(j[r['_key']], t), True, 28.1, 1)
    table = []
    for cname, (d, rule, deployable, vram, extra_calls) in configs.items():
        fa = fd = n_deny = n_allow = rec = n_fire = 0
        for key, r in d.items():
            r['_key'] = key
            e = expected(r)
            if e == 'ambiguous':
                continue
            a = rule(r)
            if e == 'deny':
                n_deny += 1; fa += a
            else:
                n_allow += 1; fd += not a
            if key.endswith('|dh') and r.get('hazard_visibility') == 'visible':
                n_fire += 1; rec += not a
        table.append({'config': cname, 'false_approvals': fa, 'n_deny': n_deny, 'correct_approvals': n_allow - fd,
                      'n_allow': n_allow, 'ca_rate': round((n_allow - fd) / max(n_allow, 1), 4),
                      'dh_fire_refused': rec, 'n_dh_fire': n_fire, 'deployable_one_v100': deployable,
                      'vram_gb': vram})
    ok = [t for t in table if t['false_approvals'] == 0 and t['ca_rate'] >= 0.95]
    ok.sort(key=lambda t: (-t['dh_fire_refused'], not t['deployable_one_v100'], t['vram_gb']))
    out = {'rule': __doc__, 'table': table, 'selected': ok[0] if ok else None}
    (RES / 'i13_selection.json').write_text(json.dumps(out, indent=1) + '\n')
    for t in sorted(table, key=lambda t: t['config']):
        print(f"{t['config']:38s} FA {t['false_approvals']:2d}/{t['n_deny']}  CA {t['correct_approvals']}/{t['n_allow']} "
              f"({t['ca_rate']:.3f})  DH fire refused {t['dh_fire_refused']}/{t['n_dh_fire']}  "
              f"{'deployable' if t['deployable_one_v100'] else 'NOT co-loadable'}")
    print('SELECTED', out['selected'])


if __name__ == '__main__':
    main()
