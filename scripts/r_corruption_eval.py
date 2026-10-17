#!/usr/bin/env python3
"""Study R (experiments/PREREGISTRATION_R.md): score the running v3.6 VLM server on camera-degraded T2 images.

  python3 scripts/r_corruption_eval.py --condition gaussian_noise_M     # one condition
  python3 scripts/r_corruption_eval.py --all                            # every registered condition (resumable)

Subset (registered): the 30 even-numbered T2 worlds (t2_00, t2_02, ... t2_58), all 10 images each = 300 images.
Each image is degraded deterministically (seed = crc32 of its name), checked by the robot's own acquisition gate
(rescuemind.image_acquisition.measure_quality: a rejected frame would never reach the VLM), and scored with the same
two passes as vlm_devset_eval.py.  Output: experiments/results/devset_r_<condition>.json
"""
from __future__ import annotations
import argparse
import json
import sys
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image  # noqa: E402
from rescuemind.corruptions import CONDITIONS, corrupt_jpeg_bytes  # noqa: E402
from rescuemind.image_acquisition import measure_quality, AcquisitionRejected  # noqa: E402
from rescuemind.local_vision import _client_call, LocalInferenceError  # noqa: E402

T2 = ROOT / 'experiments/vlm_testset_t2'


def subset():
    rows = [json.loads(x) for x in (T2 / 'labels.jsonl').read_text().splitlines()]
    return [r for r in rows if int(r['world_id'].split('_')[1]) % 2 == 0]


def run(condition, model, port):
    dest = ROOT / 'experiments/results' / f'devset_r_{condition}.json'
    if dest.is_file():
        print('exists', dest); return
    url = f'http://127.0.0.1:{port}/v1/classify'
    out = []
    for r in subset():
        img = Image.open(T2 / r['image']).convert('RGB')
        blob = corrupt_jpeg_bytes(img, condition, seed=zlib.crc32(r['image'].encode()))
        import io
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
    dest.write_text(json.dumps({'tag': f'r_{condition}', 'model': model, 'n': len(out), 'records': out},
                               ensure_ascii=False, indent=1) + '\n')
    print('saved', dest, flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--condition', choices=CONDITIONS)
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--model', default='Qwen/Qwen3.5-9B')
    ap.add_argument('--port', type=int, default=8765)
    a = ap.parse_args()
    for c in (CONDITIONS if a.all else [a.condition]):
        run(c, a.model, a.port)


if __name__ == '__main__':
    main()
