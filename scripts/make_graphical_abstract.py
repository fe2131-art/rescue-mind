#!/usr/bin/env python3
"""One-page graphical abstract (2000x1125), Japanese and English: the single story of the paper
('Advice May Only Tighten').  Left = problem, middle = three ideas as a chain
(1 check and stop when unsure -> 2 look again from the side -> 3 untrusted inputs may only tighten),
right = results.  All numbers are read from experiments/results/*summary*.json; studies that have not run
yet (A adversarial advice, X realistic depot) show a PENDING chip that turns into numbers by itself once
a_summary.json / x_summary.json exist.  Text that does not fit is shrunk or wrapped; any overflow is reported.
Run inside the dev container (Noto Sans CJK):
  docker exec rm-dev python3 scripts/make_graphical_abstract.py
"""
from __future__ import annotations
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import advice_numbers  # noqa: E402  (I-23 z3 numbers, I-24 credit-model numbers)

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'
FIG = ROOT / 'docs/figures'
FR = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
FB = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
W, H = 2000, 1125
BG, INK, MUTED, CARD = (250, 250, 248), (30, 34, 40), (95, 102, 112), (243, 243, 241)
BLUE, GREEN, RED, ORANGE = (40, 110, 210), (25, 165, 115), (215, 60, 60), (235, 100, 50)
PURPLE = (120, 80, 170)
PALE = {GREEN: (221, 244, 233), BLUE: (225, 236, 252), RED: (252, 232, 232), ORANGE: (253, 237, 226), PURPLE: (238, 231, 248)}
_fc: dict = {}
WARN: list = []


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
    """Every number comes from a result file; a missing study is None (-> PENDING chip), never a made-up value."""
    n = {}
    try:
        g = jl('g_summary.json')
        n['G'] = (g['per_config']['B']['wrong_deliveries'], g['per_config']['C']['wrong_deliveries'],
                  g['primary']['n_world_pairs_fire_perceivable'], g['primary']['mcnemar_p'])
    except (TypeError, KeyError):
        n['G'] = None
    try:
        h = jl('h_summary.json')
        p2, p1 = h['P2_safety_naive_vs_verified'], h['P1_efficiency_relocation_persist']
        n['H'] = dict(naive=p2['unsafe_M1'], ours=p2['unsafe_M2'], n=p2['n_pairs'], m0=h['P3_no_extra_risk_vs_v36']['unsafe_M0'],
                      t0=round(p1['time_M0_median_s']), t2=round(p1['time_M2_median_s']), npair=p1['n_pairs'])
    except (TypeError, KeyError):
        n['H'] = None
    try:
        c = jl('p2_summary.json')['chosen_test']
        n['P2'] = (c['recall']['k'], c['recall']['n'], c['false_alarm']['k'], c['false_alarm']['n'])
    except (TypeError, KeyError):
        n['P2'] = None
    try:
        l_ = jl('l_summary.json')
        n['L'] = (l_['primary']['correct'], l_['n_trials'], l_['primary']['unsafe_deliveries'])
    except (TypeError, KeyError):
        n['L'] = None
    try:  # study A (scripts/a_analysis.py): naive advice-following vs ours, unsafe deliveries
        a = jl('a_summary.json')['A1_unsafe_naive_vs_monotone']['runs']
        n['A'] = (a['naive']['unsafe'], a['naive']['n'], a['monotone']['unsafe'], a['monotone']['n'])
    except (TypeError, KeyError):
        n['A'] = None
    try:  # study X (scripts/x_analysis.py): four-station depot, memory vs none (visited bays), unsafe deliveries in hazard cells
        x = jl('x_summary.json')
        v, hz = x['X-m']['visits'], x['X-a']['hazard_cells_unsafe']
        n['X'] = (v['mean_M0'], v['mean_M2'], hz['k'], hz['n'])
        if v['mean_M0'] is None or v['mean_M2'] is None:
            n['X'] = None
    except (TypeError, KeyError):
        n['X'] = None
    return n


