#!/usr/bin/env python3
"""Vector figures for the paper (docs/paper/fig_*.pdf), all from result files.

  python3 scripts/make_paper_figures.py
"""
from __future__ import annotations
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'
OUT = ROOT / 'docs/paper'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 7, 'axes.linewidth': 0.6,
                     'pdf.fonttype': 42, 'ps.fonttype': 42})
INK, MUTED = '#1f2933', '#616e7c'
BLUE, ORANGE, GREEN, RED, GREY = '#2563a8', '#c4661f', '#2f7d4f', '#b3261e', '#9aa5b1'


def box(ax, x, y, w, h, title, sub='', fc='#eef3f8', ec=BLUE):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.008,rounding_size=0.015', fc=fc, ec=ec, lw=0.8))
    ax.text(x + w / 2, y + h * (0.64 if sub else 0.5), title, ha='center', va='center', fontsize=7, color=INK, weight='bold')
    if sub:
        ax.text(x + w / 2, y + h * 0.3, sub, ha='center', va='center', fontsize=5.6, color=MUTED)


def arrow(ax, p, q, text='', color=INK, ls='-', off=(0, 0.018)):
    ax.annotate('', xy=q, xytext=p, arrowprops=dict(arrowstyle='-|>', lw=0.7, color=color, ls=ls, shrinkA=1, shrinkB=1))
    if text:
        ax.text((p[0] + q[0]) / 2 + off[0], (p[1] + q[1]) / 2 + off[1], text, ha='center', va='bottom', fontsize=5.4, color=color)


def fig_system():
    fig, ax = plt.subplots(figsize=(3.45, 2.35))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    box(ax, 0.02, 0.70, 0.30, 0.22, 'Gazebo Harmonic', 'diff-drive, lidar, camera', fc='#f4f1ea', ec=GREY)
    box(ax, 0.38, 0.70, 0.24, 0.22, 'ros_gz_bridge', '/odom /scan /camera', fc='#f4f1ea', ec=GREY)
    box(ax, 0.68, 0.70, 0.30, 0.22, 'Local VLM server', 'Qwen3.5-9B, FP16, V100', fc='#fdf1e6', ec=ORANGE)
    box(ax, 0.38, 0.38, 0.24, 0.20, 'Mission node', 'parse, navigate, check')
    box(ax, 0.02, 0.38, 0.30, 0.20, 'Velocity guard', 'sole /cmd_vel publisher', fc='#eaf5ee', ec=GREEN)
    box(ax, 0.68, 0.38, 0.30, 0.20, 'Graph watcher', 'e-stop on 2nd publisher', fc='#eaf5ee', ec=GREEN)
    box(ax, 0.02, 0.05, 0.46, 0.20, 'Independent recorder + ROS bag', 'ground truth /ground_truth/odom', fc='#f2f2f2', ec=GREY)
    box(ax, 0.54, 0.05, 0.44, 0.20, 'Post-run audit', 'decision recompute, GT arrival/stop', fc='#f2f2f2', ec=GREY)
    arrow(ax, (0.32, 0.81), (0.38, 0.81))
    arrow(ax, (0.50, 0.70), (0.50, 0.58), 'sensors', off=(0.055, -0.01))
    arrow(ax, (0.62, 0.50), (0.68, 0.74), 'HTTP\nloopback', color=ORANGE, off=(-0.01, -0.03))
    arrow(ax, (0.38, 0.47), (0.32, 0.47), 'request', off=(0.0, 0.012))
    arrow(ax, (0.17, 0.58), (0.17, 0.70), '/cmd_vel', color=GREEN, off=(0.06, -0.01))
    arrow(ax, (0.68, 0.45), (0.32, 0.43), '', color=RED, ls='--')
    ax.text(0.50, 0.405, 'e-stop', color=RED, fontsize=5.4, ha='center')
    arrow(ax, (0.48, 0.15), (0.54, 0.15))
    fig.savefig(OUT / 'fig_system.pdf', bbox_inches='tight', pad_inches=0.01)
    plt.close(fig)


def fig_risk_coverage():
    f = RES / 't1_summary.json'
    if not f.is_file():
        return
    t1 = json.loads(f.read_text())
    fig, ax = plt.subplots(figsize=(3.4, 2.1))
    colors = {'Qwen3.5-9B': BLUE, 'Qwen3.5-4B': '#5b8fd1', 'Qwen3-VL-8B': GREEN, 'Qwen2.5-VL-3B': ORANGE}
    for name, m in t1['models'].items():
        c = m['risk_coverage']
        ax.plot([100 * x[2] for x in c], [100 * x[1] for x in c], lw=1.4 if name == 'Qwen3.5-9B' else 1.0,
                color=colors.get(name, GREY), label=name)
        f50 = m['rules']['full']
        ax.plot(100 * f50['ca_rate'], 100 * f50['fa_rate'], 'o', ms=4, color=colors.get(name, GREY), mec='white', mew=0.8)
    for name, v in t1.get('json_method', {}).items():
        if isinstance(v, dict):
            ax.plot(100 * v['ca_rate'], 100 * v['fa_rate'], 'x', ms=5, color=colors.get(name, GREY), label=f'{name} free JSON')
    ax.set_xlabel('correct approvals (% of must-approve images)')
    ax.set_ylabel('false approvals\n(% of must-refuse images)')
    ax.grid(lw=0.3, color='#dde3ea'); ax.set_axisbelow(True)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    ax.legend(frameon=False, fontsize=5.6, loc='upper left')
    fig.savefig(OUT / 'fig_risk_coverage.pdf', bbox_inches='tight', pad_inches=0.01)
    plt.close(fig)


def fig_t1_examples():
    from PIL import Image
    d = ROOT / 'experiments/vlm_testset_t1'
    lab = d / 'labels.jsonl'
    if not lab.is_file():
        return
    rows = [json.loads(x) for x in lab.read_text().splitlines()]
    want = [('nominal plain', lambda r: r['scene'] == 'nominal' and not r.get('distractor_at') and r['hazard_visibility'] == 'hidden'),
            ('swapped', lambda r: r['scene'] == 'swapped' and not r.get('distractor_at') and r['hazard_visibility'] == 'hidden'),
            ('fire, correct supply', lambda r: r['scene'] == 'nominal' and r['hazard_visibility'] == 'visible'),
            ('cone (new)', lambda r: r.get('distractor_kind') == 'cone' and r.get('distractor_at') == r['station']),
            ('crate on empty platform (new)', lambda r: r.get('distractor_kind') == 'crate' and r['scene'] == 'empty' and r.get('distractor_at') == r['station']),
            ('box beside supply', lambda r: r.get('distractor_kind') == 'box' and r['scene'] != 'empty' and r.get('distractor_at') == r['station'])]
    fig, axes = plt.subplots(2, 3, figsize=(3.45, 1.85))
    for ax, (title, pred) in zip(axes.flat, want):
        r = next((r for r in rows if pred(r)), None)
        ax.axis('off')
        if r is None:
            continue
        ax.imshow(Image.open(d / r['image']))
        ax.set_title(f"{title}\nexpected: {r['expected']}", fontsize=5.4, pad=1.5, color=INK)
    fig.subplots_adjust(wspace=0.04, hspace=0.32)
    fig.savefig(OUT / 'fig_t1_examples.pdf', bbox_inches='tight', pad_inches=0.01, dpi=220)
    plt.close(fig)


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    fig_system()
    fig_risk_coverage()
    fig_t1_examples()
    print('figures written to', OUT)
