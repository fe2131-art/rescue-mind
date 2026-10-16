#!/usr/bin/env python3
"""I-03: score the Japanese one-sentence explanations on dev v2 with keyword rules.

A sentence is correct when it names the true platform content (water bottles /
first-aid kit / nothing) without naming a supply that is not there, and mentions
fire/smoke exactly when a fire is in view.  Rules are deliberately simple and are
reported with every sentence so a human can re-check them.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rescuemind.local_vision import describe_station_local  # noqa: E402

WATER = re.compile(r'(水|ボトル|ペットボトル|飲料)')
MED = re.compile(r'(救急|医療|十字|赤十字|応急|医薬)')
EMPTY = re.compile(r'(何も(あり|置かれて|な)|何もない|空(っぽ|です|の台)|ありません。?$)')
FIRE = re.compile(r'(火|炎|煙|燃)')
NEG_FIRE = re.compile(r'(火|炎|煙)[^。]*?(見え|は)?(ません|ない|無い|ありません)')


def judge(text, truth_supply, fire):
    says_water, says_med = bool(WATER.search(text)), bool(MED.search(text))
    says_fire = bool(FIRE.search(text)) and not NEG_FIRE.search(text)
    if truth_supply == 'water':
        supply_ok = says_water and not says_med
    elif truth_supply == 'medicine':
        supply_ok = says_med and not says_water
    else:
        supply_ok = not says_water and not says_med and bool(EMPTY.search(text) or '段ボール' in text or '箱' in text)
    return {'supply_ok': supply_ok, 'fire_ok': says_fire == fire, 'ok': supply_ok and says_fire == fire}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', required=True)
    ap.add_argument('--devset', default=str(ROOT / 'experiments/vlm_devset_v2'))
    ap.add_argument('--model', default='Qwen/Qwen2.5-VL-3B-Instruct')
    a = ap.parse_args()
    dev = Path(a.devset)
    rows = [json.loads(x) for x in (dev / 'labels.jsonl').read_text().splitlines()]
    out = []
    for r in rows:
        t0 = time.perf_counter()
        text = describe_station_local(dev / r['image'], model=a.model)['text_ja']
        j = judge(text, r['truth_supply'], r.get('truth_hazard_visible', False))
        out.append({'image': r['image'], 'truth_supply': r['truth_supply'], 'fire': r.get('truth_hazard_visible', False),
                    'distractor': bool(r.get('distractor_at')), 'text_ja': text,
                    'latency_s': round(time.perf_counter() - t0, 2), **j})
    n = len(out)
    summ = {'tag': a.tag, 'n': n, 'correct': sum(o['ok'] for o in out),
            'supply_ok': sum(o['supply_ok'] for o in out), 'fire_ok': sum(o['fire_ok'] for o in out),
            'empty_ok': f"{sum(o['ok'] for o in out if o['truth_supply'] == 'other')}/{sum(o['truth_supply'] == 'other' for o in out)}",
            'mean_latency_s': round(sum(o['latency_s'] for o in out) / n, 2)}
    (ROOT / 'experiments/results' / f'explain_{a.tag}.json').write_text(
        json.dumps({'summary': summ, 'records': out}, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == '__main__':
    main()
