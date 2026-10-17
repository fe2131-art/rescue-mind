#!/usr/bin/env python3
"""I-15 principle diagram ("memory proposes, perception disposes") -> docs/figures/memory_principle_{ja,en}.png (1600x900).
Run: docker exec rm-dev rescuemind-entrypoint python3 scripts/make_memory_diagram.py"""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = Path(__file__).resolve().parent.parent / 'docs' / 'figures'
BG, INK, GREY = '#fcfcfb', '#2b2b2b', '#6b6b6b'
BLUE, GREEN, ORANGE, RED = '#2a76d2', '#1fb07a', '#ee6a3b', '#d63c3c'
JA_FONTS = ['/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']
JA_BOLD = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'

T = {
 'ja': dict(
  title='記憶は提案、判断はその場の目で', sub='出動をまたぐ記憶（I-15）：確認を減らすことは決してしない',
  h=['前回の出動で見たこと', '記憶にできること', '記憶にできないこと', 'その場で必ず確認'],
  b=[['物資の場所', '火を見た拠点と向き', '（見たものだけ。', '正解データではない）'],
     ['① 先に行く拠点を提案', '② 危険を見た拠点では', '　 閾値を厳しく、', '　 火が見えた側から見る'],
     ['確認を省く', '行かずに判断する'],
     ['正面＋左右から見る', '→ 許可 / 拒否']],
  naive='素朴な記憶（記憶を信じる）', ours='本方式（提案だけ）',
  nb=['確認を省略する', '物資が戻っていたら → 誤配達', '火が出ていたら → 火の中へ'],
  ob=['必ず現地で確認する', '遠回りは起きうる', '危険は増えない（同じ画像なら', '記憶ありの許可 ⊆ 記憶なしの許可）'],
  bad='危険', good='安全'),
 'en': dict(
  title='Memory proposes, perception disposes', sub='Cross-mission memory (I-15): it never removes a check',
  h=['What it saw last mission', 'What memory can do', 'What memory cannot do', 'Always check on site'],
  b=[['Where supplies were', 'Where fire was seen,', 'and from which side', '(observations only)'],
     ['1. Propose the first', '    station to visit', '2. Stricter threshold where', '    a hazard was seen; look', '    from the revealing side'],
     ['Skip the check', 'Decide without going'],
     ['Front + left/right views', '-> allow / refuse']],
  naive='Naive memory (trust memory)', ours='Ours (proposal only)',
  nb=['Skips the on-site check', 'Supply moved back -> wrong delivery', 'New fire -> drives into the fire'],
  ob=['Always checks on site', 'A detour can happen', 'No added risk (same images:', 'approvals with memory ⊆ without)'],
  bad='Unsafe', good='Safe'),
}


def setup_font(lang):
    if lang == 'ja':
        fm.fontManager.addfont(JA_FONTS[0]); fm.fontManager.addfont(JA_BOLD)
        return 'Noto Sans CJK JP'
    return 'DejaVu Sans'


def box(ax, x, y, w, h, col, fill=None, lw=3.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0,rounding_size=2', fc=fill or 'white', ec=col, lw=lw))


def arrow(ax, x0, x1, y, col=INK):
    ax.add_patch(FancyArrowPatch((x0, y), (x1, y), arrowstyle='-|>', mutation_scale=28, lw=3.5, color=col))


def lines(ax, x, y, ls, size, col=INK, dy=4.6, weight='normal', ha='left'):
    for i, s in enumerate(ls):
        ax.text(x, y - i * dy, s, fontsize=size, color=col, va='center', ha=ha, fontweight=weight)


def render(lang):
    t = T[lang]
    setup_font(lang)
    plt.rcParams['font.family'] = 'Noto Sans CJK JP' if lang == 'ja' else 'DejaVu Sans'
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 160); ax.set_ylim(0, 90); ax.axis('off')
    ja = lang == 'ja'
    ax.text(3, 85, t['title'], fontsize=34 if ja else 31, fontweight='bold', color=INK, va='center')
    ax.text(3, 78.6, t['sub'], fontsize=17 if ja else 15, color=GREY, va='center')
    # top row
    xs, w, y0, hh = [3, 43, 83, 123], 34, 40, 33
    cols = [BLUE, GREEN, RED, ORANGE]
    fs = 19.5 if ja else 15
    for i, (x, c) in enumerate(zip(xs, cols)):
        box(ax, x, y0, w, hh, c, fill='#fdf0f0' if i == 2 else None)
        ax.text(x + w / 2, y0 + hh - 4.2, t['h'][i], fontsize=20 if ja else 14.5, fontweight='bold', color=c, ha='center', va='center')
        ls = t['b'][i]
        if i == 2:  # big cross
            ax.text(x + w / 2, y0 + 19, '×', fontsize=70, fontweight='bold', color=RED, ha='center', va='center')
            lines(ax, x + w / 2, y0 + 8.5, ls, fs + 1, RED, dy=4.8, weight='bold', ha='center')
        elif i == 3:
            lines(ax, x + w / 2, y0 + 16, ls, fs + 1.5, INK, dy=6.5, weight='bold', ha='center')
        elif i == 0:
            lines(ax, x + 2.2, y0 + 20, ls, fs, INK, dy=5.6)
        else:
            lines(ax, x + 2.0, y0 + 21, ls, fs - (0 if ja else 0.8), INK, dy=(4.9 if ja else 4.4))
    for i in range(3):
        arrow(ax, xs[i] + w + 0.6, xs[i + 1] - 0.6, y0 + hh / 2)
    # contrast panel
    ax.add_patch(FancyBboxPatch((3, 3), 154, 31, boxstyle='round,pad=0,rounding_size=2', fc='#f3f3f1', ec='none'))
    for (x, col, title, body, tag, big) in ((6, RED, t['naive'], t['nb'], t['bad'], False), (84, GREEN, t['ours'], t['ob'], t['good'], True)):
        ax.text(x, 30.3, title, fontsize=22 if ja else 17.5, fontweight='bold', color=col, va='center')
        ax.add_patch(FancyBboxPatch((x + 55.5, 27.6), 11, 5.4, boxstyle='round,pad=0,rounding_size=1.2', fc=col, ec='none'))
        ax.text(x + 61, 30.3, tag, fontsize=16 if ja else 13.5, fontweight='bold', color='white', ha='center', va='center')
        lines(ax, x + 1, 23.2, body, 20 if ja else 16, INK, dy=5.4)
    ax.plot([81, 81], [6, 31], color='#cfcfcc', lw=2)
    fig.savefig(OUT / f'memory_principle_{lang}.png', dpi=100, facecolor=BG)
    plt.close(fig)


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    for lg in ('ja', 'en'):
        render(lg)
        print('wrote', OUT / f'memory_principle_{lg}.png')
