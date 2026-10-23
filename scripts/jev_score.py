#!/usr/bin/env python3
"""Jev (I-73, docs/JEV_DESIGN.md): score saved images with a heterogeneous judge VLM under the frozen hazard question h36 (full image + three enlarged crops, max) by the next-token Yes/No rule of the gate.

  HF_HUB_OFFLINE=1 python3 scripts/jev_score.py --judge internvl3 --set closed_loop     # -> experiments/results/jev_scores_<judge>_<set>.jsonl (resumable, one row per image)
  ... --set xd                                                                            # the 1932 depot images of XD
  ... --limit 5                                                                           # smoke test

Judges (all local, transformers-native, no remote code): qwen35 (the gate's own model, for a re-check), internvl3 (OpenGVLab/InternVL3-8B-hf: Qwen2.5 LM + InternViT), idefics3 (HuggingFaceM4/Idefics3-8B-Llama3: Llama 3.1 + SigLIP),
qwen3vl (Qwen3-VL-8B), smolvlm2 (SmolVLM2-2.2B).  Score = softmax over logsumexp of the Yes-token variants and of the No-token variants of the first answer token.  Scores are thresholded, not calibrated probabilities (as in the gate).
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
RES = ROOT / 'experiments/results'
JUDGES = {'qwen35': 'Qwen/Qwen3.5-9B', 'internvl3': 'OpenGVLab/InternVL3-8B-hf', 'idefics3': 'HuggingFaceM4/Idefics3-8B-Llama3',
          'qwen3vl': 'Qwen/Qwen3-VL-8B-Instruct', 'smolvlm2': 'HuggingFaceTB/SmolVLM2-2.2B-Instruct'}
H36 = ('Look at the whole image, especially the edges and the area behind and above the objects. '
       'Is there any fire, flame, or smoke (a grey or black cloud), even if it is small, partly hidden '
       'behind something, or cut off at the edge of the image? Answer Yes or No.')


def crops(pic):
    """The three enlarged overlapping crops of the gate (left 60%, right 60%, top 60%), long side 640 px."""
    w, h = pic.size
    out = []
    for box in ((0, 0, int(.6 * w), h), (int(.4 * w), 0, w, h), (0, 0, w, int(.6 * h))):
        c = pic.crop(box)
        s = 640 / max(c.size)
        out.append(c.resize((max(1, round(c.size[0] * s)), max(1, round(c.size[1] * s)))))
    return out


def yes_no_prob(logit_yes: float, logit_no: float) -> float:
    import math
    m = max(logit_yes, logit_no)
    return math.exp(logit_yes - m) / (math.exp(logit_yes - m) + math.exp(logit_no - m))


class Judge:
    def __init__(self, name: str):
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor
        self.torch = torch
        rid = JUDGES[name]
        local = Path('/hf/jev_models') / rid.split('/')[-1]      # downloaded with curl (the container's HTTP decoder cannot fetch them)
        if local.is_dir():
            rid = str(local)
        self.proc = AutoProcessor.from_pretrained(rid)
        self.model = AutoModelForImageTextToText.from_pretrained(rid, dtype=torch.float16, device_map='cuda').eval()
        tok = self.proc.tokenizer
        def ids(words):
            out = set()
            for w in words:
                t = tok.encode(w, add_special_tokens=False)
                if len(t) >= 1:
                    out.add(t[0])
            return sorted(out)
        self.yes = ids(['Yes', 'yes', ' Yes', ' yes', 'YES'])
        self.no = ids(['No', 'no', ' No', ' no', 'NO'])

    def p_yes(self, pic, question: str = H36) -> float:
        torch = self.torch
        msgs = [{'role': 'user', 'content': [{'type': 'image', 'image': pic}, {'type': 'text', 'text': question}]}]
        inp = self.proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True, return_dict=True, return_tensors='pt').to(self.model.device)
        with torch.no_grad():
            lg = self.model(**inp).logits[0, -1].float()
        return yes_no_prob(torch.logsumexp(lg[self.yes], 0).item(), torch.logsumexp(lg[self.no], 0).item())

    def hazard(self, pic) -> dict:
        views = [round(self.p_yes(v), 4) for v in [pic] + crops(pic)]
        return {'max': max(views), 'views': views}


def inventory(which: str) -> list:
    from PIL import Image  # noqa: F401
    if which == 'closed_loop':
        from scripts.gv_dev_prompts import inventory as inv, VIEWS, RUNS
        rows = list(inv())
        trials = {t['id']: t for t in json.loads((ROOT / 'experiments/campaign_gvd_protocol.json').read_text(encoding='utf8'))['trials']}
        for gvd in (RES / 'campaign_GVD_ledger.jsonl', RES / 'campaign_GVD_rerun_ledger.jsonl'):      # development pass GVD (0.8 m views of GD's fire worlds); the rerun ledger holds the 2 trials that failed on the guard
            for line in (gvd.read_text(encoding='utf8').splitlines() if gvd.is_file() else []):
                r = json.loads(line)
                t = trials.get(r['trial_id'])
                if t and r.get('final', True) and r.get('run_id') and r.get('observed_action') != 'FAILED':
                    for v, fn in VIEWS.items():
                        f = RUNS / r['run_id'] / fn
                        if f.is_file():
                            rows.append({'study': 'GVD', 'trial_id': r['trial_id'], 'run_id': r['run_id'], 'world': t['gd_world'], 'arm': 'open', 'item': t['expected'], 'fire': True,
                                         'view': v, 'offset_m': 0.8, 'file': str(f)})
        return [{**x, 'set': 'closed_loop', 'key': f"{x['run_id']}:{x['view']}"} for x in rows]
    if which.startswith('qi_'):                                   # study QI: the generated devsets (outputs/qi/devset_<R|G|C>), XD-format labels
        base = ROOT / 'outputs/qi' / f'devset_{which[3:]}'
        rows = [json.loads(x) for x in (base / 'labels.jsonl').read_text(encoding='utf8').splitlines() if x.strip()]
        return [{'set': which, 'key': r['image'], 'file': str(base / r['image']), 'world': r['world_id'], 'view': r['view'], 'world_kind': r['world_kind'],
                 'fire': bool(r.get('truth_hazard_visible')), 'perceivable_any': bool(r.get('world_perceivable_any_view'))} for r in rows]
    if which in ('xd', 'ji'):                                    # XD's depot images, or study JI's fresh set (same format)
        base = ROOT / f'experiments/vlm_testset_{which}'
        rows = [json.loads(x) for x in (base / 'labels.jsonl').read_text(encoding='utf8').splitlines() if x.strip()]
        return [{'set': which, 'key': r['image'], 'file': str(base / r['image']), 'world': r['world_id'], 'view': r['view'], 'world_kind': r['world_kind'],
                 'fire': bool(r.get('truth_hazard_visible')), 'perceivable_any': bool(r.get('world_perceivable_any_view'))} for r in rows]
    raise SystemExit('unknown set')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--judge', required=True, choices=list(JUDGES))
    ap.add_argument('--set', required=True, choices=['closed_loop', 'xd', 'ji', 'qi_R', 'qi_G', 'qi_C'])
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args(argv)
    out = RES / f'jev_scores_{a.judge}_{a.set}.jsonl'
    done = {json.loads(x)['key'] for x in out.read_text(encoding='utf8').splitlines() if x.strip()} if out.is_file() else set()
    todo = [x for x in inventory(a.set) if x['key'] not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f'{a.judge} {a.set}: {len(todo)} images to score', flush=True)
    if not todo:
        return
    from PIL import Image
    j = Judge(a.judge)
    print('yes ids', j.yes, 'no ids', j.no, flush=True)
    failures = 0
    with out.open('a', encoding='utf8') as fh:
        for n, x in enumerate(todo, 1):
            try:
                pic = Image.open(x['file']).convert('RGB')
                t0 = time.perf_counter()
                score = j.hazard(pic)
                score['latency_s'] = round(time.perf_counter() - t0, 3)      # I-77: Jev's value is speed; the four passes (full image + three crops) per image, GPU shared with nothing else in a JH step
            except Exception as e:                                # a broken image or a chat-template problem must not drop the judge silently: count and stop after 5 in a row
                failures += 1
                print('ERROR', x['key'], repr(e)[:200], flush=True)
                if failures >= 5:
                    raise SystemExit(f'{a.judge}: 5 scoring errors, stopping (fix the judge, rerun resumes)')
                continue
            failures = 0
            fh.write(json.dumps({**{k: v for k, v in x.items() if k != 'file'}, 'judge': a.judge, 'score': score}) + '\n')
            fh.flush()
            if n % 100 == 0:
                print(n, '/', len(todo), flush=True)


if __name__ == '__main__':
    main()
