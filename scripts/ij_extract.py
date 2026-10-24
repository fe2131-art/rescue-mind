#!/usr/bin/env python3
"""Study IJ: hidden states and the zero-shot yes-probability of Qwen3.5-9B on the destination text set (GPU; run inside rm-next by scripts/ij_run.sh; resumable as a whole file).

  python3 scripts/ij_extract.py      # -> experiments/results/ij_features.npz  (H: texts x layers x d float16, layers, yes_prob, texts)
Text-only prompt (chat template of the model's processor): the request, then the question 'The only known delivery destination is shelter B. Does this request name a destination other than shelter B? Answer Yes or No.'
Features: the hidden state of the LAST prompt token at eight depths (fractions 0.25 ... 1.0 of the layers) and the yes/no probability of the next token (the zero-shot baseline).  Nothing is trained here.
"""
import json
import sys
import time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
OUT = ROOT / 'experiments/results/ij_features.npz'
QUESTION = 'The only known delivery destination is shelter B. Does this request name a destination other than shelter B? Answer Yes or No.'
FRACTIONS = (0.25, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)


def main():
    from jev_score import Judge, yes_no_prob
    rows = [json.loads(l) for l in (ROOT / 'experiments/intent_eval/ij_v1.jsonl').read_text(encoding='utf8').splitlines() if l.strip()]
    j = Judge('qwen35')
    torch = j.torch
    hs, yes = [], []
    layers = None
    t0 = time.time()
    for n, r in enumerate(rows, 1):
        msgs = [{'role': 'user', 'content': [{'type': 'text', 'text': f"Request: {r['text']}\n{QUESTION}"}]}]
        inp = j.proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True, return_dict=True, return_tensors='pt').to(j.model.device)
        with torch.no_grad():
            out = j.model(**inp, output_hidden_states=True)
        states = out.hidden_states
        if layers is None:
            L = len(states) - 1
            layers = sorted({max(1, round(L * f)) for f in FRACTIONS})
        hs.append(np.stack([states[k][0, -1].float().cpu().numpy() for k in layers]).astype(np.float16))
        lg = out.logits[0, -1].float()
        yes.append(yes_no_prob(torch.logsumexp(lg[j.yes], 0).item(), torch.logsumexp(lg[j.no], 0).item()))
        if n % 100 == 0:
            print(n, '/', len(rows), round(time.time() - t0), 's', flush=True)
    np.savez_compressed(OUT, H=np.stack(hs), layers=np.array(layers), yes_prob=np.array(yes), texts=np.array([r['text'] for r in rows]))
    print('IJ_EXTRACT_DONE', len(rows), 'texts, layers', layers, flush=True)


if __name__ == '__main__':
    main()
