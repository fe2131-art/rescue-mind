#!/usr/bin/env python3
"""Study W-a secondary (optional): the W fire-world views under study R's 12 camera degradations.

  python3 scripts/w_degraded_eval.py --all            # every registered condition, resumable
  python3 scripts/w_degraded_eval.py --condition jpeg_M

Subset (registered): perceivable fire worlds whose number is even (wf000, wf002, ...), all three views.  Each image is degraded
as in scripts/r_corruption_eval.py (seed = crc32 of its name), checked by the robot's acquisition gate (a rejected frame never
reaches the VLM and counts as a refusal), and scored with the same two passes as vlm_devset_eval.py.  Needs a running v3.6
server (--hazard-prompt h36 --hazard-views tiles).  Output: experiments/results/devset_w_r_<condition>.json
"""
from __future__ import annotations
import argparse
import io
import json
import sys
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
W = ROOT / 'experiments/vlm_testset_w'


def subset(rows: list) -> list:
    return [r for r in rows if r['world_kind'] == 'fire' and r['world_perceivable'] and int(r['world_id'][2:]) % 2 == 0]


def run(condition: str, model: str, port: int):
    from PIL import Image
    from rescuemind.corruptions import corrupt_jpeg_bytes
    from rescuemind.image_acquisition import AcquisitionRejected, measure_quality
    from rescuemind.local_vision import LocalInferenceError, _client_call
    dest = ROOT / 'experiments/results' / f'devset_w_r_{condition}.json'
    if dest.is_file():
        print('exists', dest); return
    url = f'http://127.0.0.1:{port}/v1/classify'
    rows = subset([json.loads(x) for x in (W / 'labels.jsonl').read_text().splitlines()])
    out = []
    for r in rows:
        img = Image.open(W / r['image']).convert('RGB')
        blob = corrupt_jpeg_bytes(img, condition, seed=zlib.crc32(r['image'].encode()))
        try:
            q = measure_quality(Image.open(io.BytesIO(blob)))
        except AcquisitionRejected as exc:
            q = {'quality_ok': False, 'reasons': [str(exc)]}
        rec = dict(r, condition=condition, quality=q, passes={})
        for pass_id in (1, 2):
            t0 = time.perf_counter()
            try:
                resp = _client_call(url, model, blob, pass_id, timeout=120)
                rec['passes'][str(pass_id)] = {'supply': resp['result']['supply'], 'scene': resp['result']['scene'],
                                               'scores': resp.get('scores'), 'latency_s': round(time.perf_counter() - t0, 3)}
            except (LocalInferenceError, OSError, ValueError) as exc:
                rec['passes'][str(pass_id)] = {'error': str(exc)[:200], 'latency_s': round(time.perf_counter() - t0, 3)}
        out.append(rec)
    dest.write_text(json.dumps({'tag': f'w_r_{condition}', 'model': model, 'n': len(out), 'records': out},
                               ensure_ascii=False, indent=1) + '\n')
    print('saved', dest, flush=True)


def main():
    from rescuemind.corruptions import CONDITIONS
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--condition', choices=CONDITIONS)
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--model', default='Qwen/Qwen3.5-9B')
    ap.add_argument('--port', type=int, default=8765)
    a = ap.parse_args()
    if not a.all and not a.condition:
        ap.error('give --condition or --all')
    for c in (CONDITIONS if a.all else [a.condition]):
        run(c, a.model, a.port)


if __name__ == '__main__':
    main()
