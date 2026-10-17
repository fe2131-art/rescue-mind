#!/usr/bin/env python3
"""Study V figure: registered model predictions (95% predictive intervals, committed before the first V trial) next to the
closed-loop observations.  Without v_summary.json it draws the predictions only (marked 'observation pending').

  python3 scripts/make_v_figure.py      # -> docs/paper/fig_v_prediction.pdf (+ docs/figures/v_prediction_ja.png)
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'
ARMS = (('M0', 'no memory'), ('M1', 'naive memory'), ('M2', 'verified memory (ours)'))
COL = {'M0': '#7a7a7a', 'M1': '#c0392b', 'M2': '#1f6feb'}


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    pred = json.loads((RES / 'v_predictions.json').read_text())
    obs = json.loads((RES / 'v_summary.json').read_text()) if (RES / 'v_summary.json').is_file() else None
    panels = (('mean_time', 'mean mission time [s]', 'mean_time_s'), ('unsafe', 'unsafe deliveries (50 missions)', 'unsafe'),
              ('searches', 'searches (50 missions)', 'searches'))
    fig, axes = plt.subplots(1, 4, figsize=(9.2, 2.5), gridspec_kw={'width_ratios': [1, 1, 1, .8]})
    for ax, (key, label, okey) in zip(axes, panels):
        for i, (arm, _) in enumerate(ARMS):
            iv = pred['arms'][arm][key]
            ax.plot([i, i], [iv['p2.5'], iv['p97.5']], color=COL[arm], lw=6, alpha=.35, solid_capstyle='round')
            ax.plot(i, iv['p50'], marker='_', ms=14, color=COL[arm])
            if obs:
                v = (obs['arms'][arm] or {}).get(okey)
                if v is not None:
                    ax.plot(i, v, marker='o', ms=6, color=COL[arm], mec='black', mew=.7, zorder=3)
        ax.set_xticks(range(3)); ax.set_xticklabels([a for a, _ in ARMS])
        ax.set_ylabel(label, fontsize=8); ax.grid(axis='y', alpha=.3, lw=.5); ax.spines[['top', 'right']].set_visible(False)
    ax = axes[3]
    iv = pred['paired_mean_time_diff_s']['M0-M2']
    ax.plot([0, 0], [iv['p2.5'], iv['p97.5']], color=COL['M2'], lw=6, alpha=.35, solid_capstyle='round')
    ax.plot(0, iv['p50'], marker='_', ms=14, color=COL['M2'])
    if obs and obs.get('V1_time_diff', {}).get('mean_M0_minus_M2_s') is not None:
        ax.plot(0, obs['V1_time_diff']['mean_M0_minus_M2_s'], marker='o', ms=6, color=COL['M2'], mec='black', mew=.7, zorder=3)
    ax.set_xticks([0]); ax.set_xticklabels(['M0 − M2']); ax.set_xlim(-.8, .8)
    ax.set_ylabel('time saved per mission [s]', fontsize=8); ax.axhline(0, color='#999', lw=.6)
    ax.grid(axis='y', alpha=.3, lw=.5); ax.spines[['top', 'right']].set_visible(False)
    fig.suptitle('Study V: registered predictions (bars: 95% interval, tick: median) vs closed loop (dots)'
                 + ('' if obs else ' — observation pending'), fontsize=8.5)
    fig.tight_layout()
    fig.savefig(ROOT / 'docs/paper/fig_v_prediction.pdf')
    (ROOT / 'docs/figures').mkdir(exist_ok=True)
    fig.savefig(ROOT / 'docs/figures/v_prediction.png', dpi=160)
    print('wrote docs/paper/fig_v_prediction.pdf', 'with observations' if obs else '(predictions only)')


if __name__ == '__main__':
    main()
