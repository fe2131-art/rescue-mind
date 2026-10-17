#!/usr/bin/env python3
"""One-page graphical abstract (2000x1125), Japanese and English.

All numbers are read from experiments/results/*summary*.json and the campaign_E ledger.
Run inside the dev container (Noto Sans CJK):
  docker exec rm-dev python3 scripts/make_graphical_abstract.py
"""
from __future__ import annotations
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'
FIG = ROOT / 'docs/figures'
FR = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
FB = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
W, H = 2000, 1125
BG, INK, MUTED, CARD = (250, 250, 248), (30, 34, 40), (95, 102, 112), (243, 243, 241)
BLUE, GREEN, RED, ORANGE = (40, 110, 210), (25, 165, 115), (215, 60, 60), (235, 100, 50)
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


def numbers():
    n = {}
    rows = [json.loads(x) for x in (RES / 'campaign_E_ledger.jsonl').read_text().splitlines() if x.strip()]
    rows = [r for r in rows if r.get('final', True)]
    safe = ('ALLOW', 'DELIVER_AFTER_SEARCH')
    n['E_ok'], n['E_n'] = sum(r['correct'] for r in rows), len(rows)
    n['E_wrong'] = sum(bool(r.get('delivered')) and r['expected_action'] not in safe for r in rows)
    g = jl('g_summary.json')
    n['G_B'], n['G_C'] = g['per_config']['B']['wrong_deliveries'], g['per_config']['C']['wrong_deliveries']
    n['G_n'], n['G_p'] = g['primary']['n_world_pairs_fire_perceivable'], g['primary']['mcnemar_p']
    r = jl('r_summary.json')['P1_pooled']
    n['R_fa'], n['R_n'] = r['false_approvals'], r['n']
    z = jl('z_summary.json')['models']['siglip']['t1']
    n['Z_b'], n['Z_o'], n['Z_n'] = z['baseline']['FA'], z['ours']['FA'], z['ours']['n_deny']
    p = jl('p_summary.json')
    n['P_r'], n['P_fa'] = p['recall'], p['false_alarm']
    h, j = jl('h_summary.json'), jl('j_summary.json')
    n['H'], n['J'] = h is not None, j is not None
    return n


T = {
 'ja': dict(
  title='RescueMind', sub='現地で「目で確かめてから」届ける災害物資ロボット',
  prob_h='問題', prob='災害時、\n在庫表と現場は違い、\n危険は隠れる',
  chip1='在庫表 ≠ 現場', chip2='危険は見えにくい', imgcap='Gazebo実レンダリング（俯瞰＋搭載カメラ）', solve='だから、その場で目で確かめる',
  mid_h='3つの工夫', i1='その場で目で確かめる', i1d='2つの選択式質問と火の質問の確率を読み、\n全部そろったときだけ許可。迷えば拒否＝安全側。',
  i2='横から見直す', i2d='正面で見落とす小さな火を、\n0.4 m 横へ動いて撮り直して見つける。',
  i3='記憶は提案だけ', i3d='前回の記憶は「先に行く拠点」を決めるだけ。\n確認は決して省かない。',
  front='正面', side='横 0.4 m', ph='火の確率\n正面 0.002 → 横 0.82', appr='許可', refu='拒否',
  q1='質問1', q2='質問2（並べ替え）', qh='火・煙', concept='概念図', thr='閾値',
  safe_side='どれか欠ければ拒否', mem_in='記憶', mem_a='先に行く拠点を提案', mem_b='その場で必ず確認', mem_x='確認を省く',
  res_h='主な結果（事前登録・実測）',
  E=('E  ランダム世界の閉ループ', '{ok}/{n}', '期待どおり・誤配達 {w}/{n}'),
  G=('G  横から見直し', '{b}/{n} → {c}/{n}', '火があるのに配達した数（p={p:.3f}）'),
  R=('R  カメラ劣化12条件', '{fa}/{n}', '誤許可（安全側に倒れる）'),
  Z=('Z  ゼロショット基準', '{b}/{n} vs {o}/{n}', '誤許可：SigLIP 対 本方式'),
  P=('P  実写真（正直に）', '{r}/{rn}', '火・煙の検出。ただし火なしの誤警報は {f}/{fn}'),
  HJ_run='評価H・J 実行中', HJ_done='評価H・J 完了（README参照）',
  strip='すべて事前登録・全試行公開・シミュレーション（実機なし）'),
 'en': dict(
  title='RescueMind', sub='A disaster-relief delivery robot that checks with its own eyes before it delivers',
  prob_h='Problem', prob='In a disaster, the inventory list and the scene disagree, and hazards hide',
  chip1='Inventory ≠ reality', chip2='Hazards hide', imgcap='Gazebo real render (overview + onboard cam)', solve='So: check on site',
  mid_h='Three ideas', i1='Check on site', i1d='Two multiple-choice questions + a fire question.\nApprove only if all agree; doubt = refuse.',
  i2='Look again from the side', i2d='Move 0.4 m sideways and re-shoot to catch a small fire missed from the front.',
  i3='Memory only proposes', i3d='Memory only picks which station to visit first.\nIt never skips the check.',
  front='front', side='side 0.4 m', ph='fire probability\n0.002 → 0.82 (side)', appr='approve', refu='refuse',
  q1='Question 1', q2='Question 2 (permuted)', qh='fire / smoke', concept='schematic', thr='threshold',
  safe_side='any miss = refuse', mem_in='memory', mem_a='proposes the order', mem_b='check on site', mem_x='skip the check',
  res_h='Key results (pre-registered)',
  E=('E  closed loop, random worlds', '{ok}/{n}', 'as expected; wrong deliveries {w}/{n}'),
  G=('G  look-around', '{b}/{n} → {c}/{n}', 'deliveries despite a fire (p={p:.3f})'),
  R=('R  12 camera degradations', '{fa}/{n}', 'false approvals (fails safe)'),
  Z=('Z  zero-shot baseline', '{b}/{n} vs {o}/{n}', 'false approvals: SigLIP vs ours'),
  P=('P  real photos (honest)', '{r}/{rn}', 'fire/smoke found. False alarms (no fire): {f}/{fn}'),
  HJ_run='Studies H, J: running', HJ_done='Studies H, J: done (see README)',
  strip='All pre-registered | every trial published | simulation only (no real robot)'),
}


