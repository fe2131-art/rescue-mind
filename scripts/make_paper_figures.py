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
    box(ax, 0.37, 0.55, 0.19, 0.42, 'Mission node', 'parse request, drive, stop,\ncheck + look from both sides,\nthen deliver / search / stop', fs=5.8, sfs=4.7)
    box(ax, 0.0, 0.03, 0.14, 0.38, 'Mission memory', 'what the robot saw before;\nmay reorder stations and\ntighten tau_h, never skip', '#eef0fb', '#5b5fc7', fs=5.8, sfs=4.4)
    ax.plot([0.07, 0.07, 0.40], [0.41, 0.48, 0.48], lw=0.7, color='#5b5fc7')
    arrow(ax, (0.40, 0.48), (0.40, 0.55), '', color='#5b5fc7')
    ax.text(0.15, 0.495, 'plan / observations', fontsize=4.8, color='#5b5fc7', ha='left', va='bottom')
    box(ax, 0.655, 0.55, 0.16, 0.42, 'Local VLM server(s)', 'Qwen3.5-9B (FP16, V100);\nopt. Qwen3.5-4B + Clef-Flash\nin the Jev role (both approve)\nloopback HTTP only', *ai, fs=5.8, sfs=4.4)
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
        c = m.get('risk_coverage_tau_h_0.05', m['risk_coverage'])
        ax.plot([100 * x[2] for x in c], [100 * x[1] for x in c], lw=1.4 if name == 'Qwen3.5-9B' else 1.0,
                color=colors.get(name, GREY), label=name)
        f50 = m['rules'].get('v35_tau_h_0.05', m['rules']['full'])
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


def fig_e_trajectories():
    from matplotlib.patches import Rectangle, Circle
    f = RES / 'campaign_E_ledger.jsonl'
    if not f.is_file():
        return
    rows = [r for r in (json.loads(x) for x in f.read_text().splitlines()) if r.get('final', True)]
    fig, ax = plt.subplots(figsize=(3.45, 2.7))
    for (x, y), name in (((1.55, 1.55), 'water station'), ((-2.45, 1.55), 'medicine station')):
        ax.add_patch(Rectangle((x, y), .9, .9, fc='#e6e6e3', ec=GREY, lw=0.6))
        ax.text(x + .45, y + 1.0, name, ha='center', fontsize=5.6, color=MUTED)
    ax.add_patch(Rectangle((2.5, -2.4), 1, .8, fc='#dcefe2', ec=GREEN, lw=0.6))
    ax.text(3, -2.62, 'shelter B', ha='center', fontsize=5.6, color=MUTED)
    ax.add_patch(Circle((0, 0), .07, color=INK))
    style = {'ALLOW': (BLUE, 'delivered'), 'ALLOW_AFTER_SEARCH': ('#5b8fd1', 'delivered after search'),
             'DENY': (GREY, 'refused, stopped'), 'DENY_HAZARD': (RED, 'hazard, stopped'),
             'DENY_HAZARD_AFTER_SEARCH': (ORANGE, 'hazard after search, stopped')}
    seen = set()
    for r in rows:
        g = RES / 'evidence' / (r['run_id'] or 'none') / 'ground_truth_xy.json'
        if not g.is_file():
            continue
        xy = json.loads(g.read_text())
        col, lab = style.get(r['observed_action'], ('#000000', r['observed_action']))
        ax.plot([q[0] for q in xy], [q[1] for q in xy], color=col, lw=0.8, alpha=0.7, label=None if lab in seen else lab)
        seen.add(lab)
        ax.plot(xy[-1][0], xy[-1][1], 'o', color=col, ms=2.2)
    ax.set_aspect('equal'); ax.set_xlim(-2.8, 3.8); ax.set_ylim(-2.8, 2.8)
    ax.set_xlabel('x [m] (Gazebo ground truth)'); ax.set_ylabel('y [m]')
    for sp in ('top', 'right'):
        ax.spines[sp].set_visible(False)
    ax.legend(frameon=False, fontsize=5.2, loc='lower left')
    fig.savefig(OUT / 'fig_e_trajectories.pdf', bbox_inches='tight', pad_inches=0.01)
    plt.close(fig)


def fig_lookaround(run='9d73663832c94f16'):
    """Front vs left side view of one v3.6 demo mission (campaign G world W03): the front check approved, the side view refused."""
    import json
    from PIL import Image
    d = ROOT / 'outputs/runs' / run
    if not (d / 'peek_L_checkpoint.jpg').is_file():
        print('fig_lookaround: run not available, keeping the existing figure'); return
    m = json.loads((d / 'mission.json').read_text())
    ph_front = m['checkpoint']['model_calls']['first']['scores']['hazard_prob']
    pk = m['look_around']['peeks'][0]
    ph_side = pk['model_calls']['first']['scores']['hazard_prob']
    fig, ax = plt.subplots(1, 2, figsize=(3.45, 1.32))
    for a, f, t in ((ax[0], 'checkpoint.jpg', f'front: $p_h$={ph_front:.3f} < 0.05 (approve)'),
                    (ax[1], 'peek_L_checkpoint.jpg', f'0.4 m left: $p_h$={ph_side:.2f} (refuse)')):
        a.imshow(Image.open(d / f)); a.set_title(t, fontsize=5.6, pad=2); a.axis('off')
    fig.tight_layout(pad=0.2, w_pad=0.4)
    fig.savefig(OUT / 'fig_lookaround.pdf', bbox_inches='tight', pad_inches=0.01, dpi=220)
    plt.close(fig)


def fig_r_examples(image='images/t2_06_medicine_1.jpg'):
    """Study R: one held-out T2 frame under the six registered degradations (severe level)."""
    import sys
    from PIL import Image
    sys.path.insert(0, str(ROOT))
    from rescuemind.corruptions import corrupt
    src = Image.open(ROOT / 'experiments/vlm_testset_t2' / image).convert('RGB')
    fams = [('clean', None), ('noise', 'gaussian_noise_S'), ('motion blur', 'motion_blur_S'), ('defocus', 'defocus_blur_S'),
            ('under-exp.', 'underexposure_S'), ('over-exp.', 'overexposure_S'), ('JPEG q8', 'jpeg_S')]
    fig, ax = plt.subplots(1, 7, figsize=(7.0, 0.95))
    for a, (t, c) in zip(ax, fams):
        im = src if c is None else corrupt(src, c, seed=1)
        a.imshow(im.crop((80, 60, 560, 420))); a.set_title(t, fontsize=5.6, pad=1.5); a.axis('off')
    fig.tight_layout(pad=0.1, w_pad=0.2)
    fig.savefig(OUT / 'fig_r_examples.pdf', bbox_inches='tight', pad_inches=0.01, dpi=200)
    plt.close(fig)


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    fig_lookaround()
    fig_r_examples()
    fig_system()
    fig_risk_coverage()
    fig_t1_examples()
    fig_e_trajectories()
    print('figures written to', OUT)
