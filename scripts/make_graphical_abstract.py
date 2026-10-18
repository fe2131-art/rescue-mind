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
    wf, vf, pm = advice_numbers.w_facts(), advice_numbers.v_facts(), advice_numbers.pooled_memory()
    n['W'] = wf    # study W (look-around on 150 new worlds), study V (model prediction, memory safety), pooled H+V
    n['V'] = (vf, pm) if vf and pm else None
    return n


T = {
 'ja': dict(
  title='RescueMind', sub='助言は「厳しくする」ことしかできない災害物資ロボット',
  prob_h='問題', prob='災害時、\n在庫表と現場は違い、\n危険は隠れる',
  chips=[('在庫表 ≠ 現場', RED), ('危険は見えにくい', ORANGE), ('助言も当てにならない', PURPLE)],
  imgcap='Gazebo実レンダリング（俯瞰＋搭載カメラ）', solve='だから、確かめ、迷えば止まる',
  new_h='新：機械検証・インターロック・信用枠',
  new=['I-23 機械検証：z3 {u}件、{c}件で不一致{d}、バグ{k}/{m}検出', 'I-22 インターロック：Gazebo実走{il}件で通過',
       'I-24 信用枠：嘘つきの代償 +{ln}→+{ly}秒（合成モデルの記述。閉ループは未確認）'],
  il_none='I-22 インターロック：Gazebo確認は未了',
  mid_h='3つの工夫（上から順に積み上げる）',
  i1='その場で確かめ、迷えば止まる', i1d='選択式の質問と火の質問の確率を読み、全部そろったときだけ許可。迷えば拒否。',
  i2='横から見直す', i2d='正面で見落とす小さな火を、0.4 m 横へ動いて撮り直して見つける。',
  i3='信頼できない入力は「締める」だけ',
  i3d='記憶・他のロボット・依頼文の言葉・在庫表は「助言」。拠点の順序を変えるか判断を厳しくするだけで、確認は決して省けない。',
  front='正面', side='横 0.4 m', ph='火の確率  正面 0.002 → 横 0.82', appr='許可', refu='拒否',
  q1='質問1', q2='質問2（並べ替え）', qh='火・煙', concept='概念図', thr='閾値',
  ins=['記憶', '他のロボット', '依頼文の言葉', '在庫表'], adv='助言', adv2='提案だけ',
  ok_='順序を変える・判断を厳しくする', bad='確認を省く（禁止）',
  naive='評価H の記憶（確認を省く設計）\n危険な配達 {a}/{n}', ours='評価H の検証つき記憶\n危険な配達 {b}/{n}（記憶なし {m0}/{n}）',
  res_h='主な結果（事前登録・実測）', pend='結果待ち',
  L=('L  未知の配置24通り', '{ok}/{n}', '期待どおり・危険な配達 {u}'),
  G=('G  横から見直し', '{b}/{n} → {c}/{n}', '火があるのに配達した数（p={p:.3f}）'),
  H=('H  記憶をまたぐ出動', '{t0}→{t2} 秒', '移されたまま続く{np}出動の所要時間（中央値）。危険な配達は下の図'),
  A=('A  悪意ある助言', '{an}/{nn} → {ao}/{no}', '危険な配達：助言どおりに動く方式 → 本方式'),
  X=('X  現実的な倉庫（4拠点）', '{m0:.1f} → {m2:.1f} 拠点', '記憶なし → あり（訪問数）。火・煙の世界の危険な配達 {k}/{hn}'),
  W=('W  見回し（新しい{n}世界）', '{fr}/{n} → {la}/{n}', '小さく隠れた火の見逃し：正面のみ → 見回し（95%CI上限 {up:.1f}%）。横からしか見えない{sn}世界では {sk}/{sn}{allm}', '見逃し'),
  V=('V  記憶：時間の予測は成立', '−{d:.0f} 秒（予測 {lo:.0f}〜{hi:.0f} 秒の内）', 'H+V計{n}出動の危険な配達：記憶なし {m0}・検証つき記憶 {m2}・素朴な記憶 {m1}。差は示せず、原因は検出力と確認の誤り1件', '記憶の安全：不成立'),
  PEND=('結果待ち（登録済み・未実行）', {'A': '悪意ある助言', 'S': '画像内の文字', 'X': '4拠点の倉庫', 'XD': '倉庫の画像', 'B': '信用枠', 'IF': '依頼文', 'Q': '実写真'}, '結果待ち'),
  allm='（残る見逃しの全て）', nonem='',
  P2=('P2  実写真（較正後）', '{r}/{rn}', '火・煙の検出。ただし火なしの誤警報は {f}/{fn}'),
  strip='すべて事前登録・全試行公開・シミュレーション（実機なし）'),
 'en': dict(
  title='RescueMind', sub='Advice may only tighten: a relief robot that checks before it delivers',
  prob_h='Problem', prob='In a disaster, the inventory and the scene disagree, and hazards hide',
  chips=[('Inventory ≠ reality', RED), ('Hazards hide', ORANGE), ('Advice may be wrong', PURPLE)],
  imgcap='Gazebo real render (overview + onboard cam)', solve='So: check, and stop if unsure',
  new_h='New: machine check, interlock, credit',
  new=['I-23 machine check: z3 {u} proofs, {c} cases, {d} mismatches, bugs caught {k}/{m}', 'I-22 interlock: passed {il} live Gazebo missions',
       'I-24 credit: a liar costs +{ln} → +{ly} s (descriptive synthetic model; closed loop not yet checked)'],
  il_none='I-22 interlock: Gazebo check not done yet',
  mid_h='Three ideas, each building on the last',
  i1='Check on site, stop if unsure', i1d='Approve only if the answer-letter probabilities of every question agree; doubt = refuse.',
  i2='Look again from the side', i2d='Move 0.4 m sideways and re-shoot to catch a small fire missed from the front.',
  i3='Untrusted inputs may only tighten',
  i3d='Memory, other robots, operator words and the inventory are "advice": they may reorder visits or tighten a threshold, never remove a check.',
  front='front', side='side 0.4 m', ph='fire probability  0.002 front → 0.82 side', appr='approve', refu='refuse',
  q1='Q1', q2='Q2 (permuted)', qh='fire / smoke', concept='schematic', thr='threshold',
  ins=['memory', 'other robots', 'operator words', 'inventory'], adv='advice', adv2='proposal only',
  ok_='reorder visits, tighten thresholds', bad='skip a check (forbidden)',
  naive='Study H, naive memory (skips checks)\nunsafe {a}/{n}', ours='Study H, verified memory\nunsafe {b}/{n} (no memory {m0}/{n})',
  res_h='Key results (pre-registered)', pend='pending',
  L=('L  24 unseen layouts', '{ok}/{n}', 'as expected; unsafe deliveries {u}'),
  G=('G  look again', '{b}/{n} → {c}/{n}', 'deliveries despite a fire (p={p:.3f})'),
  H=('H  memory across missions', '{t0} → {t2} s', 'median mission time over {np} relocated runs. Unsafe deliveries: see below'),
  A=('A  adversarial advice', '{an}/{nn} → {ao}/{no}', 'unsafe deliveries: advice-following baseline → ours'),
  X=('X  realistic depot (4 bays)', '{m0:.1f} → {m2:.1f} bays', 'visited, no memory → memory. Unsafe in fire/smoke worlds {k}/{hn}'),
  W=('W  look-around on {n} new worlds', '{fr}/{n} → {la}/{n}', 'misses of small hidden fires, front-only → look-around (95% CI upper {up:.1f}%). Side-only worlds: {sk}/{sn}{allm}', 'misses'),
  V=('V  memory: timing held', '−{d:.0f} s (predicted {lo:.0f}-{hi:.0f} s)', 'Unsafe, H+V over {n} missions: no memory {m0}, verified {m2}, naive {m1}. No difference shown (low power, one check error)', 'safety: not supported'),
  PEND=('Pending (registered, not yet run)', {'A': 'adversarial advice', 'S': 'scene text', 'X': '4-bay depot', 'XD': 'depot images', 'B': 'credit', 'IF': 'request text', 'Q': 'real photos'}, 'pending'),
  allm=' (all remaining misses)', nonem='',
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
    y = paras(d, (lx0 + 28, top + 64), t['prob'], font(33, True), iw_, tag='prob', lh=1.25)
    hero = Image.open(FIG / 'hero_gazebo.png').convert('RGB')
    hw_ = int(iw_ * 0.5)      # smaller picture: the bottom of the panel carries the new I-23 / I-24 results
    hh = int(hw_ * hero.height / hero.width)
    y += 14 if 'new' in t else 18
    im.paste(hero.resize((hw_, hh), Image.LANCZOS), (lx0 + 28, y))
    d.rectangle((lx0 + 28, y, lx0 + 28 + hw_, y + hh), outline=(180, 185, 190), width=2)
    y += hh + 10
    y = paras(d, (lx0 + 28, y), t['imgcap'], font(21), iw_, MUTED, 1.3, tag='imgcap') + 16
    f = font(26, True)
    x = lx0 + 28
    for text, col in t['chips']:  # flow layout: wrap to the next line instead of overflowing
        w = d.textlength(text, font=f) + 36
        if x + w > lx1 - 28 and x > lx0 + 28:
            x, y = lx0 + 28, y + 58
        x = chip(d, (x, y), text, f, col, PALE[col], limit=lx1 - 28) + 12
    y += 62
    arrow(d, lx0 + 28, lx0 + 74, y + 18, GREEN)
    d.text((lx0 + 90, y), t['solve'], font=fit(d, t['solve'], 28, lx1 - 28 - (lx0 + 90)), fill=GREEN)
    if y + 40 > bot:
        WARN.append(f'left column overflows: {y + 40} > {bot}')
    sf, cf_, ilc = advice_numbers.smt_facts(), advice_numbers.credit_facts(), advice_numbers.interlock_check()   # I-23 machine check, I-24 credit model, I-22 interlock check
    if sf:
        by0 = y + 44
        card(d, (lx0 + 20, by0, lx1 - 20, bot - 12), fill=PALE[PURPLE], outline=PURPLE, r=16, w=3)
        d.text((lx0 + 36, by0 + 6), t['new_h'], font=fit(d, t['new_h'], 24, lx1 - lx0 - 72), fill=PURPLE)
        yy = by0 + 38
        for k, line in enumerate(t['new']):
            if k == 1 and not ilc:
                line = t['il_none']
            body = line.format(u=sf['unsat'], c=f"{sf['cases']:,}", d=sf['disagreements'], k=sf['caught'], m=sf['mutants'],
                               il=ilc['missions'] if ilc else '-', ln=round(cf_['liar_no']) if cf_ else '-', ly=round(cf_['liar_yes']) if cf_ else '-')
            d.ellipse((lx0 + 38, yy + 9, lx0 + 48, yy + 19), fill=PURPLE)
            yy = paras(d, (lx0 + 58, yy), body, font(20), lx1 - lx0 - 100, INK, 1.2, tag='new') + 4
        if yy > bot - 12:
            WARN.append(f'new-results card overflows: {yy} > {bot - 12}')
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
    yc = ys[2] + hs[2] - 66
    if n['H']:
        hn = n['H']
        half = (cx1 - cx0 - 52 - 16) // 2
        for k, (key, col, val) in enumerate((('naive', RED, hn['naive']), ('ours', GREEN, hn['ours']))):
            xx = cx0 + 26 + k * (half + 16)
            s = t[key].format(a=val, b=val, n=hn['n'], m0=hn['m0'])
            card(d, (xx, yc, xx + half, yc + 54), fill=PALE[col], outline=col, r=14, w=3)
            for li, ln_ in enumerate(s.split('\n')):
                d.text((xx + half / 2, yc + 14 + 25 * li), ln_, font=fit(d, ln_, 20, half - 16), fill=col, anchor='mm')
    # ---- right: results
    rx0, rx1 = 1365, 1960
    d.text((rx0, top - 4), t['res_h'], font=fit(d, t['res_h'], 34, rx1 - rx0), fill=INK)
    maxw = rx1 - rx0 - 52
    items = []          # (colour, name, big, small, badge or None); a study without a result file is not drawn here but listed in the pending card
    if n['L']:
        items.append((GREEN, t['L'][0], t['L'][1].format(ok=n['L'][0], n=n['L'][1]), t['L'][2].format(u=n['L'][2]), None))
    if n['G']:
        items.append((ORANGE, t['G'][0], t['G'][1].format(b=n['G'][0], c=n['G'][1], n=n['G'][2]), t['G'][2].format(p=n['G'][3]), None))
    if n['W']:
        w = n['W']
        so, la = w['so_la'], w['la']
        items.append((ORANGE, t['W'][0].format(n=w['n']), t['W'][1].format(fr=w['front']['k'], la=la['k'], n=w['n']),
                      t['W'][2].format(up=100 * la['ci95'][1], sk=so['k'], sn=so['n'], allm=t['allm'] if so['k'] == la['k'] else ''), None))
    if n['H']:
        hn = n['H']
        items.append((BLUE, t['H'][0], t['H'][1].format(t0=hn['t0'], t2=hn['t2']), t['H'][2].format(np=hn['npair']), None))
    if n['V']:
        vf, pm = n['V']
        bad = not vf['memory_claim']
        items.append((BLUE, t['V'][0], t['V'][1].format(d=vf['diff'], lo=vf['pred_lo'], hi=vf['pred_hi']),
                      t['V'][2].format(n=pm['n'], m0=pm['unsafe']['M0'], m2=pm['unsafe']['M2'], m1=pm['unsafe']['M1']), (t['V'][3], RED) if bad else None))
    if n['A']:
        a = n['A']
        items.append((BLUE, t['A'][0], t['A'][1].format(an=a[0], nn=a[1], ao=a[2], no=a[3]), t['A'][2], None))
    if n['X']:
        x = n['X']
        items.append((PURPLE, t['X'][0], t['X'][1].format(m0=x[0], m2=x[1]), t['X'][2].format(k=x[2], hn=x[3]), None))
    if n['P2']:
        p = n['P2']
        items.append((ORANGE, t['P2'][0], t['P2'][1].format(r=p[0], rn=p[1]), t['P2'][2].format(f=p[2], fn=p[3]), None))
    gap_r = 7
    y0 = top + 44
    sf = font(19)
    for c, name, big, small, badge in items:
        nl = len(wrap(d, small, sf, maxw))
        nf, bf_ = fit(d, name, 22, maxw), fit(d, big, 38, maxw)
        if d.textlength(name, font=nf) + d.textlength(big, font=bf_) + 30 > maxw or badge:
            bf_ = fit(d, big, 34, maxw)
        one = (not badge) and d.textlength(name, font=nf) + d.textlength(big, font=bf_) + 30 <= maxw    # name and number share one row
        top_h = 50 if one else 84
        ch = top_h + int(19 * 1.22) * nl + 12
        card(d, (rx0, y0, rx1, y0 + ch), fill=(255, 255, 255), outline=c, w=3)
        d.rectangle((rx0 + 2, y0 + 18, rx0 + 12, y0 + ch - 18), fill=c)
        bw_ = 0
        if badge:      # a failed registered claim is a first-class item, not a footnote
            bf = font(20, True)
            bw_ = int(d.textlength(badge[0], font=bf)) + 32
            d.rounded_rectangle((rx1 - 14 - bw_, y0 + 7, rx1 - 14, y0 + 7 + 34), 12, fill=badge[1])
            d.text((rx1 - 14 - bw_ // 2, y0 + 24), badge[0], font=bf, fill='white', anchor='mm')
        if one:
            d.text((rx0 + 28, y0 + 12), name, font=nf, fill=c)
            d.text((rx1 - 20, y0 + 4), big, font=bf_, fill=INK, anchor='ra')
        else:
            d.text((rx0 + 28, y0 + 6), name, font=fit(d, name, 22, maxw - bw_ - 8), fill=c)
            d.text((rx0 + 28, y0 + 34), big, font=bf_, fill=INK)
        paras(d, (rx0 + 28, y0 + top_h), small, sf, maxw, MUTED, 1.22, tag=f'res {name}')
        y0 += ch + gap_r
    # pending studies: registered, no result file yet (they turn into cards above once a_summary.json etc. exist)
    pend = [k for k, v in advice_numbers.pending_all().items() if not v]
    if pend:
        pt = t['PEND']
        desc = '・'.join(f'{k} {pt[1][k]}' for k in pend)
        dl = wrap(d, desc, font(18), maxw)
        ch = 6 + 28 + 54 + int(18 * 1.22) * len(dl) + 8
        card(d, (rx0, y0, rx1, y0 + ch), fill=(246, 246, 244), outline=(150, 155, 162), w=3)
        d.text((rx0 + 28, y0 + 6), pt[0], font=fit(d, pt[0], 22, maxw), fill=MUTED)
        xx = rx0 + 28
        for k in pend:
            xx = chip(d, (xx, y0 + 36), k, font(22, True), MUTED, (232, 232, 230), limit=rx1 - 14) + 8
        paras(d, (rx0 + 28, y0 + 90), desc, font(18), maxw, MUTED, 1.22, tag='pending')
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
