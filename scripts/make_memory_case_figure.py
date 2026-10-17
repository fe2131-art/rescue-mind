#!/usr/bin/env python3
"""Case-study figure for I-15 (cross-mission memory), campaign H, sequence Q09 mission 3.

Same world, no memory (M0) vs verified memory (M2). All numbers are read from the run
outputs; nothing is typed in by hand except the run ids.

  docker exec rm-dev rescuemind-entrypoint python3 scripts/make_memory_case_figure.py

Writes docs/paper/fig_h_case.pdf (English, 3.4 in, vector) and docs/figures/memory_case_ja.png
(Japanese, 1600x900).
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from run_paths import run_dir  # noqa: E402
RUN = {'M0': '4e5461e9e58542c4', 'M2': '54c52d274181424a'}
MASKS = ROOT / 'experiments/campaign_h_protocol_design_fire_masks.json'
INK, MUTED = '#1f2933', '#616e7c'
BLUE, ORANGE, GREEN, RED, GREY = '#2563a8', '#c4661f', '#2f7d4f', '#b3261e', '#9aa5b1'
CJK = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
CJKB = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'

TXT = {
    'en': dict(
        rows={'M0': 'M0, no memory', 'M2': 'M2, verified memory'},
        view={'front': 'front', 'L': 'left', 'R': 'right'},
        px='fire mask {n:,} px',
        verdict={'M0': 'deliver (missed fire)', 'M2': 'stop'},
        tau='$\\tau_h$ = {t:g}', tau_def='default 0.05', xlabel='hazard probability $p_h$ (log scale)',
        mem='memory: fire seen here 2 missions earlier', stopped='(not looked at: stopped)',
        title=None, foot=None),
    'ja': dict(
        rows={'M0': 'M0　記憶なし', 'M2': 'M2　検証つき記憶'},
        view={'front': '正面', 'L': '左', 'R': '右'},
        px='火炎マスク {n:,} px',
        verdict={'M0': '配達した（火を見逃し）', 'M2': '停止した'},
        tau='閾値 $\\tau_h$ = {t:g}', tau_def='通常の閾値 0.05', xlabel='危険確率 $p_h$（対数軸）',
        mem='記憶：2ミッション前にこの拠点で火を観測', stopped='（停止したため未確認）',
        title='記憶が慎重さを足した例',
        foot='同じ世界（Q09 ミッション3）。左から見た火は小さく、$p_h$ は 0.0346 と 0.0489 で 0.05 の手前。'
             '記憶は閾値を 0.01 に下げ、同じ見え方で判定が変わった。'),
}


def load():
    masks = {r['key']: r['fire_pixels'] for r in json.loads(MASKS.read_text())}
    out = {}
    for arm, rid in RUN.items():
        d = run_dir(rid)
        m = json.loads((d / 'mission.json').read_text())
        sc = lambda c: c['model_calls']['first']['scores']
        front = sc(m['checkpoint'])
        peeks = {p['side']: p for p in m['look_around']['peeks']}
        views = {'front': dict(img=d / 'checkpoint.jpg', p=front['hazard_prob'], px=masks['Q09m3'])}
        for s in ('L', 'R'):
            if s in peeks:
                views[s] = dict(img=d / peeks[s]['image'], p=sc(peeks[s])['hazard_prob'], px=masks['Q09m3' + s])
        tau = front['hazard_threshold']
        mem = m.get('memory') or {}
        if mem.get('caution'):
            tau = min(c['tau_h'] for c in mem['caution'].values())
        out[arm] = dict(views=views, tau=tau, allow=m['checkpoint']['decision']['allow'] and
                        not m['checkpoint']['decision'].get('look_around_hazard_sides') and
                        all(not p['hazard'] for p in peeks.values()))
        # sanity: the threshold the model call used is the one we plot
        for s, v in views.items():
            used = (sc(m['checkpoint']) if s == 'front' else sc(peeks[s]))['hazard_threshold']
            v['tau_used'] = used
    return out


def figure(lang, data):
    T = TXT[lang]
    pdf = lang == 'en'
    if pdf:
        plt.rcParams.update({'font.family': 'DejaVu Sans', 'pdf.fonttype': 42, 'ps.fonttype': 42})
        W, H, S = 3.4, 4.45, 1.0
    else:
        for f in (CJK, CJKB):
            font_manager.fontManager.addfont(f)
        plt.rcParams.update({'font.family': 'Noto Sans CJK JP'})
        W, H, S = 16.0, 9.0, 2.45
    plt.rcParams.update({'axes.linewidth': 0.6 * S, 'mathtext.fontset': 'dejavusans'})
    fig = plt.figure(figsize=(W, H), dpi=100 if not pdf else 300)
    fig.patch.set_facecolor('white')

    def A(x, y, w, h, **kw):  # inches from top-left
        return fig.add_axes([x / W, 1 - (y + h) / H, w / W, h / H], **kw)

    def txt(x, y, s, **kw):
        fig.text(x / W, 1 - y / H, s, **kw)

    y0 = 0.02
    if not pdf:
        txt(0.45, 0.55, T['title'], fontsize=30, weight='bold', color=INK, va='center')
        y0 = 1.0
    row_h = (H - y0 - (0.62 if not pdf else 0.03)) / 2
    for k, arm in enumerate(('M0', 'M2')):
        D = data[arm]
        top = y0 + k * row_h
        ok = D['allow']
        vc = RED if ok else GREEN
        verdict = T['verdict'][arm]
        tau = D['tau']
        if pdf:
            ih, iw = 1.16, 1.55
            txt(0.04, top + 0.08, T['rows'][arm], fontsize=7, weight='bold', color=INK, va='center')
            txt(W - 0.04, top + 0.08, T['tau'].format(t=tau) + '  →  ' + verdict, fontsize=6.4, weight='bold',
                color=vc, va='center', ha='right')
            ix, iy = [0.04, 0.04 + iw + 0.07], top + 0.22
            sx, sy, sw, sh = 0.42, iy + ih + 0.06, W - 0.42 - 0.12, row_h - (ih + 0.22 + 0.06) - 0.3
            fs, fs2 = 5.2, 5.0
        else:
            ih, iw = 2.7, 3.6
            txt(0.45, top + 0.28, T['rows'][arm], fontsize=19, weight='bold', color=INK, va='center')
            txt(W - 0.45, top + 0.28, T['tau'].format(t=tau) + '  →  ' + verdict, fontsize=17, weight='bold',
                color=vc, va='center', ha='right')
            if arm == 'M2':
                txt(3.2, top + 0.30, T['mem'], fontsize=11.5, color='#5b5fc7', va='center')
            ix, iy = [0.45, 0.45 + iw + 0.15], top + 0.62
            sx, sy, sw, sh = ix[1] + iw + 0.95, top + 0.9, W - (ix[1] + iw + 0.95) - 0.45, 1.8
            fs, fs2 = 12, 11.5
        for j, key in enumerate(('front', 'L')):
            v = D['views'][key]
            ax = A(ix[j], iy, iw, ih)
            ax.imshow(Image.open(v['img']))
            ax.set_xticks([]); ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_edgecolor(GREY); sp.set_linewidth(0.5 * S)
            lab = T['view'][key] + ' · ' + T['px'].format(n=v['px'])
            ax.text(0.02, 0.97, lab, transform=ax.transAxes, fontsize=fs2 - (0.2 if pdf else 0.5), va='top', color=INK,
                    bbox=dict(fc='white', ec='none', alpha=0.85, pad=1.2 * S))
        # strip: p_h per view against the threshold used in that arm
        ax = A(sx, sy, sw, sh)
        ax.set_xscale('log'); ax.set_xlim(2e-4, 1.0); ax.set_ylim(-0.6, 3.15)
        names = [key for key in ('front', 'L', 'R')]
        ax.set_yticks([2, 1, 0]); ax.set_yticklabels([T['view'][n] for n in names], fontsize=fs)
        ax.axvspan(tau, 1.0, color='#fbe9e7', lw=0, zorder=0)
        ax.vlines(tau, -0.6, 2.62, color=RED, lw=1.0 * S, zorder=2)
        if arm == 'M2':
            ax.vlines(0.05, -0.6, 2.62, color=GREY, lw=0.8 * S, ls=(0, (3, 2)), zorder=1)
        ax.text(tau, 3.1, T['tau'].format(t=tau), color=RED, fontsize=fs, ha='center', va='top', weight='bold')
        if arm == 'M2':
            ax.text(0.058, -0.5, T['tau_def'], color=MUTED, fontsize=fs - 0.4, ha='left', va='bottom')
        for yy, n in zip((2, 1, 0), names):
            v = D['views'].get(n)
            if v is None:
                ax.text(3e-4, yy, T['stopped'], fontsize=fs - 0.4, color=MUTED, va='center')
                continue
            hit = v['p'] >= tau
            ax.plot([2e-4, v['p']], [yy, yy], color=GREY, lw=0.6 * S, zorder=2)
            ax.plot(v['p'], yy, 'o' if not hit else 'D', ms=(3.8 if pdf else 11), color=RED if hit else BLUE,
                    mec='white', mew=0.5 * S, zorder=4)
            near = v['p'] > tau * 0.3
            ax.text(v['p'] / 1.3 if near else v['p'] * 1.3, yy + 0.3, f"{v['p']:.4f}", fontsize=fs, color=INK,
                    va='bottom', ha='right' if near else 'left')
        ax.tick_params(axis='x', labelsize=fs - 0.4, length=2 * S, width=0.5 * S)
        ax.tick_params(axis='y', length=0)
        for s in ('top', 'right', 'left'):
            ax.spines[s].set_visible(False)
        if arm == 'M2' or not pdf:
            ax.set_xlabel(T['xlabel'], fontsize=fs, color=MUTED, labelpad=1.5)
    if not pdf:
        txt(0.45, H - 0.38, T['foot'], fontsize=11.5, color=MUTED, va='center')
    return fig


def main():
    data = load()
    for arm, D in data.items():
        for s, v in D['views'].items():
            print(arm, s, v['p'], 'tau_used', v['tau_used'], 'mask px', v['px'])
        print(arm, 'tau plotted', D['tau'], 'delivered' if D['allow'] else 'stopped')
    f = figure('en', data)
    f.savefig(ROOT / 'docs/paper/fig_h_case.pdf', bbox_inches='tight', pad_inches=0.01)
    plt.close(f)
    f = figure('ja', data)
    f.savefig(ROOT / 'docs/figures/memory_case_ja.png', dpi=100)
    plt.close(f)


if __name__ == '__main__':
    main()
