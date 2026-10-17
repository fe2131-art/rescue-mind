#!/usr/bin/env python3
"""Study W-b: score the paraphrased hazard questions (PARAPHRASE_SETS['w5'] in scripts/local_vlm_server.py) on an existing image set.

  python3 scripts/w_paraphrase_eval.py --devset experiments/vlm_testset_t2 --tag t2      # -> experiments/results/devset_w_para_t2.json

Needs a running scripts/local_vlm_server.py (any hazard flags: this endpoint does not use them).  Stores p(Yes) of the five
paraphrases and of the h36 wording on the full image for every image.  No decision is taken here; scripts/w_analysis.py does that.
Resumable: an existing output file is not overwritten.  An image that errors twice is stored with an error and counts as a refusal.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SET = 'w5'


def call(url: str, model: str, blob: bytes, name: str = SET, timeout: int = 180) -> dict:
    payload = {'model': model, 'set': name, 'image_sha256': hashlib.sha256(blob).hexdigest(),
               'image_base64': base64.b64encode(blob).decode('ascii')}
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf8'), headers={'Content-Type': 'application/json'},
                                 method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as f:
        resp = json.loads(f.read(65536).decode('utf8'))
    if (resp.get('model') != model or resp.get('real_inference') is not True or resp.get('set') != name
            or resp.get('image_sha256') != payload['image_sha256'] or len(resp.get('probs', [])) != resp.get('n_questions')):
        raise ValueError('invalid hazard_set response')
    return {'probs': resp['probs'], 'ref_h36': resp['ref_h36']}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--devset', required=True)
    ap.add_argument('--tag', required=True)
    ap.add_argument('--model', default='Qwen/Qwen3.5-9B')
    ap.add_argument('--port', type=int, default=8765)
    a = ap.parse_args(argv)
    dest = ROOT / 'experiments/results' / f'devset_w_para_{a.tag}.json'
    if dest.is_file():
        print('exists', dest); return
    dev = Path(a.devset)
    url = f'http://127.0.0.1:{a.port}/v1/hazard_set'
    rows = [json.loads(x) for x in (dev / 'labels.jsonl').read_text().splitlines()]
    out = []
    for r in rows:
        blob = (dev / r['image']).read_bytes()
        rec = dict(r)
        for attempt in (1, 2):
            t0 = time.perf_counter()
            try:
                rec['para'] = call(url, a.model, blob)
                rec['para']['latency_s'] = round(time.perf_counter() - t0, 3)
                break
            except (OSError, ValueError) as exc:
                rec['para'] = {'error': str(exc)[:200]}
        out.append(rec)
        if len(out) % 50 == 0:
            print(len(out), '/', len(rows), flush=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({'tag': f'w_para_{a.tag}', 'model': a.model, 'set': SET, 'n': len(out), 'records': out},
                               ensure_ascii=False, indent=1) + '\n')
    print('saved', dest, 'errors', sum('error' in r['para'] for r in out))


if __name__ == '__main__':
    main()
