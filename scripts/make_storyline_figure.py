#!/usr/bin/env python3
"""Storyline figure  攻撃 -> 発見 -> 対策 -> 再測定  for the Japanese explanatory report (main part).

Four stories, one row each; all text and numbers come from advice_numbers.storyline() (result files + docs/FINDINGS.md; nothing typed here).
A study without results reads 結果待ち (or, in submission snapshot mode, 登録済み・提出時点で未実施).  Rendered with matplotlib and Noto Sans CJK:
  docker exec rm-dev python3 scripts/make_storyline_figure.py [--out PATH]
make_report.py calls build() itself (snapshot mode writes under docs/snapshot/figures/, the tracked file is never touched then).
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import advice_numbers  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FR = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
FB = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
W_IN = 7.6                     # drawn about 1.1 x the text block (174 mm = 6.85 in): 6.9 pt text prints at about 6.3 pt
INK, MUTED, LINE = '#1e2228', '#5f6670', '#d9d9d4'
COL = {'attack': ('#d73c3c', '#fce8e8', '攻撃'), 'found': ('#eb6432', '#fdede2', '発見'),
       'fix': ('#286ed2', '#e1ecfc', '対策'), 'after': ('#19a573', '#ddf4e9', '再測定')}
AMBER = '#b26a00'
WARN: list = []


def build(out: Path, rows=None) -> bool:
    """Render the figure to `out`; False (nothing written) when matplotlib or the stories are missing."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib import font_manager as fm
        from matplotlib.patches import FancyBboxPatch
    except ImportError:
        return False
    rows = rows if rows is not None else advice_numbers.storyline()
    if not rows:
        return False
    for f in (FR, FB):
        if Path(f).is_file():
            fm.fontManager.addfont(f)
    plt.rcParams['font.family'] = 'Noto Sans CJK JP'
    wcol = [1.0, 1.2, 1.4, 1.2, 2.2]                       # row title | 攻撃 | 発見 | 対策 | 再測定 (inches)
    gap, left, top = 0.12, 0.06, 0.06
    head_h, pad, fs, lead = 0.30, 0.07, 6.9, 1.42
    total_w = sum(wcol) + gap * 4 + 2 * left
    fig = plt.figure(figsize=(W_IN, 6), dpi=300)                # height fixed after the layout is known
    rend = fig.canvas.get_renderer()

    def wrap(txt, width_in, size, bold=False):
        """Greedy wrap by measured width (inches); Japanese may break anywhere except before closing punctuation."""
        t = fig.text(0, 0, '', fontsize=size, fontweight='bold' if bold else 'normal')
        lines, cur = [], ''
        for tok in re.findall(r"[A-Za-z0-9/.\-_#%:=+<>~|\u03b1-\u03c9]+|.", txt):     # an ASCII word is never split
            t.set_text(cur + tok)
            if t.get_window_extent(rend).width / fig.dpi > width_in - 0.17 and cur.strip() and tok not in '、。）」，．' and not cur.endswith(('「', '（')):
                lines.append(cur.rstrip())
                cur = tok.lstrip()
            else:
                cur += tok
        lines.append(cur)
        t.remove()
        return lines

    # ---- layout: measure every cell first
    cells = []
    for r in rows:
        inner = [w - 2 * pad for w in wcol]
        cs = {'attack': wrap(r['attack'], inner[1], fs), 'found': wrap(r['found'], inner[2], fs), 'fix': wrap(r['fix'], inner[3], fs)}
        ex = []
        for t in r['extra']:
            pend = bool(r.get('pending')) and t.endswith(r['pending'])
            ex.append((wrap('・' + t, inner[4], fs), pend))
        cells.append((cs, ex))
    line_h = fs * lead / 72
    heights = []
    for (cs, ex) in cells:
        n_left = max(len(v) for v in cs.values())
        lab = len(wrap(r['label'], inner[4], 6.6))
        h_right = 0.27 + lab * 6.6 * 1.3 / 72 + 0.04 + sum(len(l) for l, _ in ex) * line_h + 0.03 * len(ex)           # headline + label + notes
        heights.append(max(n_left * line_h + 2 * pad + 0.06, h_right + pad))
    total_h = top + head_h + 0.06 + sum(heights) + gap * len(rows) + 0.05
    fig.set_size_inches(total_w, total_h)          # 1 data unit = 1 inch, so the measured text widths are exact
    rend = fig.canvas.get_renderer()
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, total_w); ax.set_ylim(total_h, 0); ax.axis('off')
    xs = [left]
    for w in wcol[:-1]:
        xs.append(xs[-1] + w + gap)

    # ---- column headers (chevrons) with arrows between them
    for i, key in enumerate(['attack', 'found', 'fix', 'after']):
        c, _, name = COL[key]
        x, w = xs[i + 1], wcol[i + 1]
        ax.add_patch(FancyBboxPatch((x, top), w, head_h, boxstyle='round,pad=0,rounding_size=0.05', fc=c, ec='none'))
        ax.text(x + w / 2, top + head_h / 2, name, color='white', fontsize=10.5, fontweight='bold', ha='center', va='center')
        if i < 3:
            ax.annotate('', xy=(xs[i + 2] - 0.005, top + head_h / 2), xytext=(x + w + 0.005, top + head_h / 2),
                        arrowprops=dict(arrowstyle='-|>', color=INK, lw=1.0, mutation_scale=7))
    y = top + head_h + 0.06 + gap / 2
    for r, (cs, ex), h in zip(rows, cells, heights):
        # row title
        ax.add_patch(FancyBboxPatch((xs[0], y), wcol[0], h, boxstyle='round,pad=0,rounding_size=0.05', fc='#2d3748', ec='none'))
        ax.text(xs[0] + wcol[0] / 2, y + h / 2, '\n'.join(wrap(r['title'], wcol[0] - 2 * pad, 7.8, True)), color='white', fontsize=7.8,
                fontweight='bold', ha='center', va='center', linespacing=1.3)
        for i, key in enumerate(['attack', 'found', 'fix', 'after']):
            c, bg, _ = COL[key]
            x, w = xs[i + 1], wcol[i + 1]
            ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0,rounding_size=0.05', fc=bg, ec=c, lw=0.8))
            if i < 3:
                lines = cs[key]
                if len(lines) * line_h + 2 * pad > h + 1e-6:
                    WARN.append(f"{r['key']}/{key}: text taller than the cell")
                ax.text(x + pad, y + pad + 0.02, '\n'.join(lines), color=INK, fontsize=fs, ha='left', va='top', linespacing=lead)
            else:
                yy = y + pad
                ax.text(x + pad, yy, r['before'], color='#c0392b', fontsize=11, fontweight='bold', ha='left', va='top')
                tw = fig.text(0, 0, r['before'], fontsize=11, fontweight='bold').get_window_extent(rend).width / fig.dpi
                ax.text(x + pad + tw + 0.06, yy, '→', color=INK, fontsize=11, fontweight='bold', ha='left', va='top')
                ax.text(x + pad + tw + 0.28, yy, r['after'], color='#12805a', fontsize=11, fontweight='bold', ha='left', va='top')
                yy += 0.27
                ax.text(x + pad, yy, '\n'.join(wrap(r['label'], w - 2 * pad, 6.6)), color=MUTED, fontsize=6.6, ha='left', va='top')
                yy += len(wrap(r['label'], w - 2 * pad, 6.6)) * 6.6 * 1.3 / 72 + 0.04
                for lines, pend in ex:
                    ax.text(x + pad, yy, '\n'.join(lines), color=AMBER if pend else INK, fontsize=fs, ha='left', va='top', linespacing=lead,
                            fontweight='bold' if pend else 'normal')
                    yy += len(lines) * line_h + 0.03
                if yy - 0.03 + pad > y + h + 0.03:
                    WARN.append(f"{r['key']}/after: text taller than the cell")
        y += h + gap
    for t in fig.texts:                     # the measuring texts were removed/never drawn; nothing else is on the figure level
        t.set_visible(False)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, facecolor='white')
    plt.close(fig)
    return True


def default_out() -> Path:
    return (advice_numbers.snapshot_dir() / 'figures' if advice_numbers.snapshot_mode() else ROOT / 'docs/figures') / 'storyline_ja.png'


if __name__ == '__main__':
    o = Path(sys.argv[sys.argv.index('--out') + 1]) if '--out' in sys.argv else default_out()
    ok = build(o)
    print(o if ok else 'not built (matplotlib or the result files are missing)')
    for w in WARN:
        print('WARNING:', w)