def wrap(d, text, f, maxw):
    out = []
    for para in text.split('\n'):
        cur = ''
        toks = para.split(' ') if ' ' in para else list(para)
        sep = ' ' if ' ' in para else ''
        for tk in toks:
            trial = cur + (sep if cur and sep else '') + tk
            if d.textlength(trial, font=f) > maxw and cur:
                out.append(cur); cur = tk
            else:
                cur = trial
        out.append(cur)
    return out


def paras(d, xy, text, f, maxw, fill=INK, lh=1.35):
    x, y = xy
    for ln in wrap(d, text, f, maxw):
        d.text((x, y), ln, font=f, fill=fill)
        y += int(f.size * lh)
    return y


def card(d, box, fill=CARD, outline=None, r=22, w=4):
    d.rounded_rectangle(box, r, fill=fill, outline=outline, width=w)


def chip(d, xy, text, f, fg, bg):
    w = d.textlength(text, font=f) + 36
    d.rounded_rectangle((xy[0], xy[1], xy[0] + w, xy[1] + f.size + 20), 16, fill=bg)
    d.text((xy[0] + 18, xy[1] + 8), text, font=f, fill=fg)
    return xy[0] + w


def arrow(d, x0, x1, y, col=INK):
    d.line((x0, y, x1 - 8, y), fill=col, width=5)
    d.polygon([(x1, y), (x1 - 18, y - 11), (x1 - 18, y + 11)], fill=col)


def circled(d, cx, cy, n, col):
    d.ellipse((cx - 24, cy - 24, cx + 24, cy + 24), fill=col)
    d.text((cx, cy), str(n), font=font(30, True), fill='white', anchor='mm')


