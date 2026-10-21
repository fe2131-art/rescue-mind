#!/usr/bin/env python3
"""Development scoring (post hoc; I-61): does a hazard question that excludes the medicine crate's red cross lower the clean-world tail without lowering the fire scores?

Scores the saved closed-loop images of the depot (front check and the two look-around views of every run of GVK (0.8 m, clean), GDK (0.4 m, clean), GD (0.4 m, fire and fire-free worlds)) with the frozen
Qwen3.5-9B, h36 crops ('tiles'), under the frozen question `h36` (sanity subset: must reproduce the stored scores) and two candidate questions that add one sentence about red crosses and labels.
Development data only; any question taken from here is registered and tested on fresh worlds (a later study), never judged on these images.  Resumable (JSONL).

  HF_HUB_OFFLINE=1 python3 scripts/gv_dev_prompts.py            # GPU; -> experiments/results/gv_dev_prompts.jsonl
"""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
RES = ROOT / 'experiments/results'
OUT = RES / 'gv_dev_prompts.jsonl'
RUNS = ROOT / 'outputs/runs'
H36 = ('Look at the whole image, especially the edges and the area behind and above the objects. '
       'Is there any fire, flame, or smoke (a grey or black cloud), even if it is small, partly hidden '
       'behind something, or cut off at the edge of the image? Answer Yes or No.')
H37A = ('Look at the whole image, especially the edges and the area behind and above the objects. '
        'Is there any fire, flame, or smoke (a grey or black cloud), even if it is small, partly hidden '
        'behind something, or cut off at the edge of the image? Do not count red crosses, labels, signs or red paint on boxes: only real flames, burning material or smoke. Answer Yes or No.')
H37B = ('Look at the whole image, especially the edges and the area behind and above the objects. '
        'Is there any real flame, burning material, or smoke (a grey or black cloud), even if it is small, partly hidden '
        'behind something, or cut off at the edge of the image? A red cross on a white label is a medical marking, not fire. Answer Yes or No.')
PROMPTS = {'h36': H36, 'h37a': H37A, 'h37b': H37B}
VIEWS = {'F': 'checkpoint.jpg', 'L': 'peek_L_checkpoint.jpg', 'R': 'peek_R_checkpoint.jpg'}


def inventory() -> list:
    """Every saved view of the runs of GVK, GDK and GD with what is known about it (world kind, item, arm, offset)."""
    out = []
    for study, ledger, proto, off in (('GVK', 'campaign_GVK_ledger.jsonl', 'campaign_gvk_protocol.json', 0.8), ('GDK', 'campaign_GDK_ledger.jsonl', 'campaign_gdk_protocol.json', 0.4),
                                      ('GD', 'campaign_GD_ledger.jsonl', 'campaign_gd_protocol.json', 0.4)):
        trials = {t['id']: t for t in json.loads((ROOT / 'experiments' / proto).read_text(encoding='utf8'))['trials']}
        for line in (RES / ledger).read_text(encoding='utf8').splitlines():
            r = json.loads(line)
            t = trials.get(r['trial_id'])
            if not t or not r.get('final', True) or not r.get('run_id'):
                continue
            for v, fn in VIEWS.items():
                f = RUNS / r['run_id'] / fn
                if f.is_file():
                    out.append({'study': study, 'trial_id': r['trial_id'], 'run_id': r['run_id'], 'world': t['world'], 'arm': t['config'], 'item': t['expected'], 'fire': t['condition'] == 'fire_hidden',
                                'view': v, 'offset_m': off, 'file': str(f)})
    return out


def main():
    inv = inventory()
    done = set()
    if OUT.is_file():
        for line in OUT.read_text(encoding='utf8').splitlines():
            r = json.loads(line)
            done.add((r['run_id'], r['view']))
    todo = [x for x in inv if (x['run_id'], x['view']) not in done]
    print(f'{len(inv)} views, {len(todo)} to score', flush=True)
    if not todo:
        return
    from local_vlm_server import ModelWorker
    w = ModelWorker('Qwen/Qwen3.5-9B', prompt_set='v35')
    w.hazard_views = 'tiles'
    ModelWorker.HAZARD_PROMPTS.update({k: v for k, v in PROMPTS.items() if k != 'h36'})
    with OUT.open('a', encoding='utf8') as fh:
        for n, x in enumerate(todo, 1):
            blob = Path(x['file']).read_bytes()
            pic = w._picture(blob)
            digest = hashlib.sha256(blob).hexdigest()
            sc = {}
            for name in PROMPTS:
                w.hazard_prompt = name
                p, views, _ = w._hazard(pic, digest, '')
                sc[name] = {'max': p, 'crops': views}
            fh.write(json.dumps({**{k: v for k, v in x.items() if k != 'file'}, 'scores': sc}) + '\n')
            fh.flush()
            if n % 50 == 0:
                print(n, '/', len(todo), flush=True)


if __name__ == '__main__':
    main()
