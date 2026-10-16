#!/usr/bin/env python3
"""I-13: local Jev/SystemOne-compatible decision server backed by Cloudflare Clef-Flash (Apache-2.0).

  HF_HUB_OFFLINE=1 python3 scripts/clef_server.py --port 8767

Clef-Flash is a Qwen3.5-9B post-train with a joint schema head that returns a probability for every option
of every typed question in ONE forward pass (no generated text).  Its API is Jev-compatible, so the request
built by rescuemind/jev.py (the original plan's Jev checkpoint) is answered unchanged, locally, on the V100:

  POST /v1/systemone   Jev request body; images either as Jev `assets` (base64) or `images_base64`
  GET  /health

The model's own code (joint_schema_model.py, shipped in the model repository) was reviewed before use: it only
builds the token sequence, runs the backbone and the head, and reads local files.  FP16 is used because the
V100 has no BF16 support.  Loopback only; no cloud call.
"""
from __future__ import annotations
import argparse
import base64
import io
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL_ID = 'Cloudflare/clef-flash'


class ClefWorker:
    def __init__(self, model_id: str = MODEL_ID, dtype: str = 'float16'):
        import torch
        from huggingface_hub import snapshot_download
        self.torch = torch
        self.path = snapshot_download(model_id, local_files_only=True)
        sys.path.insert(0, self.path)
        import joint_schema_model as jsm
        self.jsm = jsm
        t0 = time.perf_counter()
        self.model, self.processor = jsm.load_release_model(self.path, device='cuda',
                                                            dtype=getattr(torch, dtype))
        self.load_s = round(time.perf_counter() - t0, 1)
        self.model_id = model_id
        self.dtype = dtype

    def _images(self, request: dict):
        from PIL import Image, ImageOps
        blobs = []
        for a in (request.get('assets') or {}).values():
            if isinstance(a, dict) and a.get('type') == 'image':
                blobs.append(base64.b64decode(a['data_base64'], validate=True))
        blobs += [base64.b64decode(b, validate=True) for b in request.get('images_base64') or []]
        out = []
        for b in blobs:
            with Image.open(io.BytesIO(b)) as im:
                pic = ImageOps.exif_transpose(im).convert('RGB')
                pic.thumbnail((640, 640))
                out.append(pic)
        return out

    def systemone(self, request: dict) -> dict:
        body = {k: v for k, v in request.items() if k not in ('assets', 'images_base64')}
        images = self._images(request)
        if images:
            body['images'] = images
        t0 = time.perf_counter()
        resp = self.jsm.systemone(self.model, self.processor, body)
        for a in resp['answers'].values():
            if a['type'] == 'noul' and not (0 <= a['noul'] <= 1):
                raise RuntimeError('non-finite Clef output - refuse to decide')
        resp['model'] = self.model_id
        resp['usage']['latency_s'] = round(time.perf_counter() - t0, 3)
        resp['usage']['dtype'] = self.dtype
        return resp


def make_handler(worker: ClefWorker):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != '/health':
                self.send_error(404); return
            self.reply(200, {'status': 'ready', 'model': worker.model_id, 'backend': 'local_transformers',
                             'api': 'jev-systemone', 'dtype': worker.dtype, 'load_s': worker.load_s})

        def do_POST(self):
            if self.path != '/v1/systemone':
                self.send_error(404); return
            n = int(self.headers.get('Content-Length', '0'))
            if n < 20 or n > 12_000_000:
                self.send_error(413); return
            try:
                request = json.loads(self.rfile.read(n))
                if not isinstance(request, dict):
                    raise ValueError('request must be an object')
                self.reply(200, {'backend': 'local_transformers', 'real_inference': True, **worker.systemone(request)})
            except Exception as exc:  # fail closed: the client treats any error as a refusal
                self.reply(400, {'error': f'{type(exc).__name__}: {exc}'[:300]})

        def reply(self, code, obj):
            data = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt, *args):
            sys.stderr.write('clef: ' + fmt % args + '\n')
    return Handler


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--port', type=int, default=8767)
    p.add_argument('--dtype', choices=['float16', 'float32'], default='float16')
    a = p.parse_args()
    worker = ClefWorker(dtype=a.dtype)
    print(f'clef ready on 127.0.0.1:{a.port} (load {worker.load_s} s)', flush=True)
    ThreadingHTTPServer(('127.0.0.1', a.port), make_handler(worker)).serve_forever()


if __name__ == '__main__':
    main()