def build(lang):
    t, n = T[lang], numbers()
    im = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(im)
    # header
    d.text((50, 22), t['title'], font=font(66, True), fill=INK)
    d.text((50 + d.textlength(t['title'], font=font(66, True)) + 30, 52), t['sub'], font=font(36), fill=MUTED)
    top, bot = 112, 1020
    # ---- left: problem
    lx0, lx1 = 40, 640
    card(d, (lx0, top, lx1, bot), outline=BLUE)
    d.text((lx0 + 30, top + 22), t['prob_h'], font=font(36, True), fill=BLUE)
    y = paras(d, (lx0 + 30, top + 80), t['prob'], font(42, True), lx1 - lx0 - 60)
    hero = Image.open(FIG / 'hero_gazebo.png').convert('RGB')
    hw = lx1 - lx0 - 60
    hh = int(hw * hero.height / hero.width)
    y += 24
    im.paste(hero.resize((hw, hh), Image.LANCZOS), (lx0 + 30, y))
    d.rectangle((lx0 + 30, y, lx0 + 30 + hw, y + hh), outline=(180, 185, 190), width=2)
    y += hh + 12
    y = paras(d, (lx0 + 30, y), t['imgcap'], font(24), hw, MUTED, 1.3) + 18
    x = lx0 + 30
    f = font(32, True)
    x = chip(d, (x, y), t['chip1'], f, RED, (252, 232, 232)) + 14
    if x + d.textlength(t['chip2'], font=f) + 36 > lx1 - 30:
        x, y = lx0 + 30, y + 70
    chip(d, (x, y), t['chip2'], f, ORANGE, (253, 237, 226))
    y += 78
    arrow(d, lx0 + 30, lx0 + 80, y + 20, GREEN)
    d.text((lx0 + 96, y), t['solve'], font=font(30, True), fill=GREEN)
    # ---- centre: three ideas
    cx0, cx1 = 680, 1360
    d.text((cx0, top - 4), t['mid_h'], font=font(34, True), fill=INK)
    ph = 280
    ys = [top + 46 + i * (ph + 8) for i in range(3)]
    cols = [GREEN, ORANGE, BLUE]
    heads = [t['i1'], t['i2'], t['i3']]
    descs = [t['i1d'], t['i2d'], t['i3d']]
    for i in range(3):
        y0 = ys[i]
        card(d, (cx0, y0, cx1, y0 + ph), fill=(255, 255, 255), outline=cols[i])
        circled(d, cx0 + 42, y0 + 42, i + 1, cols[i])
        d.text((cx0 + 84, y0 + 20), heads[i], font=font(36, True), fill=cols[i])
        paras(d, (cx0 + 26, y0 + 76), descs[i], font(24), cx1 - cx0 - 52, INK, 1.3)
    # panel 1 visual: probability bars with threshold
    y0 = ys[0] + 152
    f = font(21)
    bars = [(t['q1'], 0.9, GREEN), (t['q2'], 0.86, GREEN), (t['qh'], 0.08, RED)]
    bx, bw = cx0 + 270, 170
    for k, (lab, v, c) in enumerate(bars):
        yy = y0 + k * 34
        d.text((cx0 + 26, yy), lab, font=f, fill=MUTED)
        d.rectangle((bx, yy + 5, bx + bw, yy + 23), fill=(232, 232, 230))
        d.rectangle((bx, yy + 5, bx + int(bw * v), yy + 23), fill=c)
    d.line((bx + bw // 2, y0 - 4, bx + bw // 2, y0 + 102), fill=INK, width=2)
    d.text((bx + bw // 2, y0 + 104), t['thr'], font=font(17), fill=MUTED, anchor='ma')
    ax = bx + bw + 24
    arrow(d, ax, ax + 46, y0 + 48)
    chip(d, (ax + 60, y0 + 2), t['appr'], font(24, True), 'white', GREEN)
    chip(d, (ax + 60, y0 + 58), t['refu'], font(24, True), 'white', RED)
    d.text((cx1 - 22, ys[0] + 34), t['concept'], font=font(18), fill=MUTED, anchor='ra')
    # panel 2 visual: two images from the paper figure
    pic = Image.open(ROOT / 'docs/report/figures/fig_lookaround.png').convert('RGB')
    a_, b_ = pic.crop((0, 34, 502, 409)), pic.crop((520, 34, 1022, 409))
    iw, ih = 150, 112
    y0 = ys[1] + 148
    xs2 = (cx0 + 26, cx0 + 26 + iw + 70)
    for img, xx, lab, ok, col in ((a_, xs2[0], t['front'], t['appr'], GREEN), (b_, xs2[1], t['side'], t['refu'], RED)):
        im.paste(img.resize((iw, ih), Image.LANCZOS), (xx, y0))
        d.rectangle((xx, y0, xx + iw, y0 + ih), outline=col, width=4)
        chip(d, (xx + 4, y0 + 4), lab, font(18, True), INK, (255, 255, 255))
        d.rounded_rectangle((xx + iw - 92, y0 + ih - 34, xx + iw - 4, y0 + ih - 4), 10, fill=col)
        d.text((xx + iw - 48, y0 + ih - 19), ok, font=font(20, True), fill='white', anchor='mm')
    arrow(d, xs2[0] + iw + 10, xs2[1] - 10, y0 + ih // 2)
    paras(d, (xs2[1] + iw + 22, y0 + 20), t['ph'], font(22, True), cx1 - (xs2[1] + iw + 22) - 18, RED, 1.3)
    # panel 3 visual: memory proposes -> always check; skipping is crossed out
    y0 = ys[2] + 150
    f = font(21, True)
    x = cx0 + 26
    x2 = chip(d, (x, y0), t['mem_in'], f, BLUE, (225, 236, 252))
    arrow(d, x2 + 8, x2 + 44, y0 + 23)
    x3 = chip(d, (x2 + 56, y0), t['mem_a'], f, BLUE, (225, 236, 252))
    arrow(d, x3 + 8, x3 + 44, y0 + 23)
    chip(d, (x3 + 56, y0), t['mem_b'], f, GREEN, (221, 244, 233))
    y1 = y0 + 62
    xe = chip(d, (x, y1), t['mem_x'], f, MUTED, (236, 236, 234))
    d.line((x + 8, y1 + 23, xe - 8, y1 + 23), fill=RED, width=4)
    d.line((xe + 16, y1 + 6, xe + 42, y1 + 40), fill=RED, width=6)
    d.line((xe + 16, y1 + 40, xe + 42, y1 + 6), fill=RED, width=6)
    # ---- right: results
    rx0, rx1 = 1400, 1960
    d.text((rx0, top - 4), t['res_h'], font=font(34, True), fill=INK)
    items = [
        ('E', GREEN, t['E'][0], t['E'][1].format(ok=n['E_ok'], n=n['E_n']), t['E'][2].format(w=n['E_wrong'], n=n['E_n'])),
        ('G', BLUE, t['G'][0], t['G'][1].format(b=n['G_B'], c=n['G_C'], n=n['G_n']), t['G'][2].format(p=n['G_p'])),
        ('R', GREEN, t['R'][0], t['R'][1].format(fa=n['R_fa'], n=n['R_n']), t['R'][2]),
        ('Z', BLUE, t['Z'][0], t['Z'][1].format(b=n['Z_b'], o=n['Z_o'], n=n['Z_n']), t['Z'][2]),
        ('P', ORANGE, t['P'][0], t['P'][1].format(r=n['P_r']['k'], rn=n['P_r']['n']),
         t['P'][2].format(f=n['P_fa']['k'], fn=n['P_fa']['n'])),
    ]
    ch, gap = 140, 8
    for i, (k, c, name, big, small) in enumerate(items):
        y0 = top + 46 + i * (ch + gap)
        card(d, (rx0, y0, rx1, y0 + ch), fill=(255, 255, 255), outline=c, w=3)
        d.rectangle((rx0 + 2, y0 + 20, rx0 + 12, y0 + ch - 20), fill=c)
        d.text((rx0 + 28, y0 + 10), name, font=font(24, True), fill=c)
        d.text((rx0 + 28, y0 + 42), big, font=font(48 if len(big) < 12 else 42, True), fill=INK)
        paras(d, (rx0 + 28, y0 + 100), small, font(21), rx1 - rx0 - 50, MUTED, 1.2)
    y0 = top + 46 + 5 * (ch + gap)
    hj = n['H'] and n['J']
    chip(d, (rx0, y0 + 2), t['HJ_done'] if hj else t['HJ_run'], font(26, True), MUTED, (232, 232, 230))
    # ---- bottom strip
    d.rounded_rectangle((40, 1040, W - 40, 1105), 18, fill=INK)
    d.text((W // 2, 1073), t['strip'], font=font(36, True), fill='white', anchor='mm')
    return im


def main():
    out = ROOT / 'docs/figures'
    for lang in ('ja', 'en'):
        p = out / f'graphical_abstract_{lang}.png'
        build(lang).save(p, optimize=True)
        print('wrote', p)


if __name__ == '__main__':
    main()
