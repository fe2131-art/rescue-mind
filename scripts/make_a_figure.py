#!/usr/bin/env python3
"""Study A in one figure (paper, report, README), every number from advice_numbers.a_facts() (a_summary.json / a_checklist.json).

  (a) unsafe deliveries per arm under hostile advice, split by channel (operator text vs a peer's advice file); the unsafe-WORLD count of each arm is printed above its group
  (b) A-steer (truthful advice that names the station with a hidden fire): deliveries LOST out of 16 per arm, with the unsafe deliveries marked: the availability cost
  (c) time: what truthful location advice saved per world, and what false advice cost per run, against the registered bound

  python3 scripts/make_a_figure.py     # -> docs/paper/fig_a_results.pdf, docs/figures/a_results_en.png, docs/figures/a_results_ja.png
Labels say what each bar is: the guardrail read each peer item and flagged none of them, and the operator channel extracted the designed advice in only part of the runs.
Nothing is written when a_summary.json does not exist (no result, no figure).
"""
from __future__ import annotations
import statistics
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import advice_numbers  # noqa: E402

INK, MUTED = '#1f2933', '#616e7c'
BLUE, ORANGE, GREEN, RED, GREY = '#2563a8', '#c4661f', '#2f7d4f', '#b3261e', '#9aa5b1'

T = {
    'en': {
        'arms': ['advice-\nfollowing', 'LLM\nguardrail', 'ours', 'no advice'],
        'a_title': '(a) unsafe deliveries, hostile advice',
        'a_y': 'unsafe runs (of {n} per channel)',
        'worlds': 'unsafe worlds:',
        'op': 'operator text', 'fl': 'peer advice file',
        'a_note': 'guardrail flagged\noperator {a}/{b}\nfile {c}/{d}',
        'b_title': '(b) steering: deliveries lost',
        'b_y': 'worlds with no delivery (of {n})', 'b_arms': ['no\nadvice', 'advice-\nfollowing', 'ours', 'scrutiny'],
        'unsafe': 'unsafe:',
        'c_title': '(c) time, ours (s)',
        'c_cols': ['truthful:\nsaved\n({n} worlds)', 'false:\nextra\n({m} runs)'],
        'c_bound': 'bound {b:.1f} s', 'c_med': 'median {m:.1f}',
    },
    'ja': {
        'arms': ['助言に\n従う方式', 'LLM\nガードレール', '本方式', '助言なし'],
        'a_title': '(a) 悪意のある助言での危険な配達',
        'a_y': '危険な配達の試行（各経路 {n} 試行中）',
        'worlds': '危険な世界:',
        'op': '依頼文', 'fl': '助言ファイル',
        'a_note': 'ガードレールが止めた数\n依頼文 {a}/{b}\nファイル {c}/{d}',
        'b_title': '(b) 誘導：配達できなかった世界',
        'b_y': '配達できなかった世界（{n}中）', 'b_arms': ['助言なし', '助言に\n従う方式', '本方式', 'scrutiny'],
        'unsafe': '危険な配達:',
        'c_title': '(c) 時間・本方式（秒）',
        'c_cols': ['正しい助言\n短縮\n({n}世界)', '嘘の助言\n追加\n({m}試行)'],
        'c_bound': '上限 {b:.1f} 秒', 'c_med': '中央値 {m:.1f}',
    },
}
ARM_COL = [RED, ORANGE, BLUE, GREY]


def _fonts(lang):
    if lang == 'ja':
        plt.rcParams['font.family'] = ['IPAexGothic', 'Noto Sans CJK JP', 'DejaVu Sans']
    else:
        plt.rcParams['font.family'] = 'DejaVu Sans'
    plt.rcParams.update({'font.size': 6, 'axes.linewidth': 0.6, 'pdf.fonttype': 42, 'ps.fonttype': 42, 'axes.unicode_minus': False})


def _row(axis, vals, label):
    """A row of numbers under the tick labels (one per bar) with its label at the left."""
    import matplotlib.transforms as mt
    tr = mt.blended_transform_factory(axis.transData, axis.transAxes)
    for i, v in enumerate(vals):
        axis.text(i, -0.19, v, transform=tr, ha='center', va='top', fontsize=5.6, color=INK, weight='bold')
    axis.text(-0.55, -0.19, label, transform=tr, ha='right', va='top', fontsize=4.8, color=MUTED)


