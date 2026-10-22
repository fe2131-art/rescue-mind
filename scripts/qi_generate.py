#!/usr/bin/env python3
"""Study QI (I-82, docs/QWENIMAGE_DESIGN.md): images from Qwen-Image-2.1-Turbo for the realism / data-expansion study.  Resumable; GPU job (run inside rm-next with PYTHONPATH=/hf/qi_pylib).

  R  photo-realise an XD image (whole frame; ground truth = the original label)
  G  put a fire into the CLEAN TWIN of an XD fire world, only inside the dilated fire mask of the fire world (pixels outside the mask are the twin's own bytes)
  C  control for G: the same edit pipeline with a neutral prompt inside the same mask (artifacts of the pipeline alone)

Every output is composited back at 640 x 480 (XD's size) and carries a manifest row with a quality check; a failed check is listed, never dropped.
  python3 scripts/qi_generate.py --mode G --limit 3
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'experiments/vlm_testset_xd'
OUT = ROOT / 'outputs/qi'
RES = ROOT / 'experiments/results'
MODEL = '/hf/jev_models/Qwen-Image-2.1-Turbo'
W, H = 1024, 768                                    # 4:3, multiples of 16; XD frames are 640 x 480
DILATE_PX = 12
PROMPTS = {
    'R': ('Convert this 3D-rendered image into a photograph shot on a real camera: replace the flat computer-graphics shading with real materials (corrugated cardboard fibres, shrink-wrap, scuffed painted steel, worn concrete), '
           'natural uneven lighting, film grain and slight depth of field. The composition, every object and its position, and any fire, flame or smoke must stay exactly the same; add nothing and remove nothing.'),
    'R0': ('Redraw this simulated warehouse camera image as a real photograph taken by a robot camera in a real warehouse. Keep every object, its position, shape and colour exactly where it is, '
          'and keep any fire, flame or smoke exactly where it is. Do not add or remove anything.'),
    'R2': ('A real photograph taken with a mobile robot\'s wide-angle camera inside a real, slightly dusty warehouse: natural lighting, realistic cardboard and plastic textures, subtle sensor noise and lens softness, '
           'a worn concrete floor. Keep the same layout, the same objects in the same places and the same colours; keep any fire, flame or smoke exactly where it is; do not add or remove anything.'),
    'G': ('Photorealistic edit: a small, partly hidden fire with a few orange and yellow flame tongues and thin grey smoke is burning behind the shelf crates, '
          'low and partly covered by the crates. Keep everything else in the picture exactly as it is.'),
    'C': 'Photorealistic edit: keep the whole picture exactly as it is, with real camera texture. Do not add anything.',
    # Amendment 2 (descriptive extension, no claim): a larger fire and two non-fire look-alikes inside the same masks
    'G2': ('Photorealistic edit: a large fire with tall orange and yellow flames and dark smoke is burning behind the shelf crates and rising above them. '
           'Keep everything else in the picture exactly as it is.'),
    'K1': ('Photorealistic edit: an orange high-visibility safety vest lies folded behind the shelf crates, low and partly covered by the crates. '
           'Keep everything else in the picture exactly as it is.'),
    'K2': ('Photorealistic edit: an orange warning beacon lamp, switched on and glowing, stands behind the shelf crates, low and partly covered by the crates. '
           'Keep everything else in the picture exactly as it is.'),
}


def fire_colour_fraction(rgb: np.ndarray, region: np.ndarray) -> float:
    """Share of the region's pixels that look like flame (red dominant, bright, saturated); the quality check of G and R."""
    px = rgb[region].astype(np.int16)
    if not len(px):
        return 0.0
    r, g, b = px[:, 0], px[:, 1], px[:, 2]
    return float(((r > 180) & (r > g + 20) & (g > b) & (r - b > 90)).mean())


def dilate(mask: np.ndarray, px: int) -> np.ndarray:
    from scipy.ndimage import binary_dilation
    return binary_dilation(mask, iterations=px)


