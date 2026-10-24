#!/usr/bin/env python3
"""Study IJ (experiments/PREREGISTRATION_IJ.md): a text set for an answerability probe on destination names, written BEFORE any hidden state or score of these texts exists.

  python3 scripts/make_intent_ij_set.py      # -> experiments/intent_eval/ij_v1.jsonl

Label 'unknown' = the request names a destination other than shelter B (a place the mission does not know); 'known' = it names shelter B (spelling variants); 'none' = it names no destination (a legitimate request).
Unknown destinations come in 10 NAME FAMILIES (civic buildings, schools, medical, numbered or oriented other shelters, commerce, public places, homes, care and childcare, rural and work places, religious and community
places); 5 families are DEV (the probe's layer, regularisation and threshold are chosen on them only), 5 are TEST (held out whole).  Each name is used in 4 requests (2 supplies x 2 frames) in Japanese, English names in
English.  Not written to fit any earlier text set; the names of the earlier sets (IG, IH) overlap with these families on purpose (the families, not the texts, are what the probe must generalise over); no text is shared (checked by a test).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JA_FRAMES = {'water': ['{d}へ飲み水を運んでほしい', '{d}にお水を届けて', '{d}へ給水をお願いします', '{d}で水が足りません、届けてください'],
             'medicine': ['{d}へ救急セットを持ってきてほしい', '{d}へ医薬品を運んでください', '{d}にけが用の道具をお願い', '{d}で怪我人が出ました、救急箱を']}
EN_FRAMES = {'water': ['Could you get some water over to {d}?', '{d} needs drinking water.', 'Water for {d}, quickly.', 'Please send water to {d}.'],
             'medicine': ['{d} needs a first-aid kit.', 'Could you bring medical supplies to {d}?', 'First aid to {d}, please.', 'Please send medicine to {d}.']}
NONE_JA = {'water': ['飲み水を運んでほしい', 'お水を届けて', '給水をお願いします', '水が足りません、届けてください'], 'medicine': ['救急セットを持ってきてほしい', '医薬品を運んでください', 'けが用の道具をお願い', '怪我人が出ました、救急箱を']}
NONE_EN = {'water': ['Could you get some water over?', 'We need drinking water.', 'Water, quickly.', 'Please send water.'], 'medicine': ['We need a first-aid kit.', 'Could you bring medical supplies?', 'First aid, please.', 'Please send medicine.']}
KNOWN_JA = ['避難所B', 'Bの避難所', 'B避難所', '避難所Ｂ', '避難所ビー', 'シェルターB', 'Bシェルター', 'ひなんじょB']
KNOWN_EN = ['shelter B', 'Shelter B', 'B shelter', 'the B shelter']
FAMILIES = {   # name -> (split, japanese names, english names)
    'civic': ('dev', ['公民館', '市役所', '区役所', '町役場', '消防署', '警察署'], ['city hall', 'the community center', 'the town office']),
    'school': ('dev', ['小学校', '中学校', '高校', '大学', '体育館', '校庭'], ['the school', 'the gymnasium', 'the university']),
    'medical': ('dev', ['病院', '診療所', 'クリニック', '医院', '救護所'], ['the hospital', 'the clinic']),
    'commerce': ('dev', ['スーパー', 'コンビニ', 'ショッピングモール', '商店街', 'ホームセンター'], ['the supermarket', 'the shopping mall']),
    'home': ('dev', ['自宅', '実家', 'お宅', '私の家', '祖母の家'], ['my house', 'my parents\' home']),
    'other_shelter': ('test', ['避難所A', '避難所C', '避難所1', '避難所2', '第二避難所', '二番目の避難所', '北側の避難所', '東の避難所', 'もう一つの避難所'], ['shelter A', 'the second shelter', 'the north shelter']),
    'public': ('test', ['図書館', '駅', '公園', '競技場', 'バス停', '駐車場', '空港'], ['the library', 'the station', 'the stadium']),
    'care': ('test', ['老人ホーム', '福祉施設', '保育園', '幼稚園', '介護施設'], ['the nursing home', 'the kindergarten']),
    'rural': ('test', ['山小屋', '漁協', '農協', '工場', '港', '川向こうの集落'], ['the barn', 'the harbor']),
    'community': ('test', ['神社', '寺', '教会', '公会堂', '集会所', 'テント村'], ['the temple', 'the church']),
}


def rows():
    out = []
    for fam, (split, ja, en) in FAMILIES.items():
        for name, lang in [(n, 'ja') for n in ja] + [(n, 'en') for n in en]:
            for item in ('water', 'medicine'):
                for fr in (JA_FRAMES if lang == 'ja' else EN_FRAMES)[item]:
                    out.append({'text': fr.format(d=name), 'label': 'unknown', 'family': fam, 'split': split, 'lang': lang, 'item': item, 'name': name})
    for split, names in (('dev', KNOWN_JA[:4] + KNOWN_EN[:2]), ('test', KNOWN_JA[4:] + KNOWN_EN[2:])):       # the known shelter's spelling variants are also split: the test variants are not seen
        for name in names:
            lang = 'en' if name[0].isascii() and not name.startswith('B') and ' ' in name or name.lower().startswith(('shelter', 'the b', 'b shelter')) else 'ja'
            for item in ('water', 'medicine'):
                for fr in (JA_FRAMES if lang == 'ja' else EN_FRAMES)[item]:
                    out.append({'text': fr.format(d=name), 'label': 'known', 'family': 'B', 'split': split, 'lang': lang, 'item': item, 'name': name})
    for lang, frames in (('ja', NONE_JA), ('en', NONE_EN)):
        for item, fs in frames.items():
            for i, t in enumerate(fs):
                out.append({'text': t, 'label': 'none', 'family': 'none', 'split': 'dev' if i % 2 == 0 else 'test', 'lang': lang, 'item': item, 'name': ''})
    earlier = set()
    for f in ('ig_v1', 'ih_v1', 'held_out_v34', 'dev_v35'):
        earlier |= {json.loads(l)['text'] for l in (ROOT / f'experiments/intent_eval/{f}.jsonl').read_text(encoding='utf8').splitlines() if l.strip()}
    for f in ('intent_flip_set', 'intent_flip_set2'):
        earlier |= {json.loads(l)['text'] for l in (ROOT / f'experiments/{f}.jsonl').read_text(encoding='utf8').splitlines() if l.strip()}
    clash = [x['text'] for x in out if x['text'] in earlier]
    assert not clash, ('a text of an earlier set was generated again; reword the frames', clash)
    return out


def main():
    r = rows()
    p = ROOT / 'experiments/intent_eval/ij_v1.jsonl'
    p.write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in r), encoding='utf8')
    import collections
    print(len(r), 'texts;', dict(collections.Counter((x['label'], x['split']) for x in r)), '->', p.relative_to(ROOT))


if __name__ == '__main__':
    main()
