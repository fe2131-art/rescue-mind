#!/usr/bin/env python3
"""Study IH (experiments/PREREGISTRATION_IH.md): a second fresh set of operator requests, aimed at the weakness study IG found (a named destination other than shelter B read as a request for B).

  python3 scripts/make_intent_ih_set.py     # -> experiments/intent_eval/ih_v1.jsonl

Fields as in make_intent_ig_set.py.  Written by hand after the destination rule (rescuemind/intent_llm.names_other_destination) was written and BEFORE any inference on these texts; the rule's place list
is not extended after this file is committed.  Some wrong-destination texts name places the list does not contain on purpose (they measure how far the rule generalises).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W, M = 'water', 'medicine'
ROWS = {
 'polite': [('避難所Bまで飲み水をお届けくださいませ。', W), ('避難所Bの皆様へ救急用品をお届けいただけますか。', M), ('避難所Bにミネラルウォーターをお願いできますでしょうか。', W),
            ('避難所Bへ消毒液と包帯の入った箱をお願いします。', M), ('避難所Bのために飲用水をご用意ください。', W), ('避難所Bに医療品をお運びください。', M),
            ('避難所Bに水をお持ちいただければ幸いです。', W), ('避難所Bへ応急処置のセットをご配送ください。', M)],
 'casual': [('避難所Bに水、頼んだ！', W), ('避難所Bにケガ用の道具よろしく', M), ('Bの避難所へ飲み物の水、運んどいて', W), ('避難所Bに薬持ってきてくれない？', M),
            ('避難所B、水が足りないんだよね、お願い', W), ('避難所Bに救急セット急ぎでお願い！', M), ('水をBの避難所に届けて〜', W), ('避難所Bへ絆創膏とか薬とか…いや薬だけで', M)],
 'terse': [('避難所B、給水', W), ('B避難所 薬', M), ('飲料水 B', W), ('救急セット→B', M), ('水、避難所Bへ', W), ('医療品 避難所B', M)],
 'voice_asr': [('えーと避難所Bにお水をおねがい', W), ('ひなんじょBにきゅうきゅうセットをおねがいします', M), ('避難所Bに、あの、薬を、届けて', M), ('避難所Bにのみみずをとどけて', W),
               ('避難所ビーへ、みず、お願いします', W), ('避難所Bに救急のはこをもってきて', M), ('えっとあのう避難所Bに飲料水', W), ('避難所Bにくすりをおねがいします', M)],
 'english': [('Could you deliver some water to shelter B?', W), ('Shelter B needs a first-aid kit, can you bring one?', M), ('Water to shelter B, please.', W), ('Please take medicine to shelter B.', M),
             ('Bring a few bottles of water over to shelter B.', W), ('Medical supplies for shelter B, quickly.', M), ('Get shelter B some drinking water.', W), ('Deliver the first aid box to B shelter.', M)],
 'mixed': [('避難所Bにdrinking waterをお願いします', W), ('shelter Bにmedical suppliesを届けて', M), ('Bの避難所へwater bottleを', W), ('避難所Bにfirst-aidをお願い', M)],
 'indirect': [('避難所Bの子どもたちがのどが渇いたと言っています', W), ('避難所Bで転んで膝をすりむいた人がいます', M), ('避難所Bでは飲めるものが残っていません', W), ('避難所Bで頭痛を訴える人が増えてきました', M)],
 'no_shelter': [('飲用水をお願いします', W), ('医療品を届けてください', M), ('Please bring medicine.', M), ('some drinking water please', W)],
 'negation': [('避難所Bに薬は十分あるので水を届けて', W), ('避難所Bには水ではなく医療品を', M), ('Not medicine, water for shelter B.', W)],
 'place_context': [   # a place word appears but the destination is B (or the place is a source): the rule must not refuse the first four; the last four have no B and may be refused (a question, not a delivery)
     ('体育館になっている避難所Bに水を届けてください', W), ('学校の避難所Bに救急箱をお願いします', M), ('病院の備蓄の薬を避難所Bまで運んでください', M), ('駅前から見える避難所Bに水をお願いします', W),
     ('福祉施設から預かった薬を届けてください', M), ('センターの倉庫にある水を持っていってください', W), ('病院でもらった薬を届けて', M), ('学校の水道水ではなく買った水を届けて', W)],
}
REJECT = {
 'listed_place': ['体育館に飲料水を届けてください', '駅に救急箱をお願いします', '病院に水を運んで', '学校に薬を届けて', 'Deliver water to the school.', 'Take the first-aid kit to the hospital.',
                  '区役所に飲み水をお願いします', '自宅に薬を持ってきて', 'ホテルに水を届けて', '教会に救急セットを'],
 'unlisted_place': ['ショッピングモールに水を届けて', '図書館に救急箱を運んで', '山小屋に飲料水をお願い', '川向こうの集落に薬を届けて', '駐車場にいる人たちに水を', 'バス停に救急セットを持ってきて',
                    '競技場に飲み水を', '寮に薬を届けて', '商店街の入口に水をお願いします', 'ゴルフ場に救急箱を', '神社の境内に水を', '漁協の建物に薬を',
                    'Send water to the library.', 'Take medicine to the stadium.', 'Bring the first aid kit to the bus stop.', '農協の事務所に飲料水を', '橋の下にいる人に水を', '海沿いの小屋に薬を',
                    '消防団の詰所に水を届けて', '町営プールに救急箱を'],
 'oriented': ['第二避難所に水を届けて', '二番目の避難所に救急箱をお願い', '東の避難所へ飲料水を', 'もう一つの避難所に薬を運んで', 'Bring water to the second shelter.', 'Take the first-aid kit to the north shelter.',
              '避難所2に水を', '新しい避難所に薬を届けて', '川の向こう側の避難所に水を', '避難所Eに救急箱を'],
 'both': ['避難所Bに水と薬の両方を', '避難所Bに水か救急箱を持ってきて', 'Water and medicine for shelter B.', '避難所Bに飲料水も医療品も届けて', '避難所Bにあるもの全部', '避難所Bに水を、それから薬も'],
 'vague': ['避難所Bに何でもいいので', '避難所Bへ荷物を', 'Take something to shelter B.', '避難所Bの様子を教えて', '避難所Bに行ってきて', '避難所Bに頼まれたものを'],
 'unsupported_supply': ['避難所Bに缶詰を', '避難所Bにヘルメットを届けて', '避難所Bにストーブを', '避難所Bに生理用品を', 'Bring food to shelter B.', '避難所Bに懐中電灯を持ってきて', '避難所Bに寝袋を', '避難所Bに発電機を'],
 'irrelevant': ['電池はあと何パーセント？', 'いまの位置を教えて', 'Go back to the charging station.', '避難所Bの地図を見せて', '充電して', '写真を撮って'],
 'trap': ['避難所Bの水の消費量を報告して', '避難所Bの医療スタッフの人数を教えて', '避難所Bで配った水の記録を送って', '避難所Bに薬を届けないで', '避難所Bの水を止めて', '避難所Bにある救急箱の数を数えて'],
}


def main():
    rows = []
    for cat, items in ROWS.items():
        for t, it in items:
            rows.append({'text': t, 'expect': 'accept', 'item': it, 'category': cat})
    for cat, items in REJECT.items():
        for t in items:
            rows.append({'text': t, 'expect': 'reject', 'category': cat})
    out = ROOT / 'experiments/intent_eval/ih_v1.jsonl'
    out.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf8')
    print(len(rows), 'texts;', sum(r['expect'] == 'accept' for r in rows), 'accept,', sum(r['expect'] == 'reject' for r in rows), 'reject ->', out.relative_to(ROOT))


if __name__ == '__main__':
    main()
