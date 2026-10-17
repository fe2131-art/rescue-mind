#!/usr/bin/env python3
"""I-18: render the one-page operator report of a run (PNG + PDF) from its mission.json / stack_result.json.

  python3 scripts/make_operator_report.py outputs/runs/<run_id>            # -> <run>/operator_report.{png,pdf}
  python3 scripts/make_operator_report.py outputs/runs/<run_id> --out docs/figures/operator_report_example.png

The text comes from rescuemind.operator_report (pure functions over the robot's own logs).
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from rescuemind.operator_report import build, STATION_JA, SIDE_JA, SHORT_JA  # noqa: E402

FONT_R = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
FONT_B = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
W, H = 1654, 1169                     # A4 landscape at 140 dpi
BG, INK, MUTED, LINE = (255, 255, 255), (25, 30, 40), (95, 105, 120), (215, 220, 228)
COL = {'good': (46, 125, 80), 'bad': (178, 38, 30), 'warn': (196, 110, 20)}
_fc = {}


def font(size, bold=False):
    k = (size, bold)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(FONT_B if bold else FONT_R, size)
    return _fc[k]


def wrap(text, size, width, bold=False):
    f, lines, cur = font(size, bold), [], ''
    for ch in text:
        if f.getlength(cur + ch) > width and ch not in '）」』。、・)':   # kinsoku: never start a line with these
            lines.append(cur); cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def para(d, xy, text, size, width, fill=INK, bold=False, gap=1.35, max_lines=None):
    x, y = xy
    for ln in wrap(text, size, width, bold)[:max_lines]:
        d.text((x, y), ln, font=font(size, bold), fill=fill)
        y += int(size * gap)
    return y


def render(run_dir: Path, out_png: Path):
    m = json.loads((run_dir / 'mission.json').read_text(encoding='utf8'))
    r = json.loads((run_dir / 'stack_result.json').read_text(encoding='utf8')) if (run_dir / 'stack_result.json').is_file() else {}
    rep = build(m, r)
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)
    # header
    d.rectangle((0, 0, W, 86), fill=(18, 28, 46))
    d.text((40, 20), 'RescueMind  現場報告', font=font(36, True), fill=(255, 255, 255))
    d.text((W - 40, 30), f"記録ID {rep['run_id']}　（ロボット自身の記録から自動作成）", font=font(20), fill=(200, 210, 225), anchor='ra')
    # request + verdict
    y = 110
    d.text((40, y), '依頼', font=font(22, True), fill=MUTED)
    d.text((120, y - 2), f"「{rep['instruction']}」 → 解釈：{rep['interpretation']}", font=font(26, True), fill=INK)
    y += 50
    c = COL[rep['colour']]
    d.rounded_rectangle((40, y, W - 40, y + 70), radius=14, fill=c)
    d.text((W // 2, y + 35), rep['headline'], font=font(32, True), fill=(255, 255, 255), anchor='mm')
    y += 96
    # images of every check
    chk = [c for c in rep['checks'] if c.get('image') and (run_dir / c['image']).is_file()]
    if chk:
        n = len(chk)
        tw = min(500, (W - 80 - 20 * (n - 1)) // n)
        th = int(tw * 0.75)
        for k, c in enumerate(chk):
            x = 40 + k * (tw + 20)
            im = Image.open(run_dir / c['image']).convert('RGB').resize((tw, th))
            img.paste(im, (x, y))
            ok = c['allow']
            label = (f"{STATION_JA.get(c['station'], c['station'])}・"
                     + ('正面' if c['kind'] == 'front' else f"{SIDE_JA.get(c['side'], c['side'])}から"))
            verdict = ('火・煙なし' if c['kind'] == 'side' and ok else SHORT_JA.get(c['decision'], c['decision']) if c['kind'] == 'front'
                       else '火・煙を検知')
            d.rounded_rectangle((x, y + th - 44, x + tw, y + th), radius=0, fill=(0, 0, 0))
            d.text((x + 10, y + th - 38), f'{label}：{verdict}', font=font(21, True),
                   fill=(140, 230, 160) if ok else (255, 150, 140))
        y += th + 24
    # two columns: reasons/memory | next actions/robot words
    colw = (W - 120) // 2
    yl = yr = y
    d.text((40, yl), '何を見て、どう判断したか', font=font(24, True), fill=INK); yl += 38
    for ln in rep['reasons']:
        yl = para(d, (56, yl), '・' + ln, 21, colw - 20)
    if rep['memory']:
        yl += 10
        d.text((40, yl), '出動をまたぐ記憶（提案だけ・確認は省略しない）', font=font(22, True), fill=(70, 72, 160)); yl += 34
        for ln in rep['memory']:
            yl = para(d, (56, yl), '・' + ln, 20, colw - 20, fill=(55, 58, 120))
    if rep.get('advice'):
        yl += 10
        d.text((40, yl), '助言の扱い（助言は並べ替えと慎重化だけ・確認は省略しない）', font=font(22, True), fill=(150, 90, 30)); yl += 34
        for ln in rep['advice']:
            yl = para(d, (56, yl), '・' + ln, 20, colw - 20, fill=(120, 75, 30))
    x2 = 80 + colw
    d.text((x2, yr), '次にしてほしいこと', font=font(24, True), fill=INK); yr += 38
    for ln in rep['next']:
        yr = para(d, (x2 + 16, yr), '□ ' + ln, 22, colw - 20, bold=True)
    if rep['robot_words']:
        yr += 12
        d.text((x2, yr), f"ロボットの報告文（{rep['robot_words_where']}・正面の画像について。判断には使っていない）", font=font(20, True), fill=MUTED); yr += 30
        yr = para(d, (x2 + 16, yr), f"「{rep['robot_words']}」", 20, colw - 20, fill=MUTED)
    yb = max(yl, yr) + 24
    d.text((40, yb), rep['timeline'], font=font(21, True), fill=MUTED)
    # footer
    d.line((40, H - 64, W - 40, H - 64), fill=LINE, width=2)
    foot = ('判定は保存されたモデル出力から再計算し、シミュレータの真値軌跡で停止・到着を監査済み。'
            if rep['audited'] else '監査未完了：この記録は参考扱いにしてください。')
    d.text((40, H - 50), foot + '　シミュレーション（Gazebo）での記録です。', font=font(19), fill=MUTED)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)
    img.save(out_png.with_suffix('.pdf'), 'PDF', resolution=140)
    return out_png


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('run_dir', type=Path)
    ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    print(render(a.run_dir, a.out or a.run_dir / 'operator_report.png'))


if __name__ == '__main__':
    main()
