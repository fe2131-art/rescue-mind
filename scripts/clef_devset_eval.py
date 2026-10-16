#!/usr/bin/env python3
"""I-13: answer the original Jev checkpoint request with local Clef-Flash for every image of an image set.

  python3 scripts/clef_devset_eval.py --devset experiments/vlm_devset_v2 --tag v2_clef
Writes experiments/results/devset_<tag>.json (labels copied from labels.jsonl, raw Clef answers kept).
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind import clef_local  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--devset', required=True)
    ap.add_argument('--tag', required=True)
    ap.add_argument('--url', default=clef_local.DEFAULT_URL)
    ap.add_argument('--schema', choices=['jev', 'task'], default='jev', help="'jev' = original plan's request; 'task' = task wording")
    a = ap.parse_args()
    dev = Path(a.devset)
    rows = [json.loads(x) for x in (dev / 'labels.jsonl').read_text().splitlines()]
    out = []
    for r in rows:
        t0 = time.perf_counter()
        try:
            res = clef_local.infer(dev / r['image'], a.url, schema=a.schema)
        except Exception as exc:  # recorded; counts as a refusal in every rule
            res = {'error': f'{type(exc).__name__}: {exc}'[:200]}
        out.append(dict(r, clef=res, clef_wall_s=round(time.perf_counter() - t0, 3)))
        print(r['image'], r.get('truth_supply'), res.get('supply', 'ERR'), res.get('hazard_probability'), flush=True)
    dest = ROOT / 'experiments/results' / f'devset_{a.tag}.json'
    dest.write_text(json.dumps({'tag': a.tag, 'model': clef_local.MODEL_ID, 'n': len(out), 'records': out},
                               ensure_ascii=False, indent=1) + '\n')
    print('saved', dest)


if __name__ == '__main__':
    main()
