#!/usr/bin/env python3
"""Study IJ: the closed-set destination probabilities of the SUBMITTED parser (intent prompt i35, dest_probs {B, other, unstated}) on the IJ text set; the baseline 'P(other)'.

  python3 scripts/ij_closedset.py      # needs local_vlm_server on 8765 started with the v3.6 flags (ij_run.sh) -> experiments/results/ij_closed_set.jsonl (resumable)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / 'experiments/results/ij_closed_set.jsonl'


def main():
    from rescuemind.intent_llm import query
    rows = [json.loads(l) for l in (ROOT / 'experiments/intent_eval/ij_v1.jsonl').read_text(encoding='utf8').splitlines() if l.strip()]
    done = {json.loads(l)['text'] for l in OUT.read_text(encoding='utf8').splitlines() if l.strip()} if OUT.is_file() else set()
    with OUT.open('a', encoding='utf8') as f:
        for r in rows:
            if r['text'] in done:
                continue
            d = query(r['text'], model='Qwen/Qwen3.5-9B')['dest_probs']
            f.write(json.dumps({'text': r['text'], 'p_other': d['other'], 'p_B': d['B'], 'p_unstated': d['unstated']}, ensure_ascii=False) + '\n')
            f.flush()
    print('IJ_CLOSEDSET_DONE')


if __name__ == '__main__':
    main()
