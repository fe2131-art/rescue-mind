#!/usr/bin/env python3
"""I-06: build the v3.4 closed-loop protocol (42 trials) BEFORE running it.

R001-R030 keep the v2.3 IDs/order/scenes (comparable with campaign C) but the expected
behaviour follows v3.4 (recovery search): swapped -> deliver after searching the other
station; empty -> refuse after checking both.  R031-R042 add fire (stop without search),
dim evening light (deliver) and a cardboard box on an empty platform (refuse).
Instructions come from a phrasing pool disjoint from the I-04 held-out set.
"""
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POOL = {
    'water': ['避難所Bに飲料水をお願いします', '避難所Bで飲み水が足りないそうです', 'Bの避難所にペットボトルの水を運んで',
              '避難所Bの人たちが喉の渇きを訴えている', 'Please take some water to shelter B'],
    'medicine': ['避難所Bに医療物資を届けてください', '避難所Bでけが人の手当てに使う物が必要', 'Bの避難所に救急箱をお願い',
                 '避難所Bに包帯や消毒薬を運んでほしい', 'Shelter B needs first aid supplies'],
}


def main():
    held = {json.loads(x)['text'] for x in (ROOT / 'experiments/intent_eval/held_out_v34.jsonl').read_text().splitlines()}
    assert not held & set(POOL['water'] + POOL['medicine']), 'phrasing pool overlaps the I-04 held-out set'
    old = json.loads((ROOT / 'experiments/v23_locked_protocol.json').read_text())
    trials = []
    for t in sorted(old['trials'], key=lambda t: t['order']):
        exp = {'nominal': 'ALLOW', 'swapped': 'DELIVER_AFTER_SEARCH', 'empty': 'DENY'}[t['scene']]
        trials.append({'id': t['id'], 'order': t['order'], 'scene': t['scene'], 'expected': t['expected'],
                       'repeat': t['repeat'], 'instruction': POOL[t['expected']][(t['repeat'] - 1) % 5],
                       'lighting': 'default', 'hazard_at': None, 'distractor_at': None, 'expected_action': exp})
    extra = []
    for item in ('water', 'medicine'):
        for r in range(3):
            extra.append(dict(scene='nominal', expected=item, repeat=r + 1, lighting='default', hazard_at=item,
                              distractor_at=None, expected_action='DENY_HAZARD'))
        for r in range(2):
            extra.append(dict(scene='nominal', expected=item, repeat=r + 1, lighting='dim_evening', hazard_at=None,
                              distractor_at=None, expected_action='ALLOW'))
        extra.append(dict(scene='empty', expected=item, repeat=1, lighting='default', hazard_at=None,
                          distractor_at=item, expected_action='DENY'))
    random.Random(20261017).shuffle(extra)
    for k, t in enumerate(extra):
        t.update(id=f'R{31 + k:03d}', order=31 + k, instruction=POOL[t['expected']][(t['repeat'] + 1) % 5])
        trials.append(t)
    out = {'schema': 'rescuemind_v34_protocol', 'planned_n': len(trials), 'derived_from': 'v23_locked_protocol.json',
           'trials': trials}
    (ROOT / 'experiments/v34_protocol.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n')
    from collections import Counter
    print(len(trials), Counter(t['expected_action'] for t in trials))


if __name__ == '__main__':
    main()
