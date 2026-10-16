#!/usr/bin/env python3
"""Regenerate every report / README figure from saved experiment data.

Inputs are committed result files (experiments/results/*.json[l]) and the curated
evidence copies; nothing here is hand-typed.  Run inside docker/run.sh (IPAex font).
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / 'docs/figures'
RES = ROOT / 'experiments/results'
for f in ('/usr/share/fonts/opentype/ipaexfont-gothic/ipaexg.ttf',):
    if Path(f).is_file():
        font_manager.fontManager.addfont(f)
        plt.rcParams['font.family'] = 'IPAexGothic'
plt.rcParams.update({'axes.spines.top': False, 'axes.spines.right': False, 'axes.edgecolor': '#8a8984',
                     'axes.labelcolor': '#52514e', 'xtick.color': '#52514e', 'ytick.color': '#52514e',
                     'axes.titleweight': 'bold', 'axes.titlesize': 13, 'figure.dpi': 150,
                     'savefig.bbox': 'tight', 'savefig.facecolor': '#fcfcfb', 'axes.facecolor': '#fcfcfb'})
BLUE, ORANGE, AQUA = '#2a78d6', '#eb6834', '#1baf7a'
GOOD, BAD, GRAY, INK, MUTED = '#008300', '#e34948', '#a3a29c', '#0b0b0b', '#52514e'


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / name)
    plt.close(fig)
    print('wrote', FIG / name)


# ------------------------------------------------------------------ architecture
def architecture():
    fig, ax = plt.subplots(figsize=(12, 6.45))
    ax.set_xlim(0, 12.1); ax.set_ylim(0, 6.45); ax.axis('off')

    def box(x, y, w, h, title, lines, color):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.02,rounding_size=0.12',
                                    fc='white', ec=color, lw=2))
        ax.text(x + 0.15, y + h - 0.28, title, fontsize=10.5, weight='bold', color=INK, va='center')
        for i, ln in enumerate(lines):
            ax.text(x + 0.15, y + h - 0.62 - i * 0.3, ln, fontsize=9, color=MUTED, va='center')

    def arrow(x1, y1, x2, y2, label='', color=MUTED):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle='-|>', color=color, lw=1.6, shrinkA=2, shrinkB=2))
        if label:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.14, label, fontsize=8.5, color=color, ha='center')

    ax.text(0.1, 6.15, 'RescueMind v3.3 — 実行時アーキテクチャ（全てローカル、クラウドAPI不使用）',
            fontsize=13, weight='bold', color=INK)
    X = (0.1, 3.25, 6.4, 9.55)   # column x; width 2.45 leaves 0.7 gaps for arrows
    Wb = 2.45
    box(X[0], 3.9, Wb, 1.7, '① 自然言語指示', ['「避難所Bに飲料水を届けて」', 'TF-IDF+ロジスティック回帰', '曖昧/複数物資/未対応→拒否'], BLUE)
    box(X[1], 3.9, Wb, 1.7, '② ミッション制御ノード', ['ウェイポイント追従', 'カメラ照準→静止確認', '新規2フレーム品質/時刻検査'], BLUE)
    box(X[2], 3.9, Wb, 1.7, '③ ローカルVLMチェック', ['Qwen2.5-VL-3B FP16/V100', '閉集合 対数確率×2問', '選択肢順を入替・閾値0.50'], ORANGE)
    box(X[3], 3.9, Wb, 1.7, '④ 判定', ['許可 → 避難所Bへ', '拒否 → その場で停止', '（危険検知も拒否）'], ORANGE)
    box(X[0], 1.55, Wb, 1.75, '実行環境', ['Docker: ROS 2 Jazzy', 'Ubuntu 22.04ホスト', 'sudo不要（dockerのみ）'], GRAY)
    box(X[1], 1.55, Wb, 1.75, '独立速度ガード', ['唯一の /cmd_vel 発行者', 'センサー鮮度/前方障害物', '異常はラッチして停止'], AQUA)
    box(X[2], 1.55, Wb, 1.75, 'Gazebo Harmonic', ['差動二輪＋LiDAR＋カメラ', '3シーン(正常/取違え/欠品)', 'EGLヘッドレス描画'], AQUA)
    box(X[3], 1.55, Wb, 1.75, '独立監査', ['Gazebo真値姿勢', 'ROS bag(MCAP)', 'Publisher監視'], AQUA)
    for k, lab in ((0, '物資・行先'), (1, '静止画'), (2, '確率')):
        arrow(X[k] + Wb, 4.75, X[k + 1], 4.75)
        ax.text(X[k] + Wb + 0.35, 4.92, lab, fontsize=8, color=MUTED, ha='center')
    arrow(X[1] + 1.2, 3.9, X[1] + 1.2, 3.3)
    ax.text(X[1] + 1.3, 3.55, '速度要求', fontsize=8.5, color=MUTED)
    arrow(X[1] + Wb, 2.15, X[2], 2.15)
    ax.text(X[1] + Wb + 0.35, 1.9, '/cmd_vel', fontsize=7, color=MUTED, ha='center')
    arrow(X[2], 2.8, X[1] + Wb, 2.8)
    ax.text(X[1] + Wb + 0.35, 2.95, '/odom\n/scan', fontsize=8, color=MUTED, ha='center', va='bottom')
    arrow(X[2] + 0.4, 3.3, X[1] + Wb - 0.3, 3.9)
    ax.text(X[2] + 0.1, 3.6, '/camera', fontsize=8.5, color=MUTED)
    ax.annotate('', xy=(X[1] + 1.6, 5.62), xytext=(X[3] + 1.2, 5.62),
                arrowprops=dict(arrowstyle='-|>', color=ORANGE, lw=1.6, connectionstyle='arc3,rad=0.18'))
    ax.text((X[1] + X[3]) / 2 + 1.4, 5.66, '許可時のみ 第2区間（避難所Bへ）を再開', fontsize=8.5, color=ORANGE, ha='center')
    arrow(X[2] + Wb, 2.4, X[3], 2.4)
    ax.text(X[2] + Wb + 0.35, 2.55, '真値', fontsize=8, color=MUTED, ha='center')
    ax.text(0.1, 0.9, '凡例：', fontsize=9, color=MUTED, weight='bold')
    for i, (c, t) in enumerate(((BLUE, '指示理解・制御'), (ORANGE, 'AI判断（VLM）'), (AQUA, '安全・シミュレーション・監査'))):
        ax.add_patch(Rectangle((0.75 + i * 2.6, 0.82), 0.3, 0.18, color=c))
        ax.text(1.15 + i * 2.6, 0.91, t, fontsize=9, color=INK, va='center')
    ax.text(0.1, 0.35, 'ロボットは物資を把持しない：「現地で物資を目視確認してから避難所へ向かう」判断と移動を対象とする。',
            fontsize=9, color=MUTED)
    save(fig, 'architecture.png')


# ------------------------------------------------------------------ dev-set ablation
def devset_ablation():
    summ = json.loads((RES / 'devset_summary.json').read_text())
    pick = {'qwen3b_json_baseline': 'v3.2 引継ぎ\n自由生成JSON（Qwen 3B）',
            'smolvlm2_scored': 'SmolVLM2-2.2B\n対数確率スコア',
            'qwen3b_scored': 'v3.3 採用\n対数確率スコア（Qwen 3B）'}
    rows = []
    for t in summ:
        if t['tag'] in pick:
            r = next(x for x in t['rows'] if x['tau'] == 0.5)
            rows.append((pick[t['tag']], r, t['parse_or_http_errors'], t['mean_latency_per_pass_s']))
    order = list(pick.values())
    rows.sort(key=lambda r: order.index(r[0]))
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), gridspec_kw={'width_ratios': [1.6, 1]})
    ax = axes[0]
    y = range(len(rows))
    names = [r[0] for r in rows]
    corr = [r[1]['allow_correct'] + r[1]['deny_correct'] for r in rows]
    fden = [r[1]['false_denial'] for r in rows]
    fapp = [r[1]['false_approval'] for r in rows]
    ax.barh(y, corr, color=BLUE, height=0.55, label='正しい判定')
    ax.barh(y, fden, left=corr, color=GRAY, height=0.55, label='誤拒否（安全側）', edgecolor='#fcfcfb', linewidth=2)
    ax.barh(y, fapp, left=[c + d for c, d in zip(corr, fden)], color=BAD, height=0.55, label='誤許可（危険側）')
    for i, r in enumerate(rows):
        ax.text(corr[i] - 0.6, i, f'{corr[i]}/48', ha='right', va='center', color='white', fontsize=10, weight='bold')
    ax.set_yticks(list(y)); ax.set_yticklabels(names, fontsize=9.5)
    ax.set_xlim(0, 48); ax.set_xlabel('開発用画像48枚（3シーン×2拠点×8視点）')
    ax.set_title('判定精度：閉集合スコアリングで 48/48')
    ax.legend(loc='lower center', bbox_to_anchor=(0.5, -0.42), ncol=3, frameon=False, fontsize=9)
    ax = axes[1]
    errs = [r[2] for r in rows]
    ax.barh(y, errs, color=ORANGE, height=0.55)
    for i, e in enumerate(errs):
        ax.text(e + 0.4, i, f'{e}', va='center', fontsize=10, color=INK)
    ax.set_yticks(list(y)); ax.set_yticklabels([''] * len(rows))
    ax.set_xlim(0, 96); ax.set_xlabel('解析不能な応答数（96問中）')
    ax.set_title('出力の頑健性')
    save(fig, 'devset_ablation.png')


# ------------------------------------------------------------------ campaign
def campaign_rows():
    rows = [json.loads(x) for x in (RES / 'campaign_ledger.jsonl').read_text().splitlines()]
    return [r for r in rows if r.get('final', True)], rows


def campaign_results():
    final, _ = campaign_rows()
    scenes = [('nominal', '正常配置'), ('swapped', '取り違え'), ('empty', '欠品')]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), gridspec_kw={'width_ratios': [1.2, 1]})
    ax = axes[0]
    cats = [('ALLOW', '許可して避難所へ到着', BLUE), ('DENY', '拒否してその場で停止', AQUA),
            ('DENY_UNVERIFIED', '拒否（証拠不足）', GRAY), ('FAILED', '失敗', BAD)]
    xs = range(len(scenes))
    bottom = [0] * len(scenes)
    for key, lab, col in cats:
        vals = [sum(1 for r in final if r['scene'] == s and r['observed_action'] == key) for s, _ in scenes]
        if sum(vals) == 0:
            continue
        ax.bar(xs, vals, bottom=bottom, color=col, width=0.55, label=lab, edgecolor='#fcfcfb', linewidth=2)
        for i, v in enumerate(vals):
            if v:
                ax.text(i, bottom[i] + v / 2, str(v), ha='center', va='center', color='white', weight='bold')
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_xticks(list(xs)); ax.set_xticklabels([f'{j}\n(期待: {"許可" if s == "nominal" else "拒否"})' for s, j in scenes])
    ax.set_ylabel('試行数'); ax.set_ylim(0, 11)
    correct = sum(r['correct'] for r in final)
    dec = [r for r in final if r.get('vlm_reason')]
    dec_ok = sum((r['vlm_reason'] == 'on_site_supply_confirmed') == (r['expected_action'] == 'ALLOW') for r in dec)
    ax.set_title(f'事前登録30試行：VLM判断 {dec_ok}/{len(dec)}、独立監査まで合格 {correct}/{len(final)}', fontsize=12)
    ax.legend(frameon=False, fontsize=9, loc='upper center', bbox_to_anchor=(0.5, -0.2), ncol=2)
    ax = axes[1]
    lat = [r['vlm_latency_s'] for r in final if r.get('vlm_latency_s') is not None]
    wall = [r['wall_s'] for r in final]
    ax.hist(lat, bins=12, color=ORANGE, edgecolor='#fcfcfb')
    med = sorted(lat)[len(lat) // 2] if lat else 0
    ax.axvline(med, color=INK, lw=1.2, ls='--')
    ax.text(med, ax.get_ylim()[1] * 0.92, f' 中央値 {med:.2f} 秒', fontsize=10)
    ax.set_xlabel('静止画取得 → 判定 までの時間 [秒]（2問×1パス）'); ax.set_ylabel('試行数')
    ax.set_title(f'VLM判断の遅延（n={len(lat)}）')
    save(fig, 'campaign_results.png')
    return {'n': len(final), 'correct': correct, 'median_vlm_latency_s': med,
            'median_wall_s': sorted(wall)[len(wall) // 2]}


def trajectories():
    final, _ = campaign_rows()
    fig, ax = plt.subplots(figsize=(8.2, 6.4))
    ax.add_patch(Rectangle((1.55, 1.55), .9, .9, fc='#e6e6e3', ec=MUTED)); ax.text(2, 2.62, '物資拠点 W', ha='center')
    ax.add_patch(Rectangle((-2.45, 1.55), .9, .9, fc='#e6e6e3', ec=MUTED)); ax.text(-2, 2.62, '物資拠点 M', ha='center')
    ax.add_patch(Rectangle((2.5, -2.4), 1, .8, fc='#cfe9d6', ec=GOOD)); ax.text(3, -2.68, '避難所 B', ha='center')
    ax.add_patch(Circle((0, 0), .08, color=INK)); ax.text(0.1, -0.25, 'スタート')
    seen = set()
    for r in final:
        rd = ROOT / 'experiments/results/evidence' / (r['run_id'] or 'none') / 'ground_truth_xy.json'
        if not rd.is_file():
            continue
        xy = json.loads(rd.read_text())
        col = BLUE if r['observed_action'] == 'ALLOW' else (AQUA if r['observed_action'] == 'DENY' else BAD)
        lab = {'ALLOW': '許可→避難所へ', 'DENY': '拒否→拠点で停止'}.get(r['observed_action'], '失敗')
        ax.plot([p[0] for p in xy], [p[1] for p in xy], color=col, lw=1.4, alpha=.75,
                label=None if lab in seen else lab)
        seen.add(lab)
        ax.plot(xy[-1][0], xy[-1][1], 'o', color=col, ms=5, mec='#fcfcfb')
    ax.set_aspect('equal'); ax.set_xlim(-3, 4); ax.set_ylim(-3, 3)
    ax.set_xlabel('x [m]（Gazebo真値）'); ax.set_ylabel('y [m]')
    ax.set_title('全30試行のGazebo真値軌跡')
    ax.legend(frameon=False, loc='lower left')
    ax.grid(color='#e9e8e4', lw=.6)
    save(fig, 'trajectories.png')


def wheel_bug():
    f = RES / 'wheel_axis_regression.json'
    if not f.is_file():
        return
    d = json.loads(f.read_text())
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.8), sharey=True)
    for ax, key, title in ((axes[0], 'handoff_v32', 'v3.2 引継ぎワールド（車輪軸の定義誤り）'),
                           (axes[1], 'fixed_v33', 'v3.3 修正後')):
        run = d[key]
        ax.plot([p[0] for p in run['truth']], [p[1] for p in run['truth']], color=BLUE, lw=3, label='Gazebo真値')
        ax.plot([p[0] for p in run['odom']], [p[1] for p in run['odom']], color=ORANGE, lw=2, ls='--', label='車輪オドメトリ /odom')
        ax.plot(0, 0, 'o', color=INK)
        ax.set_title(title + f"\n最大乖離 {run['max_gap_m']:.2f} m / 最大傾斜 {run['max_tilt_deg']:.0f}°", fontsize=11.5)
        ax.set_xlabel('x [m]'); ax.set_ylim(-0.35, 0.35); ax.grid(color='#e9e8e4', lw=.6)
    axes[0].set_ylabel('y [m]')
    axes[0].legend(frameon=False, loc='upper left')
    fig.suptitle('同じ /cmd_vel（0.3 m/s前進4秒→旋回3秒）を与えたときの比較', fontsize=12, y=1.07)
    save(fig, 'wheel_axis_regression.png')


def i01_drift():
    d = RES / 'i01_drift'
    if not (d / 'baseline.json').is_file() or not (d / 'sphere_wheels.json').is_file():
        return
    variants = [('baseline', '円柱コリジョン（v3.3）', GRAY), ('accel_1.0_3.0', '＋加速度制限', ORANGE),
                ('front_caster', '＋前キャスター', AQUA), ('sphere_wheels', '球コリジョン（採用）', BLUE)]
    pats = [('straight_2m', '直進2m'), ('turn_360', 'その場1回転'), ('medicine_route', '医療物資ルートの指令列')]
    fig, ax = plt.subplots(figsize=(11, 4))
    width = 0.2
    for k, (v, lab, col) in enumerate(variants):
        f = d / f'{v}.json'
        if not f.is_file():
            continue
        r = json.loads(f.read_text())['patterns']
        vals = [max(x['pos_error_m'] for x in r[pk]) if pk in r else 0 for pk, _ in pats]
        xs = [i + (k - 1.5) * width for i in range(len(pats))]
        ax.bar(xs, vals, width=width * 0.92, color=col, label=lab)
        for x, val in zip(xs, vals):
            ax.text(x, val + 0.005, f'{val:.3f}', ha='center', fontsize=8, color=INK)
    ax.set_xticks(range(len(pats))); ax.set_xticklabels([p[1] for p in pats])
    ax.set_ylabel('最終位置の誤差 [m]（オドメトリ − Gazebo真値）')
    ax.set_title('I-01 推測航法ドリフトの原因切り分け：車輪の円柱コリジョンが原因（球に変更で約1/15）')
    ax.legend(frameon=False, fontsize=9)
    save(fig, 'i01_drift.png')


def i08_models():
    f = RES / 'i08_model_selection.json'
    if not f.is_file():
        return
    rows = json.loads(f.read_text())
    import re
    def frac(v):
        m = re.match(r'(\d+)/(\d+)', v or '')
        return int(m.group(1)) / int(m.group(2)) if m else 0
    def unsafe(v):
        m = re.search(r'(FA|unsafe) (\d+)', v or '')
        return int(m.group(2)) if m else 0
    metrics = [('vision_v35', '視覚判定（開発176枚）'), ('explain', '状況説明の正確さ（128枚）'), ('intent_dev_i35', '指示理解（開発40文）')]
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.4), gridspec_kw={'width_ratios': [2.2, 1]})
    ax = axes[0]
    cols = [GRAY, AQUA, ORANGE, BLUE]
    width = 0.2
    for k, r in enumerate(rows):
        vals = [frac(r.get(m)) * 100 for m, _ in metrics]
        xs = [i + (k - 1.5) * width for i in range(len(metrics))]
        ax.bar(xs, vals, width=width * 0.92, color=cols[k], label=f"{r['model']}（{r['released']}）")
        for x, v in zip(xs, vals):
            ax.text(x, v + 0.8, f'{v:.0f}', ha='center', fontsize=8)
    ax.set_xticks(range(len(metrics))); ax.set_xticklabels([m[1] for m in metrics])
    ax.set_ylim(50, 105); ax.set_ylabel('正解率 [%]')
    ax.set_title('I-08 モデル比較（同一データ・同一プロンプトv35/i35）')
    ax.legend(frameon=False, fontsize=8.5, ncol=4, loc='upper center', bbox_to_anchor=(0.5, -0.12))
    ax = axes[1]
    names = [r['model'] for r in rows]
    fa = [unsafe(r.get('vision_v35')) for r in rows]
    ua = [unsafe(r.get('intent_dev_i35')) for r in rows]
    y = range(len(rows))
    ax.barh([i + 0.2 for i in y], fa, height=0.38, color=BAD, label='視覚の誤許可')
    ax.barh([i - 0.2 for i in y], ua, height=0.38, color=ORANGE, label='指示の危険な誤受理')
    ax.set_yticks(list(y)); ax.set_yticklabels(names); ax.set_xlim(0, 3)
    ax.set_title('危険側の誤り（少ないほど良い）'); ax.legend(frameon=False, fontsize=8.5)
    save(fig, 'i08_models.png')


if __name__ == '__main__':
    which = sys.argv[1:] or ['architecture', 'devset', 'campaign', 'trajectories', 'wheel']
    out = {}
    if 'architecture' in which: architecture()
    if 'devset' in which: devset_ablation()
    if 'campaign' in which and (RES / 'campaign_ledger.jsonl').is_file(): out['campaign'] = campaign_results()
    if 'trajectories' in which and (RES / 'campaign_ledger.jsonl').is_file(): trajectories()
    if 'wheel' in which: wheel_bug()
    if 'i01' in which or not sys.argv[1:]: i01_drift()
    if 'i08' in which or not sys.argv[1:]: i08_models()
    if out:
        (RES / 'figure_stats.json').write_text(json.dumps(out, indent=1) + '\n')
