#!/usr/bin/env python3
"""I-04: score instruction parsers on the frozen held-out set (experiments/intent_eval/held_out_v34.jsonl).

  python3 scripts/intent_eval.py --method tfidf
  python3 scripts/intent_eval.py --method llm      # needs local_vlm_server (/v1/intent) on 8765
  python3 scripts/intent_eval.py --method hybrid

Correct = (accept with the right supply) or (reject when a reject is expected).
'unsafe' counts the dangerous errors: accepting a request that should be refused,
or accepting with the WRONG supply.
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run(method: str, text: str) -> dict:
    if method == 'tfidf':
        from rescuemind.mission_policy import decide_intent
        g = decide_intent(text)
        return {'accept': g.allow, 'item': g.intent.item if g.allow else None, 'reason': g.reason}
    from rescuemind.intent_llm import parse_instruction_llm, decide_intent_hybrid
    if method == 'llm':
        r = parse_instruction_llm(text)
        return {'accept': r['accept'], 'item': r['item'] if r['accept'] else None, 'reason': r['reason'], 'probs': r['probs']}
    if method == 'hybrid':
        r = decide_intent_hybrid(text)
        return {'accept': r['accept'], 'item': r['item'] if r['accept'] else None, 'reason': r['reason']}
    raise ValueError(method)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--method', choices=['tfidf', 'llm', 'hybrid'], required=True)
    a = ap.parse_args()
    rows = [json.loads(x) for x in (ROOT / 'experiments/intent_eval/held_out_v34.jsonl').read_text().splitlines()]
    out = []
    for r in rows:
        t0 = time.perf_counter()
        got = run(a.method, r['text'])
        ok = (got['accept'] and r['expect'] == 'accept' and got['item'] == r['item']) or \
             (not got['accept'] and r['expect'] == 'reject')
        unsafe = got['accept'] and (r['expect'] == 'reject' or got['item'] != r.get('item'))
        out.append({**r, 'got': got, 'correct': ok, 'unsafe': unsafe, 'latency_s': round(time.perf_counter() - t0, 3)})
    by = {}
    for o in out:
        c = by.setdefault(o['category'], [0, 0])
        c[0] += o['correct']; c[1] += 1
    summ = {'method': a.method, 'n': len(out), 'correct': sum(o['correct'] for o in out),
            'unsafe_accepts': sum(o['unsafe'] for o in out),
            'false_rejects': sum((not o['got']['accept']) and o['expect'] == 'accept' for o in out),
            'by_category': {k: f'{v[0]}/{v[1]}' for k, v in sorted(by.items())},
            'mean_latency_s': round(sum(o['latency_s'] for o in out) / len(out), 3)}
    (ROOT / 'experiments/results' / f'intent_{a.method}.json').write_text(
        json.dumps({'summary': summ, 'records': out}, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps(summ, ensure_ascii=False))
    for o in out:
        if not o['correct']:
            print('  ✗', o['category'], o['text'], '->', o['got'].get('item'), o['got'].get('reason'))


if __name__ == '__main__':
    main()