def composite(base: np.ndarray, edited: np.ndarray, region: np.ndarray) -> np.ndarray:
    """Edited pixels only inside `region`; every pixel outside is the base's own value."""
    out = base.copy()
    out[region] = edited[region]
    return out


def inventory(mode: str, split: str, views: list) -> list:
    rows = [json.loads(x) for x in (BASE / 'labels.jsonl').read_text(encoding='utf8').splitlines() if x.strip()]
    byw = {}
    for r in rows:
        byw.setdefault((r['world_id'], r['view']), r)
    items = []
    if mode == 'R':
        for r in rows:
            if r['split'] == split and r['view'] in views:
                items.append({'key': r['image'], 'src': r['image'], 'mask': None, 'world': r['world_id'], 'view': r['view'], 'fire': bool(r['truth_hazard_visible']), 'kind': r['world_kind']})
        return items
    twin_of = {r['world_id']: r['twin_of'] for r in rows if r['twin_of']}              # clean twin world -> fire world
    for tw, fw in sorted(twin_of.items()):
        for v in views:
            f, t = byw.get((fw, v)), byw.get((tw, v))
            if not f or not t or t['split'] != split or not f['truth_hazard_visible'] or not (BASE / 'fire_masks' / f"{fw}_{v}.png").is_file():
                continue
            items.append({'key': f'{mode}_{tw}_{v}', 'src': t['image'], 'mask': f'fire_masks/{fw}_{v}.png', 'world': tw, 'fire_world': fw, 'view': v, 'fire': mode in ('G', 'G2'), 'kind': 'twin'})
    return items


CHUNK = 12


def load_pipe(dtype: str, fast: bool = False):
    import torch
    from diffusers import QwenImage21Pipeline
    pipe = QwenImage21Pipeline.from_pretrained(MODEL, dtype=getattr(torch, dtype))
    if fast:
        QwenImage21Pipeline._execution_device = property(lambda self: torch.device('cuda'))    # no offload hooks: the models are moved by hand
        pipe.vae.to('cuda')
    else:
        pipe.enable_model_cpu_offload()
    return pipe, torch


