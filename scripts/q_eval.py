#!/usr/bin/env python3
"""Study Q (experiments/PREREGISTRATION_Q.md): the supply check on real photographs (Wikimedia Commons).

Order of operations (each step only reads what the previous ones wrote):
  python3 scripts/q_fetch.py --all                    # candidates + thumbnails -> experiments/q_sample.json
  python3 scripts/q_contact_sheet.py                  # contact sheets for the label audit -> experiments/q_exclusions.json (by hand, BEFORE inference)
  python3 scripts/q_eval.py --sample                  # exclusions + per-image requested supply -> experiments/q_sample_final.json
  # server: scripts/local_vlm_server.py --model Qwen/Qwen3.5-9B --prompt-set v35   (port 8765)
  ~/.cache/rescuemind/pqvenv/bin/python scripts/q_eval.py --run       # two option-permuted questions per image (resumable)
  python3 scripts/q_eval.py --zeroshot                # SigLIP + CLIP, prompts and thresholds frozen by study Z (GPU, after the server is stopped)
  python3 scripts/q_analysis.py                       # -> experiments/results/q_summary.json

The hazard question is NOT evaluated here (studies P and P2 cover it).  Images stay in ~/.cache/rescuemind/q/images.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
EXP = ROOT / 'experiments'
RES = EXP / 'results'
CANDIDATES = EXP / 'q_sample.json'
EXCLUSIONS = EXP / 'q_exclusions.json'
FINAL = EXP / 'q_sample_final.json'
OUT_VLM = RES / 'q_scores_qwen9b_v35.jsonl'
OUT_ZS = {'siglip': RES / 'q_scores_siglip.json', 'clip': RES / 'q_scores_clip.json'}
IMAGES = Path.home() / '.cache/rescuemind/q/images'
SEED = 'Q-2026'
TARGET_PER_CLASS = 150
MAX_PER_ARTIST = 8            # per (class, artist): near-duplicate series do not dominate a class
PROMPT_SET = 'v35'
MODEL = 'Qwen/Qwen3.5-9B'
SUPPLIES = ('water', 'medicine')
OTHER = {'water': 'medicine', 'medicine': 'water'}


# ------------------------------------------------------------------ sampling and labels (pure, no model, no GPU)
def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_exclusions(path: Path = EXCLUSIONS) -> dict:
    """{image id: reason}.  The list is written by hand from the contact sheets before any inference."""
    if not path.is_file():
        return {}
    return {int(e['id']): e['reason'] for e in json.loads(path.read_text()).get('excluded', [])}


def final_sample(candidates: list, excluded: dict, target: int = TARGET_PER_CLASS, seed: str = SEED,
                 max_per_artist: int = MAX_PER_ARTIST) -> list:
    """Deterministic: drop excluded ids, cap images per (class, artist), then draw `target` per class (seed Q-2026)."""
    out = []
    for cls in ('water', 'medicine', 'neither'):
        pool = sorted((r for r in candidates if r['class'] == cls and r['id'] not in excluded), key=lambda r: r['id'])
        rng = random.Random(f'{seed}|artist|{cls}')
        order = list(pool)
        rng.shuffle(order)
        per, kept = {}, []
        for r in order:
            a = r.get('artist') or r['id']
            per[a] = per.get(a, 0) + 1
            if per[a] <= max_per_artist:
                kept.append(r)
        kept.sort(key=lambda r: r['id'])
        if len(kept) > target:
            kept = sorted(random.Random(f'{seed}|final|{cls}').sample(kept, target), key=lambda r: r['id'])
        out += kept
    return out


def assign_requests(images: list, seed: str = SEED) -> list:
    """Requested supply per image.  water / medicine images: exactly half request their own supply (must approve), the
    other half the other supply (must refuse).  neither images: half request water, half medicine (always must refuse)."""
    res = {}
    for cls in ('water', 'medicine', 'neither'):
        ids = sorted(r['id'] for r in images if r['class'] == cls)
        random.Random(f'{seed}|req|{cls}').shuffle(ids)
        half = math.ceil(len(ids) / 2)
        for k, i in enumerate(ids):
            if cls == 'neither':
                res[i] = 'water' if k < half else 'medicine'
            else:
                res[i] = cls if k < half else OTHER[cls]
    out = []
    for r in images:
        req = res[r['id']]
        out.append({**r, 'requested': req, 'expected': 'allow' if req == r['class'] else 'deny',
                    'refusal_kind': None if req == r['class'] else ('wrong_supply' if r['class'] in SUPPLIES else 'neither:' + r['type'])})
    return out


def do_sample():
    cand = json.loads(CANDIDATES.read_text())
    if any('sha256' not in r for r in cand['images']):
        sys.exit('candidates are not downloaded yet: run scripts/q_fetch.py --download')
    if not EXCLUSIONS.is_file():
        sys.exit('experiments/q_exclusions.json is missing: do the label audit (scripts/q_contact_sheet.py) before sampling')
    excl = load_exclusions()
    imgs = assign_requests(final_sample(cand['images'], excl))
    FINAL.write_text(json.dumps({
        'study': 'Q', 'seed': SEED, 'target_per_class': TARGET_PER_CLASS, 'max_per_artist': MAX_PER_ARTIST,
        'candidates_sha256': hashlib.sha256(CANDIDATES.read_bytes()).hexdigest(),
        'exclusions_sha256': hashlib.sha256(EXCLUSIONS.read_bytes()).hexdigest(), 'n_excluded': len(excl),
        'n': len(imgs), 'counts': {c: sum(r['class'] == c for r in imgs) for c in ('water', 'medicine', 'neither')},
        'images': imgs}, indent=1, ensure_ascii=False) + '\n')
    print('final sample', len(imgs), {c: sum(r['class'] == c for r in imgs) for c in ('water', 'medicine', 'neither')},
          'must-approve', sum(r['expected'] == 'allow' for r in imgs), 'must-refuse', sum(r['expected'] == 'deny' for r in imgs))


# ------------------------------------------------------------------ Qwen3.5-9B through the local server (as p_realphoto_eval.py)
def do_run(port: int):
    from rescuemind.local_vision import _client_call, LocalInferenceError
    done = {json.loads(x)['id'] for x in OUT_VLM.read_text().splitlines()} if OUT_VLM.is_file() else set()
    todo = [r for r in json.loads(FINAL.read_text())['images'] if r['id'] not in done]
    url = f'http://127.0.0.1:{port}/v1/classify'
    for n, r in enumerate(todo):
        blob = (IMAGES / r['file']).read_bytes()
        if hashlib.sha256(blob).hexdigest() != r['sha256']:
            sys.exit(f'image {r["id"]} does not match the recorded sha256')
        rec = {k: r[k] for k in ('id', 'class', 'type', 'requested', 'expected', 'refusal_kind')}
        rec['passes'] = {}
        for pass_id in (1, 2):
            try:
                resp = _client_call(url, MODEL, blob, pass_id, timeout=180)
            except (LocalInferenceError, OSError, ValueError) as exc:
                rec['passes'][str(pass_id)] = {'error': str(exc)[:200]}
                continue
            sc = resp.get('scores') or {}
            if sc.get('prompt_set') != PROMPT_SET:
                sys.exit(f'server is not configured with --prompt-set {PROMPT_SET}: {sc.get("prompt_set")}')
            rec['passes'][str(pass_id)] = {'supply': resp['result']['supply'], 'scores': sc}
        with OUT_VLM.open('a') as f:
            f.write(json.dumps(rec) + '\n')
        if (n + 1) % 50 == 0:
            print('scored', n + 1, '/', len(todo), flush=True)
    print('scored', len(todo))


# ------------------------------------------------------------------ SigLIP / CLIP, exactly the study-Z prompts and models
def do_zeroshot():
    import zeroshot_baseline as zb      # prompts, models and the crop code are study Z's; thresholds are read from z_thresholds.json
    imgs = json.loads(FINAL.read_text())['images']
    items = [('q', str(IMAGES), {'image': r['file'], 'id': r['id']}) for r in imgs]
    for name in zb.MODELS:
        if OUT_ZS[name].is_file():
            continue
        sc = zb.score_model(name, items)
        OUT_ZS[name].write_text(json.dumps({'model': zb.MODELS[name], 'supply_prompts': zb.SUPPLY_PROMPTS,
                                            'scores': {k.split('|', 1)[1].removesuffix('.jpg'): v['supply_probs'] for k, v in sc.items()}}) + '\n')
        print('saved', OUT_ZS[name])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--sample', action='store_true'); ap.add_argument('--run', action='store_true')
    ap.add_argument('--zeroshot', action='store_true'); ap.add_argument('--port', type=int, default=8765)
    a = ap.parse_args()
    if a.sample:
        do_sample()
    if a.run:
        do_run(a.port)
    if a.zeroshot:
        do_zeroshot()


if __name__ == '__main__':
    main()