T = {
 'ja': dict(
  title='RescueMind', sub='助言は「厳しくする」ことしかできない災害物資ロボット',
  prob_h='問題', prob='災害時、\n在庫表と現場は違い、\n危険は隠れる',
  chips=[('在庫表 ≠ 現場', RED), ('危険は見えにくい', ORANGE), ('助言も当てにならない', PURPLE)],
  imgcap='Gazebo実レンダリング（俯瞰＋搭載カメラ）', solve='だから、確かめ、迷えば止まる',
  new_h='新：保証の機械検証と期間の上限',
  new='命題2を実装で機械検証：z3 {u}件、{c}件で不一致{d}、バグ{k}/{m}検出。締めるだけが必要十分。嘘つきの代償 +{ln}→+{ly}秒（信用枠）{pend}',
  mid_h='3つの工夫（上から順に積み上げる）',
  i1='その場で確かめ、迷えば止まる', i1d='選択式の質問と火の質問の確率を読み、全部そろったときだけ許可。迷えば拒否。',
  i2='横から見直す', i2d='正面で見落とす小さな火を、0.4 m 横へ動いて撮り直して見つける。',
  i3='信頼できない入力は「締める」だけ',
  i3d='記憶・他のロボット・依頼文の言葉・在庫表は「助言」。拠点の順序を変えるか判断を厳しくするだけで、確認は決して省けない。',
  front='正面', side='横 0.4 m', ph='火の確率  正面 0.002 → 横 0.82', appr='許可', refu='拒否',
  q1='質問1', q2='質問2（並べ替え）', qh='火・煙', concept='概念図', thr='閾値',
  ins=['記憶', '他のロボット', '依頼文の言葉', '在庫表'], adv='助言', adv2='提案だけ',
  ok_='順序を変える・判断を厳しくする', bad='確認を省く（禁止）',
  naive='素朴に従う：危険な配達 {a}/{n}', ours='本方式：危険な配達 {b}/{n}',
  res_h='主な結果（事前登録・実測）', pend='結果待ち',
  L=('L  未知の配置24通り', '{ok}/{n}', '期待どおり・危険な配達 {u}'),
  G=('G  横から見直し', '{b}/{n} → {c}/{n}', '火があるのに配達した数（p={p:.3f}）'),
  H=('H  記憶をまたぐ出動', '{t0}→{t2} 秒', '移されたまま続く{np}出動の所要時間。危険な配達：記憶なし {m0}/{n}・本方式 {b}/{n}・確認を省く記憶 {a}/{n}（設計上）'),
  A=('A  悪意ある助言', '{an}/{nn} → {ao}/{no}', '危険な配達：助言どおりに動く方式 → 本方式'),
  A_p='危険な配達：助言どおりに動く方式 対 本方式（閉ループ）',
  X=('X  現実的な倉庫（4拠点）', '{m0:.1f} → {m2:.1f} 拠点', '記憶なし → あり（訪問数）。火・煙の世界の危険な配達 {k}/{hn}'),
  X_p='4拠点の倉庫で記憶あり対なし（閉ループ）',
  P2=('P2  実写真（較正後）', '{r}/{rn}', '火・煙の検出。ただし火なしの誤警報は {f}/{fn}'),
  strip='すべて事前登録・全試行公開・シミュレーション（実機なし）'),
 'en': dict(
  title='RescueMind', sub='Advice may only tighten: a relief robot that checks before it delivers',
  prob_h='Problem', prob='In a disaster, the inventory and the scene disagree, and hazards hide',
  chips=[('Inventory ≠ reality', RED), ('Hazards hide', ORANGE), ('Advice may be wrong', PURPLE)],
  imgcap='Gazebo real render (overview + onboard cam)', solve='So: check, and stop if unsure',
  mid_h='Three ideas, each building on the last',
  i1='Check on site, stop if unsure', i1d='Approve only if the answer-letter probabilities of every question agree; doubt = refuse.',
  i2='Look again from the side', i2d='Move 0.4 m sideways and re-shoot to catch a small fire missed from the front.',
  i3='Untrusted inputs may only tighten',
  i3d='Memory, other robots, operator words and the inventory are "advice": they may reorder visits or tighten a threshold, never remove a check.',
  front='front', side='side 0.4 m', ph='fire probability  0.002 front → 0.82 side', appr='approve', refu='refuse',
  q1='Q1', q2='Q2 (permuted)', qh='fire / smoke', concept='schematic', thr='threshold',
  ins=['memory', 'other robots', 'operator words', 'inventory'], adv='advice', adv2='proposal only',
  ok_='reorder visits, tighten thresholds', bad='skip a check (forbidden)',
  naive='naive follower: unsafe {a}/{n}', ours='ours: unsafe {b}/{n}',
  res_h='Key results (pre-registered)', pend='pending',
  L=('L  24 unseen layouts', '{ok}/{n}', 'as expected; unsafe deliveries {u}'),
  G=('G  look again', '{b}/{n} → {c}/{n}', 'deliveries despite a fire (p={p:.3f})'),
  H=('H  memory across missions', '{t0} → {t2} s', 'mission time over {np} relocated runs. Unsafe: no memory {m0}/{n}, ours {b}/{n}, naive memory {a}/{n} (by design)'),
  A=('A  adversarial advice', '{an}/{nn} → {ao}/{no}', 'unsafe deliveries: advice-following baseline → ours'),
  A_p='unsafe deliveries: advice-following baseline vs ours (closed loop)',
  X=('X  realistic depot (4 bays)', '{m0:.1f} → {m2:.1f} bays', 'visited, no memory → memory. Unsafe in fire/smoke worlds {k}/{hn}'),
  X_p='verified memory vs none in a four-bay depot (closed loop)',
  P2=('P2  real photos (calibrated)', '{r}/{rn}', 'fire/smoke found. False alarms on no-fire photos {f}/{fn}'),
  strip='All pre-registered | every trial published | simulation only (no real robot)'),
}


