#!/usr/bin/env python3
"""Score a running local VLM server on the Gazebo development set.

Each dev image was taken at a station whose *requested* supply is the station
name (water/medicine); the mission must ALLOW only when the truth supply equals
that request.  Raw per-pass responses are saved so thresholds can be swept
offline without re-running the model.  Development data only, never the test.
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind.local_vision import _client_call, LocalInferenceError  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--devset', default=str(ROOT / 'experiments/vlm_devset'))
    ap.add_argument('--model', default='Qwen/Qwen2.5-VL-3B-Instruct')
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--tag', required=True, help='e.g. qwen3b_scored')
    a = ap.parse_args(argv)
    dev = Path(a.devset)
    rows = [json.loads(x) for x in (dev / 'labels.jsonl').read_text().splitlines()]
    url = f'http://127.0.0.1:{a.port}/v1/classify'
    out = []
    for r in rows:
        blob = (dev / r['image']).read_bytes()
        rec = dict(r, passes={})
        for pass_id in (1, 2):
            t0 = time.perf_counter()
            try:
                resp = _client_call(url, a.model, blob, pass_id, timeout=120)
                rec['passes'][str(pass_id)] = {'supply': resp['result']['supply'],
                                               'scene': resp['result']['scene'],
                                               'scores': resp.get('scores'),
                                               'latency_s': round(time.perf_counter() - t0, 3)}
            except (LocalInferenceError, OSError, ValueError) as exc:
                rec['passes'][str(pass_id)] = {'error': str(exc)[:200],
                                               'latency_s': round(time.perf_counter() - t0, 3)}
        out.append(rec)
        p1, p2 = rec['passes']['1'], rec['passes']['2']
        print(r['image'], r['truth_supply'], '|', p1.get('supply', 'ERR'), p2.get('supply', 'ERR'), flush=True)
    dest = ROOT / 'experiments/results' / f'devset_{a.tag}.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({'tag': a.tag, 'model': a.model, 'n': len(out), 'records': out},
                               ensure_ascii=False, indent=1) + '\n')
    print('saved', dest)


if __name__ == '__main__':
    main()
