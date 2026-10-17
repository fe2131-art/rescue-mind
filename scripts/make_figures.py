#!/usr/bin/env python3
"""Regenerate every report / README figure from saved experiment data.

Inputs are committed result files (experiments/results/*.json[l]) and the curated
evidence copies; nothing here is hand-typed.  Run inside docker/run.sh (IPAex font).
"""
from __future__ import annotations
import json
import statistics
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
PURPLE = '#7b5cc4'


def architecture():
    """v3.6 runtime pipeline (flat style, Japanese labels)."""
    fig, ax = plt.subplots(figsize=(13.9, 8.6))
    ax.set_xlim(0, 13.9); ax.set_ylim(0, 8.6); ax.axis('off')

    def box(x, y, w, h, title, lines, color, dashed=False):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.02,rounding_size=0.12',
                                    fc='white', ec=color, lw=2.2, ls='--' if dashed else '-'))
        ax.text(x + 0.15, y + h - 0.3, title, fontsize=12, weight='bold', color=color, va='center')
        for i, ln in enumerate(lines):
            ax.text(x + 0.15, y + h - 0.72 - i * 0.37, ln, fontsize=10, color=INK, va='center')

    def arrow(x1, y1, x2, y2, color=MUTED, rad=0.0, lw=1.8):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle='-|>', color=color, lw=lw, shrinkA=1, shrinkB=1,
                                    connectionstyle=f'arc3,rad={rad}'))

    def label(x, y, t, ha='left', color=MUTED, fs=9.5):
        ax.text(x, y, t, fontsize=fs, color=color, ha=ha, va='center')

    ax.text(0.1, 8.25, 'RescueMind v3.6 — 実行時アーキテクチャ', fontsize=16, weight='bold', color=INK, va='center')
    ax.text(0.1, 7.8, '全推論はローカルGPU（クラウドAPI不使用）。記憶は提案だけ、判断は必ずその場で。', fontsize=11, color=MUTED, va='center')

    Wb, G = 2.5, 0.3
    X = [0.1 + i * (Wb + G) for i in range(5)]
    Y1, H1 = 3.7, 1.95          # main flow row
    Y2, H2 = 0.95, 1.95          # support row
    Y0, H0 = 6.2, 1.3            # memory row
    # ---- row 1: decision pipeline
    box(X[0], Y1, Wb, H1, '① 指示の理解', ['例「喉が渇いた人が多い」', 'ローカルLLMで意図解析', '選択式2問＋規則ガード'], BLUE)
    box(X[1], Y1, Wb, H1, '② ミッション制御', ['走行→停止→照準', '新規フレームを取得', '品質・時刻を検査'], BLUE)
    box(X[2], Y1, Wb, H1, '③ 現地VLMチェック', ['選択式2問（順序入替）', '＋危険の有無を質問', '不明は拒否（安全側）'], ORANGE)
    box(X[3], Y1, Wb, H1, '④ 見回し（I-14）', ['±0.4 mから再撮影', '危険の確認のみ', '1枚でも危険→承認取消'], ORANGE)
    box(X[4], Y1, Wb, H1, '⑤ 判定', ['許可 → 避難所へ配達', '物資違い → 別拠点を1回', '危険・不明 → 停止'], ORANGE)
    ym = Y1 + H1 / 2
    for k in range(4):
        arrow(X[k] + Wb + 0.03, ym, X[k + 1] - 0.03, ym)
    # ---- row 0: cross-mission memory
    mx, mw = X[1], X[3] + Wb - X[1]
    box(mx, Y0, mw, H0, '出動をまたぐ記憶（I-15）',
        ['提案は「拠点の順序」と「注意」だけ。確認は決して省略しない',
         '保存：見た物資の場所／火を見た拠点と向き（観測であり、正解データではない）'], PURPLE)
    arrow(X[1] + Wb / 2, Y0 - 0.03, X[1] + Wb / 2, Y1 + H1 + 0.03, color=PURPLE, lw=2.0)
    label(X[1] + Wb / 2 + 0.15, (Y0 + Y1 + H1) / 2, '提案：拠点順＋注意', color=PURPLE)
    xr = X[4] + Wb / 2
    yr = Y0 + H0 / 2
    ax.plot([xr, xr], [Y1 + H1 + 0.03, yr], color=PURPLE, lw=2.0, solid_capstyle='butt')
    arrow(xr, yr, mx + mw + 0.03, yr, color=PURPLE, lw=2.0)
    label((xr + mx + mw) / 2, yr + 0.3, '出動後に\n観測を保存', ha='center', color=PURPLE, fs=9)
    # ---- row 2: safety / simulation / audit / report
    box(X[0], Y2, Wb, H2, 'Gazebo Harmonic', ['差動二輪＋LiDAR＋カメラ', '取違え/欠品/火災/照明', 'EGLヘッドレス描画'], AQUA)
    box(X[1], Y2, Wb, H2, '独立速度ガード', ['唯一の /cmd_vel 発行者', '鮮度・前方障害物を検査', '異常はラッチして停止'], AQUA)
    box(X[2], Y2, Wb, H2, '第2モデル（任意, I-16）', ['Clef-Flash（Jev役）', '同じ画像を独立に判定', '両方が許可で初めて許可'], PURPLE, dashed=True)
    box(X[3], Y2, Wb, H2, '運用レポート（I-18）', ['ログから自動生成', '判断・根拠・画像を', '人が読める1枚にまとめる'], AQUA)
    box(X[4], Y2, Wb, H2, '記録・独立監査', ['Gazebo真値姿勢', 'ROS bag（MCAP）', '判定の再計算で検証'], AQUA)
    # mission node -> guard -> Gazebo, sensors back
    arrow(X[1] + Wb / 2 + 0.5, Y1 - 0.03, X[1] + Wb / 2 + 0.5, Y2 + H2 + 0.03)
    label(X[1] + Wb / 2 + 0.65, (Y1 + Y2 + H2) / 2, '速度要求')
    arrow(X[1] - 0.03, Y2 + 0.6, X[0] + Wb + 0.03, Y2 + 0.6)
    arrow(X[0] + Wb - 0.35, Y2 + H2 + 0.03, X[1] + 0.35, Y1 - 0.03, rad=0.0)
    label(X[0] + Wb - 0.5, (Y1 + Y2 + H2) / 2 + 0.05, 'センサー\n/odom /scan /camera', ha='right')
    # second model -> VLM check
    arrow(X[2] + Wb / 2, Y2 + H2 + 0.03, X[2] + Wb / 2, Y1 - 0.03, color=PURPLE, lw=2.0)
    label(X[2] + Wb / 2 + 0.15, (Y1 + Y2 + H2) / 2, '同じ画像を独立判定', color=PURPLE)
    # decision -> recorder -> report
    arrow(X[4] + Wb / 2, Y1 - 0.03, X[4] + Wb / 2, Y2 + H2 + 0.03)
    label(X[4] + Wb / 2 + 0.15, (Y1 + Y2 + H2) / 2, '全判定を記録')
    arrow(X[4] - 0.03, Y2 + H2 / 2, X[3] + Wb + 0.03, Y2 + H2 / 2)
    # ---- legend / note
    ax.text(0.1, 0.5, '凡例：', fontsize=10.5, color=MUTED, weight='bold', va='center')
    for i, (c, t) in enumerate(((BLUE, '指示理解・制御'), (ORANGE, 'AI判断（ローカルVLM）'),
                                (PURPLE, '記憶・第2モデル'), (AQUA, '安全・シミュレーション・監査'))):
        x0 = 0.85 + i * 3.1
        ax.add_patch(Rectangle((x0, 0.4), 0.3, 0.2, color=c))
        ax.text(x0 + 0.4, 0.5, t, fontsize=10.5, color=INK, va='center')
    ax.text(0.1, 0.08, 'ロボットは物資を把持しない：「現地で物資を目視確認してから避難所へ向かう」判断と移動を対象とする。',
            fontsize=10, color=MUTED, va='center')
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
    med = statistics.median(lat) if lat else 0
    ax.axvline(med, color=INK, lw=1.2, ls='--')
    ax.text(med, ax.get_ylim()[1] * 0.92, f' 中央値 {med:.2f} 秒', fontsize=10)
    ax.set_xlabel('静止画取得 → 判定 までの時間 [秒]（2問×1パス）'); ax.set_ylabel('試行数')
    ax.set_title(f'VLM判断の遅延（n={len(lat)}）')
    save(fig, 'campaign_results.png')
    return {'n': len(final), 'correct': correct, 'median_vlm_latency_s': med,
            'median_wall_s': statistics.median(wall)}


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


