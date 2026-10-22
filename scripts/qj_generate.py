#!/usr/bin/env python3
"""Study QJ (I-90; experiments/PREREGISTRATION_QJ.md): text-to-image NEW warehouse scenes, no simulator frame as input, for the frozen gate.

  python3 scripts/qj_generate.py --mode N0|NF|NB [--limit N] [--tag _pilot] [--fast]     (run inside rm-next, see scripts/qj_run.sh)
N0 clean scene, NF small partly hidden fire behind the crates (the hard class of the paper), NB large fire (positive control).  6 scene templates (2 supplies x 3 lighting) x 20 seeds = 120 images per mode;
the seed of an image is 20261200 + its index in the inventory (the same seed in the three modes, so the scenes of N0, NF and NB are paired by seed and template).
Same model, precision and steps as study QI (Qwen-Image-2.1-Turbo, fp16, 8 steps, 1024 x 768).  Pixel check, from pixels only: share of flame-coloured pixels in the whole image (`flame_share`).
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from qi_generate import MODEL, W, H, load_pipe, fire_colour_fraction  # noqa: E402,F401

OUT = ROOT / 'outputs/qj'
RES = ROOT / 'experiments/results'
SEED0 = 20261200
OBJ = {'water': 'a shrink-wrapped pack of six clear plastic water bottles with blue caps',
       'medicine': 'a white first-aid supply box with a red cross'}
LIGHT = ['Bright even overhead warehouse lighting.', 'Dim warehouse lighting with a window glowing at the side.', 'Warm late-afternoon light falling through a high window.']
BASE = ("A photograph taken by a small ground robot's low camera inside a real warehouse. In the foreground, on a cardboard pallet, stands {obj}. "
        "Behind it are steel storage shelves with cardboard boxes. {light} Realistic camera noise and slight depth of field.")
FIRE = {'N0': '',
        'NF': ' A small, low fire with a few orange flame tongues and thin grey smoke is burning behind the crates, partly hidden by them.',
        'NB': ' A large fire with tall orange flames and thick dark smoke is burning behind the crates and rising above them.'}
TEMPLATES = [(item, li) for item in ('water', 'medicine') for li in range(3)]
PER_TEMPLATE = 20


def prompt_of(mode: str, item: str, li: int) -> str:
    return BASE.format(obj=OBJ[item], light=LIGHT[li]) + FIRE[mode]


def inventory(mode: str) -> list:
    items = []
    for n in range(len(TEMPLATES) * PER_TEMPLATE):
        item, li = TEMPLATES[n % len(TEMPLATES)]
        items.append({'key': f'{mode}_{n + 1:03d}', 'world': f'qj{n + 1:03d}', 'item': item, 'light': li, 'seed': SEED0 + n + 1, 'prompt': prompt_of(mode, item, li)})
    return items


def flame_share(rgb: np.ndarray) -> float:
    """Share of the whole frame that is flame-coloured (the colour rule of scripts/qi_generate.fire_colour_fraction over the full image)."""
    return fire_colour_fraction(rgb, np.ones(rgb.shape[:2], dtype=bool))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--mode', required=True, choices=sorted(FIRE))
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--dtype', default='float16', choices=['float16', 'bfloat16', 'float32'])
    ap.add_argument('--tag', default='')
    ap.add_argument('--fast', action='store_true')
    ap.add_argument('--seed-offset', type=int, default=0, help='development pilots only: shifts every seed (pilot images are never part of the study)')
    a = ap.parse_args(argv)
    out_dir = OUT / (a.mode + a.tag)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = RES / f'qj_manifest_{a.mode}{a.tag}.jsonl'
    done = {json.loads(x)['key'] for x in manifest.read_text(encoding='utf8').splitlines() if x.strip()} if manifest.is_file() else set()
    todo = [x for x in inventory(a.mode) if x['key'] not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f'mode {a.mode}: {len(todo)} images to generate', flush=True)
    if not todo:
        return
    pipe, torch = load_pipe(a.dtype, a.fast)
    emb: dict = {}
    if a.fast:                                                       # text encoder once per distinct prompt, then the transformer stays resident
        orig = pipe.encode_prompt

        class Enough(Exception):
            pass
        pipe.transformer.to('cpu')
        pipe.text_encoder.to('cuda')
        for x in todo:
            if x['prompt'] in emb:
                continue
            cache = []

            def record(*args, **kw):
                cache.append(tuple(t.cpu() if t is not None else None for t in orig(*args, **kw)))
                raise Enough
            pipe.encode_prompt = record
            try:
                pipe(prompt=x['prompt'], width=W, height=H, generator=torch.Generator('cpu').manual_seed(1))
            except Enough:
                pass
            emb[x['prompt']] = cache[0]
        pipe.text_encoder.to('cpu')
        torch.cuda.empty_cache()
        pipe.transformer.to('cuda')
        pipe.encode_prompt = orig
    from PIL import Image
    with manifest.open('a', encoding='utf8') as fh:
        for x in todo:
            gen = torch.Generator('cpu').manual_seed(x['seed'] + a.seed_offset)
            t0 = time.perf_counter()
            if a.fast:
                e = emb[x['prompt']]
                pipe.encode_prompt = lambda *args, _e=e, **kw: tuple(t.to('cuda') if t is not None else None for t in _e)
            res = pipe(prompt=x['prompt'], width=W, height=H, generator=gen).images[0]
            lat = round(time.perf_counter() - t0, 2)
            rgb = np.asarray(res.convert('RGB').resize((640, 480), Image.LANCZOS))            # the size of the XD frames
            Image.fromarray(rgb).save(out_dir / f"{x['key']}.jpg", quality=92)
            fh.write(json.dumps({**x, 'mode': a.mode, 'dtype': a.dtype, 'latency_s': lat, 'fast': a.fast, 'seed_offset': a.seed_offset, 'flame_share': round(flame_share(rgb), 5)}) + '\n')
            fh.flush()
            print(x['key'], lat, flush=True)


if __name__ == '__main__':
    sys.exit(main())
