#!/usr/bin/env python3
"""Study IG (experiments/PREREGISTRATION_IG.md): a fresh set of operator requests, written before any inference on it.

  python3 scripts/make_intent_ig_set.py     # -> experiments/intent_eval/ig_v1.jsonl

Fields: text, expect (accept|reject), item (water|medicine, accept only), category.  An 'accept' text is one a human operator would mean as
"bring <item> to shelter B" (the only shelter of the mission; a text without a shelter name is a request for B).  Everything else is 'reject'.
The texts are listed here by hand and never changed after the registration commit.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W, M = 'water', 'medicine'
ROWS = {
 'polite': [  # accept
  ('避難所Bへ飲料水をお届けください。', W), ('避難所Bに救急箱を届けていただけますか。', M), ('避難所Bまで、お水を運んでいただけますでしょうか。', W),
  ('避難所Bへ医薬品をお願いいたします。', M), ('恐れ入りますが、避難所Bにペットボトルの水を届けてください。', W), ('避難所Bの方々に、応急手当の用品を届けてください。', M),
  ('避難所Bへ飲み水をお願いします。', W), ('避難所Bに薬の入った救急セットをお願いできますか。', M), ('避難所Bの皆さんに水を届けてあげてください。', W),
  ('避難所Bへ救護用品を運搬してください。', M), ('避難所Bに水の補給をお願いします。', W), ('避難所Bに医療用品の補給をお願いします。', M)],
 'casual': [
  ('Bの避難所に水持ってきて', W), ('避難所Bに救急箱たのむ', M), ('B避難所、水ね', W), ('避難所Bにくすり届けてくれる？', M), ('避難所Bに飲み物の水、よろしく', W),
  ('避難所B、ケガ人いるから救急セット持ってって', M), ('避難所Bのみんな喉かわいてるから水お願い', W), ('ちょっと避難所Bに水運んで', W), ('避難所Bに薬ちょうだい、急ぎで', M),
  ('避難所Bへ水を、急いで！', W), ('避難所Bに救急箱、大至急', M), ('避難所Bに水ください', W)],
 'terse': [
  ('B 水', W), ('B 救急', M), ('避難所B 飲料水', W), ('避難所B 医薬品', M), ('水→避難所B', W), ('救急箱→避難所B', M), ('B避難所へ水', W), ('Bへ救急セット', M),
  ('給水 避難所B', W), ('救護物資 避難所B', M)],
 'voice_asr': [   # speech-recognition style: homophone slips, dropped particles, fillers, wrong script
  ('えーっと、避難所Bに、お水を、届けて', W), ('避難所びーに水を届けて', W), ('避難所Bにきゅうきゅうばこをお願い', M), ('あのー避難所Bにみずをお願いします', W),
  ('避難所Bに救急箱 を とどけて ください', M), ('避難所Bに水 水を届けて', W), ('ひなんじょBに、くすりを、運んで', M), ('避難所Bにおみずもってきて', W),
  ('避難所Bに救急ばこ運んでください', M), ('えっと避難所Bに薬をお願い、あ、救急セットで', M), ('避難所Bにミズを届けて', W), ('避難所ビーに救急箱を', M),
  ('避難所Bに、飲、飲料水をお願いします', W), ('避難所Bに 救急 はこ おねがい', M), ('ひなんじょBへ みず おねがい', W)],
 'english': [
  ('Please send drinking water over to shelter B.', W), ('Deliver the first-aid kit to shelter B.', M), ('Shelter B needs water, please send some.', W),
  ('Could you take the medical supplies to shelter B?', M), ('Bring water to B shelter', W), ('first aid kit to shelter B asap', M), ('Water for shelter B, thanks.', W),
  ('Send medicine to shelter B please.', M), ('Take a bottle of water to shelter B.', W), ('Shelter B: first aid, now.', M)],
 'mixed': [
  ('shelter Bにwaterをお願い', W), ('避難所Bにfirst aid kitを届けて', M), ('Bの避難所へmedicineを', M), ('避難所Bにドリンキングウォーターを', W),
  ('避難所Bにメディカルキットを運んで', M), ('shelter Bに水をdeliverして', W)],
 'indirect': [   # a need is stated instead of a command; one supply is clearly implied
  ('避難所Bの人たちが喉をからからにして困っています', W), ('避難所Bで脱水の人が出ています。飲めるものを', W), ('避難所Bに怪我人がいます。手当ての道具を', M),
  ('避難所Bで熱を出した人がいます。薬が必要です', M), ('避難所Bでは飲み水が底をつきました', W), ('避難所Bで切り傷の人が多く、包帯が足りません', M)],
 'no_shelter': [
  ('お水を届けてください', W), ('救急箱をお願いします', M), ('飲料水を運んで', W), ('薬を持ってきて', M), ('Please bring water.', W), ('first aid kit please', M)],
 'negation': [   # one supply is ruled out, the other is wanted
  ('避難所Bには水じゃなくて救急箱を届けて', M), ('避難所Bに水はもう足りているので、薬をお願いします', M), ('避難所Bに救急箱は要らないから水を', W),
  ('避難所Bに薬ではなく飲料水を届けてください', W), ('Not water, the first-aid kit to shelter B.', M), ('No medicine needed at B, bring water.', W)],
}
REJECT = {
 'both': ['避難所Bに水と救急箱の両方を届けて', '避難所Bに水も薬も必要です', '避難所Bへ飲料水と医薬品をまとめて', 'Bの避難所に水と救急セットを一緒に持ってきて',
          'Bring water and a first-aid kit to shelter B.', '避難所Bには水が先、あとで薬も', '避難所Bに水かくすり、どちらでもいい', '避難所Bにあるだけ全部の物資を'],
 'vague': ['避難所Bに何か持ってきて', '避難所Bに必要なものを届けてください', '避難所Bに物資を', '避難所Bの状況を確認してきて', 'Bring something to shelter B.', '避難所Bに役に立つものを', '避難所Bへ行って'],
 'wrong_shelter': ['避難所Aに水を届けて', '避難所Cに救急箱を', '学校の体育館に水を届けてください', '公民館に薬を持っていって', 'Bring water to shelter A.', '避難所Dに救急セットを',
                   '市役所に水をお願い', '避難所1に飲料水を', '避難所Bではなく避難所Aに水を', '北側の避難所に救急箱を'],
 'unsupported_supply': ['避難所Bに毛布をお願い', '避難所Bに食べ物を運んで', '避難所Bに乾電池を', '避難所Bにおむつをお願い', '避難所Bにカセットコンロを', '避難所Bに簡易トイレを届けて',
                        'Bring blankets to shelter B.', '避難所Bにおにぎりを', '避難所Bにスマホの充電器を', '避難所Bにマスクを届けてください', '避難所Bに粉ミルクを', '避難所Bに酸素ボンベを'],
 'irrelevant': ['今日の予定を教えて', 'ありがとう、助かりました', '避難所Bの電気を直して', 'ロボットの電池残量は？', 'What time is it?', '避難所Bにいる人数を数えて', 'マップを見せて', '歌を歌って'],
 'trap': ['避難所Bの水道が止まっているので点検して', '避難所Bの救急隊員を呼んで', '避難所Bに水害の被害報告を送って', '避難所Bの薬局に電話して', '水を飲むな、と避難所Bに伝えて',
          '避難所Bの救急箱は使わないで', '避難所Bで水を配らないで', '避難所Bに届けた水の数を記録して'],
}


def main():
    rows = []
    for cat, items in ROWS.items():
        for t, it in items:
            rows.append({'text': t, 'expect': 'accept', 'item': it, 'category': cat})
    for cat, items in REJECT.items():
        for t in items:
            rows.append({'text': t, 'expect': 'reject', 'category': cat})
    out = ROOT / 'experiments/intent_eval/ig_v1.jsonl'
    out.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf8')
    print(len(rows), 'texts;', sum(r['expect'] == 'accept' for r in rows), 'accept,', sum(r['expect'] == 'reject' for r in rows), 'reject ->', out.relative_to(ROOT))


if __name__ == '__main__':
    main()