GROUP_JA = {'nominal': '正常配置\n（期待：配達）', 'swapped': '取り違え\n（期待：探索→配達）',
            'empty': '欠品\n（期待：両拠点で停止）', 'fire': '火災\n（期待：即停止）',
            'dim': '夕方の照明\n（期待：配達）', 'box': '空の台＋段ボール\n（期待：停止）'}
OBS_JA = [('ALLOW', '配達（1拠点目で確認）', BLUE), ('ALLOW_AFTER_SEARCH', '配達（別拠点を探索）', AQUA),
          ('DENY', '停止（物資なし）', '#6250d6'), ('DENY_HAZARD', '停止（危険を検知）', '#e87ba4'),
          ('DENY_UNVERIFIED', '停止（証拠不足）', GRAY), ('FAILED', '失敗', BAD)]


def campaign_d_rows():
    led = RES / 'campaign_D_ledger.jsonl'
    if not led.is_file():
        return []
    proto = {t['id']: t for t in json.loads((ROOT / 'experiments/v34_protocol.json').read_text())['trials']}
    rows = [json.loads(x) for x in led.read_text().splitlines()]
    out = []
    for r in rows:
        if not r.get('final', True):
            continue
        t = proto[r['trial_id']]
        r['group'] = ('fire' if t.get('hazard_at') else 'dim' if t.get('lighting') == 'dim_evening'
                      else 'box' if t.get('distractor_at') else t['scene'])
        out.append(r)
    return out