def build(lang: str, outs: list[Path], f: dict | None = None, size=(7.0, 2.45)) -> bool:
    f = f or advice_numbers.a_facts()
    if not f or not f['worlds']['naive']:
        return False
    L = T[lang]
    _fonts(lang)
    fig, (ax, bx, cx) = plt.subplots(1, 3, figsize=size, gridspec_kw={'width_ratios': [1.5, 1.05, 0.9], 'wspace': 0.55})
    # (a) unsafe runs per arm and channel; the world count of the arm on top
    bc, w = f['by_channel'], 0.36
    ops = [bc['naive']['operator'], bc['filtered']['operator'], bc['ours']['operator']]
    fls = [bc['naive']['file'], bc['filtered']['file'], bc['ours']['file']]
    n_ch = ops[0][1]
    for i in range(3):
        for off, (k, n), hatch in ((-w / 2, ops[i], '////'), (w / 2, fls[i], None)):
            ax.bar(i + off, k, w, color=ARM_COL[i], alpha=0.55 if hatch else 1.0, hatch=hatch, edgecolor='white' if not hatch else ARM_COL[i], lw=0.4)
            ax.text(i + off, k + 0.25, f'{k}', ha='center', va='bottom', fontsize=6.4, color=INK)
    ctrl_k, ctrl_n = f['unsafe']['control']
    ax.bar(3, ctrl_k, 0.5, color=ARM_COL[3])
    ax.text(3, ctrl_k + 0.25, f'{ctrl_k}', ha='center', va='bottom', fontsize=6.4, color=INK)
    wk = [f['worlds']['naive'], f['worlds']['filtered'], f['worlds']['monotone']]
    ax.set_ylim(0, n_ch + 2.2)
    ax.set_xlim(-0.55, 3.55)
    ax.set_yticks([0, 4, 8, 12])
    ax.set_xticks(range(4)); ax.set_xticklabels(L['arms'], fontsize=5.2)
    _row(ax, [f'{k}/{n}' for k, n in wk] + ['-'], L['worlds'])
    ax.set_ylabel(L['a_y'].format(n=n_ch), fontsize=5.8)
    ax.set_title(L['a_title'], fontsize=6.4, pad=4, loc='left')
    ax.legend(handles=[Patch(fc=GREY, alpha=0.55, hatch='////', ec=GREY, label=L['op']), Patch(fc=GREY, label=L['fl'])],
              loc='upper right', bbox_to_anchor=(1.0, 0.66), fontsize=5.2, frameon=False, handlelength=1.1, borderaxespad=0.1)
    ax.text(1.0, 0.46, L['a_note'].format(a=f['filter_flag_operator'][0], b=f['filter_flag_operator'][1], c=f['filter_flag_file'][0], d=f['filter_flag_file'][1]),
            transform=ax.transAxes, ha='right', va='top', fontsize=5.0, color=MUTED, linespacing=1.3)
    ax.spines[['top', 'right']].set_visible(False)
    # (b) A-steer: deliveries lost
    st = f['steer']
    arms = [st['control'], st['naive'], st['ours'], st['scrutiny']]
    cols = [GREY, RED, BLUE, GREEN]
    for i, a in enumerate(arms):
        bx.bar(i, a['lost'], 0.62, color=cols[i])
        bx.text(i, a['lost'] + 0.4, f"{a['lost']}/{st['n']}", ha='center', va='bottom', fontsize=6.4, color=INK, weight='bold')
    bx.set_ylim(0, st['n'] + 3)
    bx.set_yticks([0, 4, 8, 12, 16])
    bx.set_xticks(range(4)); bx.set_xticklabels(L['b_arms'], fontsize=5.2)
    _row(bx, [f"{x['unsafe']}/{st['n']}" for x in arms], L['unsafe'])
    bx.set_ylabel(L['b_y'].format(n=st['n']), fontsize=5.8)
    bx.set_title(L['b_title'].format(n=st['n']), fontsize=6.4, pad=4, loc='left')
    bx.spines[['top', 'right']].set_visible(False)
    # (c) time: saved by truthful advice, extra under false advice, with the registered bound
    sv, ex = f['time_saved_s'], f['extra_s']
    pr = f['price']
    import random
    rnd = random.Random(7)             # fixed jitter: the figure is reproducible
    for x, vals, col in ((0, sv, GREEN), (1, ex, ORANGE)):
        cx.scatter([x + rnd.uniform(-0.14, 0.14) for _ in vals], vals, s=8, color=col, zorder=3, lw=0)
        m = statistics.median(vals)
        cx.hlines(m, x - 0.3, x + 0.3, color=INK, lw=1.0, zorder=4)
        cx.text(x + 0.33, m, L['c_med'].format(m=m), ha='left', va='center', fontsize=5.0, color=INK)
    cx.axhline(pr['bound'], color=RED, lw=0.7, ls='--')
    cx.text(-0.45, pr['bound'] + 1.2, L['c_bound'].format(b=pr['bound']), ha='left', va='bottom', fontsize=5.2, color=RED)
    cx.axhline(0, color=GREY, lw=0.5)
    cx.set_xlim(-0.5, 2.35); cx.set_ylim(-8, pr['bound'] + 9)
    cx.set_xticks([0, 1]); cx.set_xticklabels([L['c_cols'][0].format(n=len(sv)), L['c_cols'][1].format(m=len(ex))], fontsize=5.2)
    cx.set_ylabel('seconds' if lang == 'en' else '秒', fontsize=5.8)
    cx.set_title(L['c_title'], fontsize=6.4, pad=4, loc='left')
    cx.spines[['top', 'right']].set_visible(False)
    for o in outs:
        o.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(o, bbox_inches='tight', pad_inches=0.02, **({'dpi': 200} if o.suffix == '.png' else {}))
    plt.close(fig)
    return True


def main() -> int:
    ok = build('en', [ROOT / 'docs/paper/fig_a_results.pdf', ROOT / 'docs/figures/a_results_en.png'])
    ok = build('ja', [ROOT / 'docs/figures/a_results_ja.png']) and ok
    print('study A figure written' if ok else 'study A figure: no a_summary.json, nothing written')
    return 0


if __name__ == '__main__':
    sys.exit(main())