def _tokens(para):
    """Latin words (with their trailing space) stay whole; every CJK character is its own token."""
    toks, cur = [], ''
    for ch in para:
        if ord(ch) < 0x2E80 and ch != ' ':
            cur += ch
        elif ch == ' ':
            toks.append(cur + ' '); cur = ''
        else:
            if cur:
                toks.append(cur); cur = ''
            toks.append(ch)
    if cur:
        toks.append(cur)
    return toks


def wrap(d, text, f, maxw):
    out = []
    for para in text.split('\n'):
        cur = ''
        for tk in _tokens(para):
            trial = cur + tk
            # a closing mark never starts a line (kinsoku); a trailing space does not count
            if d.textlength(trial.rstrip(), font=f) > maxw and cur and tk not in '。、）」':
                out.append(cur.rstrip()); cur = tk
            else:
                cur = trial
        out.append(cur.rstrip())
    return out


def paras(d, xy, text, f, maxw, fill=INK, lh=1.35, tag=''):
    x, y = xy
    for ln in wrap(d, text, f, maxw):
        if d.textlength(ln, font=f) > maxw + 1:
            WARN.append(f'overflow {tag}: {ln!r}')
        d.text((x, y), ln, font=f, fill=fill)
        y += int(f.size * lh)
    return y


def fit(d, text, size, maxw, bold=True, lo=14):
    """Largest font <= size whose rendering of `text` fits in maxw (one line)."""
    while size > lo and d.textlength(text, font=font(size, bold)) > maxw:
        size -= 1
    if d.textlength(text, font=font(size, bold)) > maxw:
        WARN.append(f'cannot fit {text!r} in {maxw}px')
    return font(size, bold)


def card(d, box, fill=CARD, outline=None, r=22, w=4):
    d.rounded_rectangle(box, r, fill=fill, outline=outline, width=w)


def chip(d, xy, text, f, fg, bg, limit=None):
    w = d.textlength(text, font=f) + 36
    if limit is not None and xy[0] + w > limit + 1:
        WARN.append(f'chip overflow {text!r}: {xy[0] + w:.0f} > {limit}')
    d.rounded_rectangle((xy[0], xy[1], xy[0] + w, xy[1] + f.size + 20), 16, fill=bg)
    d.text((xy[0] + 18, xy[1] + 8), text, font=f, fill=fg)
    return xy[0] + w