def fire_pixels_of(render):
    """The design 'mask' files are renders of the fire alone, not binary masks: fire pixels are the magenta key colour (the rule of scripts/fire_mask_at_pose.py)."""
    a = np.asarray(render).astype(int)
    return (a[..., 0] > 150) & (a[..., 2] > 150) & (a[..., 1] < 100)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--mode', required=True, choices=['R', 'G', 'C', 'G2', 'K1', 'K2'])
    ap.add_argument('--split', default='test')
    ap.add_argument('--views', default='F,L,R')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--dtype', default='float16', choices=['float16', 'bfloat16', 'float32'])
    ap.add_argument('--tag', default='')
    ap.add_argument('--prompt-key', default=None, help='development pilots only: a key of PROMPTS other than the mode (e.g. R2, R3)')
    ap.add_argument('--fast', action='store_true', help='chunked two-phase run: text encoder and transformer take turns on the GPU (no per-image offload)')
    ap.add_argument('--only', default='', help='development pilots only: comma-separated substrings of the image keys')
    a = ap.parse_args(argv)
    from PIL import Image
    out_dir = OUT / (a.mode + a.tag)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = RES / f'qi_manifest_{a.mode}{a.tag}.jsonl'
    done = {json.loads(x)['key'] for x in manifest.read_text(encoding='utf8').splitlines() if x.strip()} if manifest.is_file() else set()
    inv = inventory(a.mode, a.split, a.views.split(','))
    seed_of = {x['key']: 20261022 + n for n, x in enumerate(inv, 1)}       # the seed belongs to the image (its place in the inventory), not to the order of this run
    todo = [x for x in inv if x['key'] not in done]
    if a.only:
        todo = [x for x in todo if any(k in x['key'] for k in a.only.split(','))]
    if a.limit:
        todo = todo[:a.limit]
    print(f'mode {a.mode}: {len(todo)} images to generate', flush=True)
    if not todo:
        return
    pipe, torch = load_pipe(a.dtype, a.fast)
    prompt = PROMPTS[a.prompt_key or a.mode]

    def one(x):
        base = Image.open(BASE / x['src']).convert('RGB')
        return base, base.resize((W, H), Image.LANCZOS).convert('RGBA'), torch.Generator('cpu').manual_seed(seed_of[x['key']])

    def stream():
        """Yields (x, base, res, latency_s).  Default: the pipeline's own CPU offload, image by image.  --fast: chunks of CHUNK images, the text encoder
        embeds the chunk (the embeddings of an edit cover the condition image, so they are made per image), then the transformer denoises it: no model moves per image."""
        if not a.fast:
            for x in todo:
                base, img, gen = one(x)
                t0 = time.perf_counter()
                res = pipe(prompt=prompt, image=img, width=W, height=H, use_kv_cache=True, generator=gen).images[0]
                yield x, base, res, round(time.perf_counter() - t0, 2)
            return
        orig = pipe.encode_prompt

        class Enough(Exception):
            pass
        for c in range(0, len(todo), CHUNK):
            chunk, cache = todo[c:c + CHUNK], []
            t0 = time.perf_counter()
            pipe.transformer.to('cpu')
            pipe.text_encoder.to('cuda')

            def record(*args, **kw):
                cache.append(tuple(t.cpu() if t is not None else None for t in orig(*args, **kw)))
                raise Enough
            pipe.encode_prompt = record
            for x in chunk:
                base, img, gen = one(x)
                try:
                    pipe(prompt=prompt, image=img, width=W, height=H, use_kv_cache=True, generator=gen)
                except Enough:
                    pass
            pipe.text_encoder.to('cpu')
            torch.cuda.empty_cache()
            pipe.transformer.to('cuda')
            t_enc = (time.perf_counter() - t0) / len(chunk)
            for x, emb in zip(chunk, cache):
                base, img, gen = one(x)
                pipe.encode_prompt = lambda *args, _e=emb, **kw: tuple(t.to('cuda') if t is not None else None for t in _e)
                t1 = time.perf_counter()
                res = pipe(prompt=prompt, image=img, width=W, height=H, use_kv_cache=True, generator=gen).images[0]
                yield x, base, res, round(t_enc + time.perf_counter() - t1, 2)
        pipe.encode_prompt = orig

    with manifest.open('a', encoding='utf8') as fh:
        for n, (x, base, res, lat) in enumerate(stream(), 1):
            base_np = np.asarray(base)
            edited = np.asarray(res.convert('RGB').resize(base.size, Image.LANCZOS))
            if x['mask']:
                m = fire_pixels_of(np.asarray(Image.open(BASE / x['mask']).convert('RGB')))
                region = dilate(m, DILATE_PX)
                final = composite(base_np, edited, region)
                qc = {'mask_px': int(m.sum()), 'region_px': int(region.sum()), 'fire_colour_in_mask': round(fire_colour_fraction(final, m), 4),
                      'fire_colour_in_mask_before': round(fire_colour_fraction(base_np, m), 4), 'outside_unchanged': bool((final[~region] == base_np[~region]).all())}
            else:
                final = edited
                qc = {'mean_abs_diff': round(float(np.abs(edited.astype(np.int16) - base_np.astype(np.int16)).mean()), 2)}
            Image.fromarray(final).save(out_dir / (x['key'].replace('/', '_').rsplit('.', 1)[0] + '.jpg'), quality=92)
            fh.write(json.dumps({**x, 'mode': a.mode, 'prompt': PROMPTS[a.prompt_key or a.mode], 'dtype': a.dtype, 'latency_s': lat, 'qc': qc, 'fast': a.fast, 'seed': seed_of[x['key']]}) + '\n')
            fh.flush()
            print(n, x['key'], lat, qc, flush=True)


if __name__ == '__main__':
    sys.exit(main())
