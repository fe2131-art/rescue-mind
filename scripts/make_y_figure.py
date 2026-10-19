#!/usr/bin/env python3
"""Study Y in one figure (supplement, report, README); every number is read from x_summary.json (X-s, without the flag) and y_summary.json (Y-s, with it).

  (a) worlds or runs with NO delivery per arm: study X (the search stops at the refusal) against study Y (--hazard-continue)
  (b) unsafe deliveries in the fire worlds per arm, X against Y: the flag does not repair a perception miss (tighten-only, XC05)
  (c) the price of continuing: mean mission time in the fire worlds per arm (Y), with the mean number of visited stations

  python3 scripts/make_y_figure.py     # -> docs/paper/fig_y_results.pdf, docs/figures/y_results_en.png, docs/figures/y_results_ja.png
Nothing is written when y_summary.json or x_summary.json does not exist (no result, no figure).
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'
INK, MUTED = '#1f2933', '#616e7c'
BLUE, ORANGE, GREEN, RED, GREY = '#2563a8', '#c4661f', '#2f7d4f', '#b3261e', '#9aa5b1'
ARMS = (('control', 'control_hc'), ('monotone', 'monotone_hc'), ('scrutiny', 'scrutiny_hc'))

T = {
    'en': {'arms': ['no advice', 'tighten-only', 'scrutiny'],
           'a_title': '(a) no delivery', 'a_y': 'worlds / runs without a delivery', 'x': 'X: search stops at the refusal', 'y': 'Y: --hazard-continue',
           'b_title': '(b) unsafe deliveries (fire worlds)', 'b_y': 'delivery into the fire', 'note_b': 'XC05: every view\nbelow the threshold',
           'c_title': '(c) price of continuing (Y)', 'c_y': 'mean mission time (s)', 'visits': '{v:.1f} stations'},
    'ja': {'arms': ['助言なし', 'tighten-only', 'scrutiny'],
           'a_title': '(a) 配達できなかった数', 'a_y': '配達なしの世界・試行', 'x': 'X：拒否で探索が止まる', 'y': 'Y：--hazard-continue',
           'b_title': '(b) 火のある世界での危険な配達', 'b_y': '火への配達', 'note_b': 'XC05：全視点が\n閾値未満',
           'c_title': '(c) 続ける代償（Y）', 'c_y': '平均の所要時間（秒）', 'visits': '{v:.1f}拠点'},
}


def facts():
    xf, yf = RES / 'x_summary.json', RES / 'y_summary.json'
    if not (xf.is_file() and yf.is_file()):
        return None
    xs, ys = json.loads(xf.read_text())['X-s'], json.loads(yf.read_text())['Y-s']
    out = {}
    for xa, ya in ARMS:
        xar, yar = xs['arms'][xa[:-3] if xa.endswith('_hc') else xa], ys['arms'][ya]
        fx, cx = xar['fire_worlds'], xar['clean_worlds']
        n_x = xs['n_fire_worlds_perceivable'] + xs['n_clean_worlds']
        lost_x = fx['refused']['k'] + (cx['delivered']['n'] - cx['delivered']['k'])       # a refusal of the steered bay ended the mission
        fy, cy = yar['fire_worlds'], yar['clean_worlds']
        n_y = fy['n'] + cy['n']
        lost_y = (fy['n'] - fy['delivered']['k']) + (cy['n'] - cy['delivered']['k'])
        out[xa] = {'lost_x': (lost_x, n_x), 'lost_y': (lost_y, n_y), 'unsafe_x': (fx['unsafe_deliveries']['k'], fx['unsafe_deliveries']['n']),
                   'unsafe_y': (fy['unsafe_deliveries']['k'], fy['unsafe_deliveries']['n']), 'time_y': fy['mean_time_s'], 'visits_y': fy['mean_visits']}
    return out


def draw(F, lang, path):
    t = T[lang]
    fig, axs = plt.subplots(1, 3, figsize=(11.4, 3.5), gridspec_kw={'width_ratios': [1.05, 1.05, 0.9]})
    xs = range(3)
    for ax, key, title, ylab in ((axs[0], 'lost', t['a_title'], t['a_y']), (axs[1], 'unsafe', t['b_title'], t['b_y'])):
        w = 0.36
        for i, (arm, _) in enumerate(ARMS):
            kx, nx = F[arm][f'{key}_x']
            ky, ny = F[arm][f'{key}_y']
            b1 = ax.bar(i - w / 2, kx, w, color=GREY, edgecolor=INK, linewidth=0.6, label=t['x'] if i == 0 else None)
            b2 = ax.bar(i + w / 2, ky, w, color=GREEN if ky == 0 else RED, edgecolor=INK, linewidth=0.6, label=t['y'] if i == 0 else None)
            ax.text(i - w / 2, kx + 0.15, f'{kx}/{nx}', ha='center', va='bottom', fontsize=8.5, color=INK)
            ax.text(i + w / 2, ky + 0.15, f'{ky}/{ny}', ha='center', va='bottom', fontsize=8.5, color=INK)
        ax.set_xticks(list(xs))
        ax.set_xticklabels(t['arms'], fontsize=9)
        ax.set_title(title, fontsize=10, color=INK, loc='left')
        ax.set_ylabel(ylab, fontsize=9, color=MUTED)
        ax.set_ylim(0, 6.2)
        ax.spines[['top', 'right']].set_visible(False)
    axs[0].legend(fontsize=7.5, frameon=False, loc='upper left')
    axs[1].text(1.0, 4.2, t['note_b'], ha='center', fontsize=8, color=MUTED)
    ax = axs[2]
    for i, (arm, _) in enumerate(ARMS):
        ax.bar(i, F[arm]['time_y'], 0.55, color=BLUE, edgecolor=INK, linewidth=0.6)
        ax.text(i, F[arm]['time_y'] + 2, f"{F[arm]['time_y']:.0f} s\n" + t['visits'].format(v=F[arm]['visits_y']), ha='center', va='bottom', fontsize=8.5, color=INK)
    ax.set_xticks(list(xs))
    ax.set_xticklabels(t['arms'], fontsize=9)
    ax.set_title(t['c_title'], fontsize=10, color=INK, loc='left')
    ax.set_ylabel(t['c_y'], fontsize=9, color=MUTED)
    ax.set_ylim(0, 175)
    ax.spines[['top', 'right']].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=170 if str(path).endswith('.png') else None, bbox_inches='tight')
    plt.close(fig)


def main():
    F = facts()
    if not F:
        print('no x_summary.json / y_summary.json: no figure')
        return 0
    plt.rcParams['font.family'] = 'sans-serif'
    draw(F, 'en', ROOT / 'docs/paper/fig_y_results.pdf')
    draw(F, 'en', ROOT / 'docs/figures/y_results_en.png')
    try:
        from matplotlib import font_manager as fm
        ja = [f.name for f in fm.fontManager.ttflist if 'IPA' in f.name or 'Noto Sans CJK' in f.name]
        if ja:
            plt.rcParams['font.family'] = ja[0]
    except Exception:
        pass
    draw(F, 'ja', ROOT / 'docs/figures/y_results_ja.png')
    print('wrote fig_y_results.pdf, y_results_en.png, y_results_ja.png')
    return 0


if __name__ == '__main__':
    sys.exit(main())