def campaign_d():
    rows = campaign_d_rows()
    if not rows:
        return
    groups = [g for g in ('nominal', 'swapped', 'empty', 'fire', 'dim', 'box') if any(r['group'] == g for r in rows)]
    fig, ax = plt.subplots(figsize=(12.5, 4.6))
    bottom = [0] * len(groups)
    for key, lab, col in OBS_JA:
        vals = [sum(1 for r in rows if r['group'] == g and r['observed_action'] == key) for g in groups]
        if not sum(vals):
            continue
        ax.bar(range(len(groups)), vals, bottom=bottom, color=col, width=0.6, label=lab, edgecolor='#fcfcfb', linewidth=2)
        for i, v in enumerate(vals):
            if v:
                ax.text(i, bottom[i] + v / 2, str(v), ha='center', va='center', color='white', weight='bold')
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_xticks(range(len(groups))); ax.set_xticklabels([GROUP_JA[g] for g in groups], fontsize=9.5)
    ax.set_ylabel('試行数')
    ok = sum(r['correct'] for r in rows)
    ax.set_title(f'評価D（v3.4、事前登録{len(rows)}試行）：期待どおりの行動 {ok}/{len(rows)}', fontsize=12.5)
    ax.legend(frameon=False, fontsize=9, ncol=3, loc='upper center', bbox_to_anchor=(0.5, -0.2))
    save(fig, 'campaign_d_results.png')


def trajectories_d():
    rows = campaign_d_rows()
    if not rows:
        return
    fig, ax = plt.subplots(figsize=(8.2, 6.4))
    ax.add_patch(Rectangle((1.55, 1.55), .9, .9, fc='#e6e6e3', ec=MUTED)); ax.text(2, 2.62, '物資拠点 W', ha='center')
    ax.add_patch(Rectangle((-2.45, 1.55), .9, .9, fc='#e6e6e3', ec=MUTED)); ax.text(-2, 2.62, '物資拠点 M', ha='center')
    ax.add_patch(Rectangle((2.5, -2.4), 1, .8, fc='#cfe9d6', ec=GOOD)); ax.text(3, -2.68, '避難所 B', ha='center')
    ax.add_patch(Circle((0, 0), .08, color=INK)); ax.text(0.1, -0.25, 'スタート')
    seen = set()
    colors = {k: c for k, _, c in OBS_JA}
    labels = {k: l for k, l, _ in OBS_JA}
    for r in rows:
        f = RES / 'evidence' / (r['run_id'] or 'none') / 'ground_truth_xy.json'
        if not f.is_file():
            continue
        xy = json.loads(f.read_text())
        k = r['observed_action']
        ax.plot([p[0] for p in xy], [p[1] for p in xy], color=colors.get(k, BAD), lw=1.3, alpha=.7,
                label=None if k in seen else labels.get(k, k))
        seen.add(k)
        ax.plot(xy[-1][0], xy[-1][1], 'o', color=colors.get(k, BAD), ms=5, mec='#fcfcfb')
    ax.set_aspect('equal'); ax.set_xlim(-3, 4); ax.set_ylim(-3, 3)
    ax.set_xlabel('x [m]（Gazebo真値）'); ax.set_ylabel('y [m]')
    ax.set_title('評価D 全試行の Gazebo 真値軌跡')
    ax.legend(frameon=False, loc='lower left', fontsize=8.5)
    ax.grid(color='#e9e8e4', lw=.6)
    save(fig, 'trajectories_d.png')


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
    if 'campaign_d' in which or not sys.argv[1:]:
        campaign_d(); trajectories_d()
    if out:
        (RES / 'figure_stats.json').write_text(json.dumps(out, indent=1) + '\n')