def arrow(d, x0, x1, y, col=INK, w=5):
    d.line((x0, y, x1 - 8, y), fill=col, width=w)
    d.polygon([(x1, y), (x1 - 18, y - 11), (x1 - 18, y + 11)], fill=col)


def down(d, x, y0, y1, col=MUTED):
    d.line((x, y0, x, y1 - 6), fill=col, width=5)
    d.polygon([(x, y1), (x - 12, y1 - 16), (x + 12, y1 - 16)], fill=col)


def circled(d, cx, cy, n, col):
    d.ellipse((cx - 24, cy - 24, cx + 24, cy + 24), fill=col)
    d.text((cx, cy), str(n), font=font(30, True), fill='white', anchor='mm')


def cross(d, x, y, col=RED, s=13):
    d.line((x - s, y - s, x + s, y + s), fill=col, width=6)
    d.line((x - s, y + s, x + s, y - s), fill=col, width=6)


def build(lang):
    t, n = T[lang], numbers()
    im = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(im)
    # header
    tf = font(66, True)
    d.text((50, 22), t['title'], font=tf, fill=INK)
    sx = 50 + d.textlength(t['title'], font=tf) + 30
    d.text((sx, 52), t['sub'], font=fit(d, t['sub'], 36, W - 40 - sx, bold=False), fill=MUTED)
    top, bot = 112, 1020
    # ---- left: problem
    lx0, lx1 = 40, 500
    card(d, (lx0, top, lx1, bot), outline=BLUE)
    d.text((lx0 + 28, top + 20), t['prob_h'], font=font(34, True), fill=BLUE)
    iw_ = lx1 - lx0 - 56
    y = paras(d, (lx0 + 28, top + 74), t['prob'], font(38, True), iw_, tag='prob', lh=1.3)
    hero = Image.open(FIG / 'hero_gazebo.png').convert('RGB')
    hw_ = int(iw_ * (0.66 if 'new' in t else 1.0))      # smaller picture: the bottom of the panel carries the new I-23 / I-24 results
    hh = int(hw_ * hero.height / hero.width)
    y += 14 if 'new' in t else 18
    im.paste(hero.resize((hw_, hh), Image.LANCZOS), (lx0 + 28, y))
    d.rectangle((lx0 + 28, y, lx0 + 28 + hw_, y + hh), outline=(180, 185, 190), width=2)
    y += hh + 10
    y = paras(d, (lx0 + 28, y), t['imgcap'], font(21), iw_, MUTED, 1.3, tag='imgcap') + 16
    f = font(30, True)
    x = lx0 + 28
    for text, col in t['chips']:  # flow layout: wrap to the next line instead of overflowing
        w = d.textlength(text, font=f) + 36
        if x + w > lx1 - 28 and x > lx0 + 28:
            x, y = lx0 + 28, y + 68
        x = chip(d, (x, y), text, f, col, PALE[col], limit=lx1 - 28) + 12
    y += 70 if 'new' in t else 82
    arrow(d, lx0 + 28, lx0 + 74, y + 18, GREEN)
    d.text((lx0 + 90, y), t['solve'], font=fit(d, t['solve'], 28, lx1 - 28 - (lx0 + 90)), fill=GREEN)
    if y + 40 > bot:
        WARN.append(f'left column overflows: {y + 40} > {bot}')
    sf, cf_ = advice_numbers.smt_facts(), advice_numbers.credit_facts()    # new in I-23 / I-24 (machine check, advice credit)
    if sf and 'new' in t:     # Japanese version only (the English card has no room)
        by0 = y + 46
        card(d, (lx0 + 20, by0, lx1 - 20, bot - 14), fill=PALE[PURPLE], outline=PURPLE, r=16, w=3)
        d.text((lx0 + 36, by0 + 8), t['new_h'], font=font(24, True), fill=PURPLE)
        body = t['new'].format(u=sf['unsat'], c=f"{sf['cases']:,}", d=sf['disagreements'], k=sf['caught'], m=sf['mutants'],
                               ln=round(cf_['liar_no']) if cf_ else '-', ly=round(cf_['liar_yes']) if cf_ else '-',
                               pend=('。' + '・'.join(k for k, v in advice_numbers.pending_studies().items() if not v) + '：結果待ち') if not all(advice_numbers.pending_studies().values()) else '')
        yy = paras(d, (lx0 + 36, by0 + 40), body, font(21), lx1 - lx0 - 72, INK, 1.2, tag='new')
        if yy > bot - 14:
            WARN.append(f'new-results card overflows: {yy} > {bot - 14}')
    # ---- centre: three ideas as a chain
    cx0, cx1 = 525, 1340
    d.text((cx0, top - 4), t['mid_h'], font=fit(d, t['mid_h'], 34, cx1 - cx0), fill=INK)
    hs, gap = [196, 232, 386], 24
    ys = [top + 46]
    for k in (0, 1):
        ys.append(ys[-1] + hs[k] + gap)
    if ys[2] + hs[2] > bot + 2:
        WARN.append(f'centre column overflows: {ys[2] + hs[2]} > {bot}')
    cols = [GREEN, ORANGE, BLUE]
    heads = [t['i1'], t['i2'], t['i3']]
    descs = [t['i1d'], t['i2d'], t['i3d']]
    vx = cx0 + 380  # x of the small diagrams in cards 1 and 2
    f19 = font(19)
    cf = font(21, True)
    d1w = (max(d.textlength(t[k], font=f19) for k in ('q1', 'q2', 'qh')) + 10 + 112 + 14 + 50
           + max(d.textlength(t['appr'], font=cf), d.textlength(t['refu'], font=cf)) + 36)
    vx1 = min(vx, int(cx1 - 18 - d1w))  # idea-1 diagram x (right-aligned, the text column shrinks if needed)
    for i in range(3):
        y0 = ys[i]
        card(d, (cx0, y0, cx1, y0 + hs[i]), fill=(255, 255, 255), outline=cols[i])
        circled(d, cx0 + 42, y0 + 40, i + 1, cols[i])
        d.text((cx0 + 84, y0 + 16), heads[i], font=fit(d, heads[i], 36, cx1 - cx0 - 110), fill=cols[i])
        if i < 2:
            paras(d, (cx0 + 26, y0 + 76), descs[i], font(22), (vx1 if i == 0 else vx) - cx0 - 50, INK, 1.3, tag=f'desc{i}')
            down(d, (cx0 + cx1) // 2, y0 + hs[i] + 2, y0 + hs[i] + gap - 2)
        else:
            paras(d, (cx0 + 26, y0 + 76), descs[i], font(23), cx1 - cx0 - 52, INK, 1.3, tag='desc2')
    # idea 1 visual: probability bars with threshold
    y0 = ys[0] + 64
    f = font(19)
    bars = [(t['q1'], 0.9, GREEN), (t['q2'], 0.86, GREEN), (t['qh'], 0.08, RED)]
    lw_ = max(d.textlength(b[0], font=f) for b in bars) + 10
    bx, bw = vx1 + lw_, 112
    for k, (lab, v, c) in enumerate(bars):
        yy = y0 + k * 31
        d.text((vx1, yy), lab, font=f, fill=MUTED)
        d.rectangle((bx, yy + 5, bx + bw, yy + 22), fill=(232, 232, 230))
        d.rectangle((bx, yy + 5, bx + int(bw * v), yy + 22), fill=c)
    d.line((bx + bw // 2, y0 - 4, bx + bw // 2, y0 + 94), fill=INK, width=2)
    d.text((bx + bw // 2, y0 + 96), t['thr'], font=font(16), fill=MUTED, anchor='ma')
    ax = bx + bw + 14
    arrow(d, ax, ax + 38, y0 + 44)
    cw = max(d.textlength(t['appr'], font=cf), d.textlength(t['refu'], font=cf)) + 36
    cxa = ax + 50
    if cxa + cw > cx1 - 12:
        WARN.append(f'idea-1 diagram overflows: {cxa + cw:.0f} > {cx1 - 12}')
    chip(d, (cxa, y0), t['appr'], cf, 'white', GREEN)
    chip(d, (cxa, y0 + 56), t['refu'], cf, 'white', RED)
    d.text((cx1 - 20, ys[0] + 20), t['concept'], font=font(16), fill=MUTED, anchor='ra')
    # idea 2 visual: the front/side pair from the paper figure
    pic = Image.open(ROOT / 'docs/report/figures/fig_lookaround.png').convert('RGB')
    a_, b_ = pic.crop((0, 34, 502, 409)), pic.crop((520, 34, 1022, 409))
    iw, ih = 160, 119
    y0 = ys[1] + 62
    xs2 = (vx, vx + iw + 56)
    for img, xx, lab, ok, col in ((a_, xs2[0], t['front'], t['appr'], GREEN), (b_, xs2[1], t['side'], t['refu'], RED)):
        im.paste(img.resize((iw, ih), Image.LANCZOS), (xx, y0))
        d.rectangle((xx, y0, xx + iw, y0 + ih), outline=col, width=4)
        chip(d, (xx + 4, y0 + 4), lab, font(17, True), INK, (255, 255, 255), limit=xx + iw)
        d.rounded_rectangle((xx + iw - 92, y0 + ih - 34, xx + iw - 4, y0 + ih - 4), 10, fill=col)
        d.text((xx + iw - 48, y0 + ih - 19), ok, font=font(20, True), fill='white', anchor='mm')
    arrow(d, xs2[0] + iw + 8, xs2[1] - 8, y0 + ih // 2)
    d.text((vx, y0 + ih + 10), t['ph'], font=fit(d, t['ph'], 22, cx1 - 16 - vx), fill=RED)
    # idea 3 visual: untrusted inputs -> advice -> may reorder / tighten, never remove a check; naive vs ours
    y0 = ys[2] + 146
    f = font(19, True)
    ins = t['ins']
    w1 = max(d.textlength(s, font=f) for s in ins) + 36
    x1 = cx0 + 26
    rows = []
    for k, s in enumerate(ins):
        yy = y0 + k * 42
        d.rounded_rectangle((x1, yy, x1 + w1, yy + 36), 14, fill=PALE[PURPLE])
        d.text((x1 + w1 / 2, yy + 18), s, font=f, fill=PURPLE, anchor='mm')
        rows.append(yy + 18)
    bx0 = x1 + w1 + 36
    af_ = font(26, True)
    bw_ = max(d.textlength(t['adv'], font=af_), d.textlength(t['adv2'], font=font(19))) + 36
    d.rounded_rectangle((bx0, y0, bx0 + bw_, y0 + 162), 20, fill=(255, 255, 255), outline=PURPLE, width=4)
    for yy in rows:
        arrow(d, x1 + w1 + 4, bx0 - 2, yy, MUTED, 3)
    d.text((bx0 + bw_ / 2, y0 + 66), t['adv'], font=af_, fill=PURPLE, anchor='mm')
    d.text((bx0 + bw_ / 2, y0 + 100), t['adv2'], font=font(19), fill=MUTED, anchor='mm')
    ox = bx0 + bw_ + 40
    ow = cx1 - 18 - ox
    # allowed (green) and forbidden (red, crossed)
    arrow(d, bx0 + bw_ + 4, ox - 2, y0 + 40, GREEN, 4)
    card(d, (ox, y0, ox + ow, y0 + 76), fill=PALE[GREEN], outline=GREEN, r=16, w=3)
    paras(d, (ox + 14, y0 + 8), t['ok_'], font(21, True), ow - 28, GREEN, 1.25, tag='ok_')
    arrow(d, bx0 + bw_ + 4, ox - 2, y0 + 122, RED, 4)
    card(d, (ox, y0 + 86, ox + ow, y0 + 162), fill=PALE[RED], outline=RED, r=16, w=3)
    paras(d, (ox + 14, y0 + 94), t['bad'], font(21, True), ow - 70, RED, 1.25, tag='bad')
    cross(d, ox + ow - 34, y0 + 124)
    # contrast row: naive follower vs ours (study H, unsafe deliveries; the naive memory skips checks by design)
    yc = ys[2] + hs[2] - 62
    if n['H']:
        hn = n['H']
        half = (cx1 - cx0 - 52 - 16) // 2
        for k, (key, col, val) in enumerate((('naive', RED, hn['naive']), ('ours', GREEN, hn['ours']))):
            xx = cx0 + 26 + k * (half + 16)
            s = t[key].format(a=val, b=val, n=hn['n'])
            card(d, (xx, yc, xx + half, yc + 46), fill=PALE[col], outline=col, r=14, w=3)
            d.text((xx + half / 2, yc + 23), s, font=fit(d, s, 23, half - 24), fill=col, anchor='mm')
    # ---- right: results
    rx0, rx1 = 1365, 1960
    d.text((rx0, top - 4), t['res_h'], font=fit(d, t['res_h'], 34, rx1 - rx0), fill=INK)
    maxw = rx1 - rx0 - 52
    items = []
    if n['L']:
        items.append((GREEN, t['L'][0], t['L'][1].format(ok=n['L'][0], n=n['L'][1]), t['L'][2].format(u=n['L'][2]), False))
    if n['G']:
        items.append((ORANGE, t['G'][0], t['G'][1].format(b=n['G'][0], c=n['G'][1], n=n['G'][2]), t['G'][2].format(p=n['G'][3]), False))
    if n['H']:
        hn = n['H']
        items.append((BLUE, t['H'][0], t['H'][1].format(t0=hn['t0'], t2=hn['t2']),
                      t['H'][2].format(np=hn['npair'], m0=hn['m0'], n=hn['n'], b=hn['ours'], a=hn['naive']), False))
    if n['A']:
        a = n['A']
        items.append((BLUE, t['A'][0], t['A'][1].format(an=a[0], nn=a[1], ao=a[2], no=a[3]), t['A'][2], False))
    else:
        items.append((BLUE, t['A'][0], t['pend'], t['A_p'], True))
    if n['X']:
        x = n['X']
        items.append((PURPLE, t['X'][0], t['X'][1].format(m0=x[0], m2=x[1]), t['X'][2].format(k=x[2], hn=x[3]), False))
    else:
        items.append((PURPLE, t['X'][0], t['pend'], t['X_p'], True))
    if n['P2']:
        p = n['P2']
        items.append((ORANGE, t['P2'][0], t['P2'][1].format(r=p[0], rn=p[1]), t['P2'][2].format(f=p[2], fn=p[3]), False))
    gap_r = 8
    y0 = top + 46
    sf = font(20)
    for c, name, big, small, pending in items:
        nl = len(wrap(d, small, sf, maxw))
        ch = 8 + 30 + 52 + int(20 * 1.25) * nl + 10
        fill, col = ((246, 246, 244), (150, 155, 162)) if pending else ((255, 255, 255), c)
        card(d, (rx0, y0, rx1, y0 + ch), fill=fill, outline=col, w=3)
        d.rectangle((rx0 + 2, y0 + 18, rx0 + 12, y0 + ch - 18), fill=col)
        d.text((rx0 + 28, y0 + 8), name, font=fit(d, name, 23, maxw), fill=col)
        if pending:
            chip(d, (rx0 + 28, y0 + 40), big, font(26, True), MUTED, (232, 232, 230))
        else:
            d.text((rx0 + 28, y0 + 38), big, font=fit(d, big, 40, maxw), fill=INK)
        paras(d, (rx0 + 28, y0 + 90), small, sf, maxw, MUTED, 1.25, tag=f'res {name}')
        y0 += ch + gap_r
    if y0 - gap_r > bot + 2:
        WARN.append(f'right column overflows: {y0 - gap_r} > {bot}')
    print(lang, 'right column ends at', y0 - gap_r, '(limit', bot, ')')
    # ---- bottom strip
    d.rounded_rectangle((40, 1040, W - 40, 1105), 18, fill=INK)
    d.text((W // 2, 1073), t['strip'], font=fit(d, t['strip'], 36, W - 140), fill='white', anchor='mm')
    return im


def main():
    out = ROOT / 'docs/figures'
    for lang in ('ja', 'en'):
        p = out / f'graphical_abstract_{lang}.png'
        build(lang).save(p, optimize=True)
        print('wrote', p)
    for w in WARN:
        print('WARNING', w)


if __name__ == '__main__':
    main()
