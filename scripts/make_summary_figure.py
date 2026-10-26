#!/usr/bin/env python3
"""I-189: the Japanese summary figure (page 1 of the report, README) -> docs/figures/graphical_abstract_ja.png (2000x1125).
Plain words, few elements: the problem, the three ideas, four headline results as "before -> after" (the numbers are read from the
result files; a missing file drops its card), and the one result that did not work.  Called by make_graphical_abstract.py.
Run inside the dev container (Noto Sans CJK): docker exec rm-dev python3 scripts/make_graphical_abstract.py"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import advice_numbers  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'
FR = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
FB = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
W, H = 2000, 1125
BG, INK, MUTED = (250, 250, 248), (30, 34, 40), (95, 102, 112)
BLUE, GREEN, RED, ORANGE = (40, 110, 210), (25, 150, 105), (205, 55, 55), (225, 95, 45)
PALE = {BLUE: (230, 239, 252), GREEN: (224, 244, 234), RED: (252, 234, 234), ORANGE: (253, 238, 228)}
_fc: dict = {}


def font(s, b=False):
    if (s, b) not in _fc:
        _fc[(s, b)] = ImageFont.truetype(FB if b else FR, s)
    return _fc[(s, b)]


def jl(n):
    f = RES / n
    try:
        return json.loads(f.read_text()) if f.is_file() else None
    except ValueError:
        return None


def wrap(d, text, f, maxw):
    lines, cur = [], ''
    for ch in text:
        if ch == '\n':
            lines.append(cur)
            cur = ''
            continue
        if d.textlength(cur + ch, font=f) > maxw and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    return lines + ([cur] if cur else [])


def text_block(d, xy, text, size, maxw, fill=INK, bold=False, lead=1.35):
    f = font(size, bold)
    x, y = xy
    for ln in wrap(d, text, f, maxw):
        d.text((x, y), ln, font=f, fill=fill)
        y += int(size * lead)
    return y


def card(d, box, col, fill=None, w=4):
    d.rounded_rectangle(box, 22, fill=fill or (255, 255, 255), outline=col, width=w)


def results():
    """Four headline results (label, scope, big text, caption, colour); each only when its result file exists."""
    out = []
    led = RES / 'campaign_E_ledger.jsonl'
    if led.is_file():
        rs = [r for r in (json.loads(x) for x in led.read_text(encoding='utf8').splitlines() if x.strip()) if r.get('final', True)]
        ok = sum(r['correct'] for r in rs)
        wrong = sum(r['observed_action'] in ('ALLOW', 'ALLOW_AFTER_SEARCH') and r['expected_action'] not in ('ALLOW', 'DELIVER_AFTER_SEARCH') for r in rs)
        out.append(('ランダムに作った場面', f'{len(rs)}場面', f'{ok}/{len(rs)}', f'すべて正しく行動（間違った配達 {wrong}件）', GREEN))
    g = jl('g_summary.json')
    if g:
        pr = g['primary']
        out.append(('物資の影にある火', f"{pr['n_world_pairs_fire_perceivable']}場面", f"{pr['wrong_deliveries_B']}件 → {pr['wrong_deliveries_C']}件",
                    '火の場所へ配達した回数（正面だけ → 横から見直す）', GREEN))
    af = advice_numbers.a_facts()
    if af and af['worlds']['naive'] and af['worlds']['monotone']:
        w = af['worlds']
        out.append(('うその情報を与えても', f"{w['naive'][1]}場面", f"{w['naive'][0]}件 → {w['monotone'][0]}件",
                    '危険な配達が起きた場面（信じる方式 → 本方式）', GREEN))
    h = jl('h_summary.json')
    if h:
        p1, p3 = h['P1_efficiency_relocation_persist'], h['P3_no_extra_risk_vs_v36']
        out.append(('前回の配達を覚えておく', f"{p3['n_pairs']}回の配達", f"{p1['time_M0_median_s']:.0f}秒 → {p1['time_M2_median_s']:.0f}秒",
                    f"物資が移された{p1['n_pairs']}回の所要時間（中央値）。危険な配達 {p3['unsafe_M2']}件", GREEN))
    return out


def build():
    im = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((60, 28), 'RescueMind', font=font(76, True), fill=INK)
    tw = int(d.textlength('RescueMind', font=font(76, True)))
    d.text((60 + tw + 30, 56), '自分の目で確かめてから届ける、災害物資ロボット', font=font(44), fill=MUTED)
    # ---- problem
    card(d, (50, 130, 1950, 300), RED, PALE[RED])
    d.text((90, 142), '問題', font=font(34, True), fill=RED)
    text_block(d, (90, 188), '災害現場は計画どおりにいかない。予定の場所に物資が無い、別の物資が置かれている、火災が起きている。'
               '指示どおり運ぶだけのロボットは、誤った物資や危険な場所へ届けてしまう。', 33, 1820, lead=1.3)
    # ---- three ideas
    d.text((60, 315), '3つの工夫', font=font(40, True), fill=INK)
    ideas = [('1', 'その場で確かめ、迷えば止まる', 'カメラで物資と火・煙を確かめ、すべてそろったときだけ届ける。迷ったら止まる。', BLUE),
             ('2', '横から見直す', '物資の影にある小さな火は、正面からは見えない。横へ動いて撮り直す。', ORANGE),
             ('3', '聞いた情報で確認を省かない', '記憶・他のロボット・依頼文の「確認不要」は、行き先を決めるのにだけ使い、確認は必ず行う。', GREEN)]
    x0 = 50
    for i, (n, ttl, body, col) in enumerate(ideas):
        bx = x0 + i * 636
        card(d, (bx, 370, bx + 612, 605), col, PALE[col])
        d.ellipse((bx + 22, 384, bx + 82, 444), fill=col)
        d.text((bx + 52, 414), n, font=font(40, True), fill='white', anchor='mm')
        text_block(d, (bx + 100, 390), ttl, 32, 500, col, True, 1.25)
        text_block(d, (bx + 28, 465), body, 27, 560, INK, False, 1.3)
    # ---- results
    d.text((60, 625), '主な結果（すべてシミュレーション）', font=font(40, True), fill=INK)
    d.text((790, 637), '「→」の左が工夫の前、右が工夫の後', font=font(30), fill=MUTED)
    res = results()
    n = len(res)
    cw = (1900 - 24 * (n - 1)) // max(n, 1)
    for i, (label, scope, big, cap, col) in enumerate(res):
        bx = 50 + i * (cw + 24)
        card(d, (bx, 685, bx + cw, 962), col, (255, 255, 255))
        d.text((bx + 24, 698), label, font=font(30, True), fill=col)
        d.text((bx + 24, 738), f'（{scope}）', font=font(26), fill=MUTED)
        bf = font(66, True)
        sz = 66
        while d.textlength(big, font=bf) > cw - 40 and sz > 36:
            sz -= 2
            bf = font(sz, True)
        d.text((bx + 24, 775), big, font=bf, fill=INK)
        text_block(d, (bx + 24, 860), cap, 27, cw - 44, MUTED, False, 1.22)
    # ---- the result that did not work
    qi = jl('qi_summary.json')
    note = '今後の課題'
    if qi and qi.get('R', {}).get('miss'):
        note = f"うまくいかなかった結果も公開：写真に近づけた画像では、火の見逃しが {qi['xd_baseline']['miss']['k']}件 → {qi['R']['miss']['k']}件に増えた（今後の課題）"
    card(d, (50, 976, 1950, 1030), RED, PALE[RED], 3)
    d.text((80, 1003), note, font=font(30), fill=RED, anchor='lm')
    d.rounded_rectangle((40, 1050, W - 40, 1110), 18, fill=INK)
    d.text((W // 2, 1080), '評価の条件は結果を見る前に決め、全試行を公開。評価はすべてシミュレーション上で行った',
           font=font(34), fill='white', anchor='mm')
    return im


if __name__ == '__main__':
    p = ROOT / 'docs/figures/graphical_abstract_ja.png'
    build().save(p, optimize=True)
    print('wrote', p)
