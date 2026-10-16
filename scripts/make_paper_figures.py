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


def box(ax, x, y, w, h, title, sub='', fc='#eef3f8', ec=BLUE, fs=6.4, sfs=5.0):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.006,rounding_size=0.012', fc=fc, ec=ec, lw=0.8))
    ax.text(x + w / 2, y + h - 0.075, title, ha='center', va='top', fontsize=fs, color=INK, weight='bold')
    if sub:
        ax.text(x + w / 2, y + h - 0.20, sub, ha='center', va='top', fontsize=sfs, color=MUTED, linespacing=1.25)


def arrow(ax, p, q, text='', color=INK, ls='-', off=(0, 0.018), fs=5.0):
    ax.annotate('', xy=q, xytext=p, arrowprops=dict(arrowstyle='-|>', lw=0.7, color=color, ls=ls, shrinkA=1, shrinkB=1))
    if text:
        ax.text((p[0] + q[0]) / 2 + off[0], (p[1] + q[1]) / 2 + off[1], text, ha='center', va='bottom', fontsize=fs, color=color)


def fig_system():
    fig, ax = plt.subplots(figsize=(7.0, 2.05))
    ax.set_xlim(-0.012, 1.012); ax.set_ylim(0, 1.08); ax.axis("off")
    sim, ai, safe, ev = ('#f4f1ea', GREY), ('#fdf1e6', ORANGE), ('#eaf5ee', GREEN), ('#f2f2f2', GREY)
    box(ax, 0.0, 0.55, 0.14, 0.42, 'Gazebo Harmonic', 'differential-drive robot,\n2D lidar, mast camera', *sim, fs=5.8, sfs=4.7)
    box(ax, 0.18, 0.55, 0.14, 0.42, 'ros_gz_bridge', '/odom /scan /camera\n/clock /ground_truth/odom', *sim, fs=5.8, sfs=4.7)
    box(ax, 0.37, 0.55, 0.19, 0.42, 'Mission node', 'parse request, drive, stop,\ncheck, then deliver /\nsearch other station / stop', fs=5.8, sfs=4.7)
    box(ax, 0.655, 0.55, 0.16, 0.42, 'Local VLM server', 'Qwen3.5-9B, FP16, V100\nloopback HTTP only\nanswer-letter scoring', *ai, fs=5.8, sfs=4.7)
    box(ax, 0.37, 0.03, 0.19, 0.38, 'Velocity guard', 'sole /cmd_vel publisher; zero\non stale sensors, obstacle,\nstale request', *safe, fs=5.8, sfs=4.7)
    box(ax, 0.18, 0.03, 0.14, 0.38, 'Graph watcher', 'e-stop if another\n/cmd_vel publisher\nappears', *safe, fs=5.8, sfs=4.7)
    box(ax, 0.655, 0.03, 0.16, 0.38, 'Recorder, ROS bag', 'ground-truth odometry,\n/cmd_vel, sensors (MCAP)', *ev, fs=5.8, sfs=4.7)
    box(ax, 0.855, 0.03, 0.145, 0.94, 'Post-run audit', 'decision recomputed from\nsaved outputs and image\nhash\n\nground-truth arrival or\nno motion after refusal\n\nodometry drift\nbag finalised', *ev, fs=5.8, sfs=4.7)
    arrow(ax, (0.14, 0.76), (0.18, 0.76))
    arrow(ax, (0.32, 0.76), (0.37, 0.76), 'sensors', off=(0, 0.012))
    arrow(ax, (0.56, 0.84), (0.655, 0.84), 'image +\n3 questions', color=ORANGE, off=(0, 0.012))
    arrow(ax, (0.655, 0.66), (0.56, 0.66), 'answer\nprobabilities', color=ORANGE, off=(0, 0.012))
    arrow(ax, (0.465, 0.55), (0.465, 0.41), 'velocity request', off=(0.05, -0.02))
    arrow(ax, (0.37, 0.30), (0.27, 0.55), '/cmd_vel', color=GREEN, off=(-0.035, 0.0))
    arrow(ax, (0.32, 0.18), (0.37, 0.18), 'e-stop', color=RED, ls='--', off=(0, 0.012))
    arrow(ax, (0.32, 0.60), (0.655, 0.30), '', color=GREY)
    arrow(ax, (0.815, 0.22), (0.855, 0.22))
    ax.plot([0.465, 0.465, 0.93], [0.97, 1.04, 1.04], lw=0.7, color=INK)
    arrow(ax, (0.93, 1.04), (0.93, 0.97))
    ax.text(0.69, 1.045, 'mission log (decisions, model outputs, frames)', fontsize=5.0, color=INK, ha='center', va='bottom')
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
            ('box beside supply', lambda r: r.get('distractor_kind') == 'box' and r['scene'] == 'nominal' and r.get('distractor_at') == r['station'])]
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
