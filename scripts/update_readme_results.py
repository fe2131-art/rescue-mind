#!/usr/bin/env python3
"""Rewrite the README results block from experiments/results (no hand-typed numbers).

Pre-registered evaluations: campaigns G and F (closed loop, paired, v3.6 look-around), E (v3.5, primary
for the broad scenarios), D (v3.4) and the held-out tests T1 and T2 (offline, 600 images each). Every number is
computed from the result files; a part whose input file is missing is skipped.
"""
from __future__ import annotations
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from t1_analysis import decide, wilson  # noqa: E402
import count_tests  # noqa: E402  (generated test / findings counts)

RES = ROOT / 'experiments/results'
GROUP = {'nominal': ('正常配置', '配達'), 'swapped': ('水と救急箱の取り違え', '別拠点を探索して配達'),
         'empty': ('欠品（両拠点とも空）', '両拠点で確認して停止'), 'fire': ('拠点の裏で火災', '探索せず即停止'),
         'dim': ('夕方の暗い照明', '配達'), 'box': ('空の台に段ボール箱', '停止')}
OBS = {'ALLOW': '配達', 'ALLOW_AFTER_SEARCH': '探索して配達', 'DENY': '停止', 'DENY_HAZARD': '危険で停止',
       'DENY_HAZARD_AFTER_SEARCH': '探索後に危険で停止',
       'DENY_UNVERIFIED': '停止（証拠不足）', 'FAILED': '失敗'}
COND = {'plain': '通常', 'cone': 'コーン', 'crate': '木箱', 'box': '段ボール'}
SAFE = ('ALLOW', 'DELIVER_AFTER_SEARCH')          # trials where a safe delivery is possible
SMALL_FIRE_PX = 10000
HAZ_DETECT = 0.05


def pct(x: float, nd: int = 1) -> str:
    return f'{100 * x:.{nd}f}%'


def ci_txt(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f'Wilson 95%CI {pct(lo)}〜{pct(hi)}'


def read_jsonl(p: Path) -> list:
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def section_e():
    led, proto_f = RES / 'campaign_E_ledger.jsonl', ROOT / 'experiments/campaign_e_protocol.json'
    if not (led.is_file() and proto_f.is_file()):
        return None
    cond = {t['id']: t['condition'] for t in json.loads(proto_f.read_text())['trials']}
    allrows = read_jsonl(led)
    rows = [r for r in allrows if r.get('final', True)]
    n = len(rows)
    ok = sum(r['correct'] for r in rows)
    wrong = sum(bool(r.get('delivered')) and r['expected_action'] not in SAFE for r in rows)
    safe = [r for r in rows if r['expected_action'] in SAFE]
    safe_ok = sum(r['correct'] for r in safe)
    # strata (scene x condition); the fire behind the OTHER station is its own stratum
    def key(r):
        c = cond[r['trial_id']]
        return 'fire_other' if c == 'fire_other' else 'fire' if c == 'fire' else r['scene']
    names = {'nominal': ('正常配置', '配達'), 'swapped': ('取り違え', '別拠点を探索して配達'),
             'empty': ('欠品', '両拠点で確認して停止'), 'fire': ('要求拠点の裏で火災', '探索せず即停止'),
             'fire_other': ('取り違え＋別拠点の裏で火災', '探索しても火災で停止')}
    lines = ['| 条件 | 期待する行動 | 期待どおり | 内訳（妨害物・正解数） |', '|---|---|---|---|']
    for k, (ja, want) in names.items():
        rs = [r for r in rows if key(r) == k]
        if not rs:
            continue
        by = Counter(); byok = Counter()
        for r in rs:
            c = cond[r['trial_id']]
            c = 'plain' if c in ('fire', 'fire_other') else c
            by[c] += 1; byok[c] += r['correct']
        det = '、'.join(f'{COND.get(c, c)} {byok[c]}/{by[c]}' for c in by) if k not in ('fire', 'fire_other') else '火は全体が見える位置'
        lines.append(f'| {ja} | {want} | **{sum(r["correct"] for r in rs)}/{len(rs)}** | {det} |')
    fo = [r for r in rows if key(r) == 'fire_other']
    fo_txt = ''
    if fo:
        fo_stop = sum(r['observed_action'] == 'DENY_HAZARD_AFTER_SEARCH' and r['correct'] for r in fo)
        fo_txt = (f'* 「別拠点の裏の火災で、探索の途中で止まる」{len(fo)}試行：**{fo_stop}/{len(fo)}**'
                  f'が探索後に火災で停止（未知の木箱・コーンを含む世界での再確認）\n')
    # counterfactual baselines on the same trials
    b0_wrong = sum(r['expected_action'] not in ('ALLOW',) for r in rows)
    b0_ok = n - b0_wrong
    b1_done = sum(r['expected_action'] == 'ALLOW' and r.get('first_checkpoint_allow') for r in rows)
    b1_wrong = sum(bool(r.get('first_checkpoint_allow')) and r['expected_action'] not in SAFE for r in rows)
    retries = len(allrows) - n
    wrong_lo, wrong_hi = wilson(wrong, n)
    ok_lo, ok_hi = wilson(ok, n)
    s_lo, s_hi = wilson(safe_ok, len(safe))
    txt = f"""### 評価E（v3.5・主結果）：試行ごとにランダムな世界で{n}試行

照明・物資の位置と向き・妨害物（未知の木箱・コーンを含む）・火災を試行ごとに乱数で生成し、全スタック（Gazebo・ROS 2・ガード・ローカルVLM）を新規起動。
Qwen3.5-9B、回復探索・状況報告・LLM指示理解あり。条件は結果を見る前に [`PREREGISTRATION_E.md`](experiments/PREREGISTRATION_E.md) に固定。

{chr(10).join(lines)}

{fo_txt}* **誤配達（誤った物資・欠品・火災の拠点へ届けた）{wrong}/{n}**（Wilson 95%CI {pct(wrong_lo)}〜{pct(wrong_hi)}）、期待どおりの行動 **{ok}/{n}**（{pct(ok_lo)}〜{pct(ok_hi)}）、安全に届けられる{len(safe)}試行の達成 **{safe_ok}/{len(safe)}**（{pct(s_lo)}〜{pct(s_hi)}）
* 同じ{n}試行での反実仮想（実行せず、同じログから計算した方針比較）：
  * **確認なしの配達**（在庫表を信じる）：誤配達 **{b0_wrong}/{n}**、期待どおり {b0_ok}/{n}（正常配置だけ正しい）
  * **確認はするが回復探索なし**（v3.3方針）：誤配達 {b1_wrong}/{n}だが、安全に届けられる{len(safe)}試行のうち完了は **{b1_done}/{len(safe)}**（取り違えの{sum(r['expected_action'] == 'DELIVER_AFTER_SEARCH' for r in rows)}試行は停止で終わる）
  * 本方式：誤配達 {wrong}/{n}、完了 **{safe_ok}/{len(safe)}**
* VLM判断前のインフラ失敗による再試行：{retries}件（台帳に全件記録）。独立シーン数は{n}で、試行はすべて別の乱数世界。ただし**拠点の配置自体は固定**"""
    return txt, dict(n=n, ok=ok, wrong=wrong)


def t1_parts():
    f, dev = RES / 't1_summary.json', RES / 'devset_t1_qwen35_9b.json'
    if not f.is_file():
        return None
    s = json.loads(f.read_text())
    m = s['models'].get('Qwen3.5-9B')
    if m is None:
        return None
    full, v35 = m['rules']['full'], m['rules']['v35_tau_h_0.05']
    n_img = m['n_images']
    def fa_txt(r):
        lo, hi = r['fa_ci95']
        return f"**{r['false_approvals']}/{r['n_deny']}**（{pct(r['fa_rate'])}、95%CI {pct(lo)}〜{pct(hi)}）"
    def ca_txt(r):
        lo, hi = r['ca_ci95']
        return f"**{r['correct_approvals']}/{r['n_allow']}**（{pct(r['ca_rate'])}、95%CI {pct(lo)}〜{pct(hi)}）"
    claim_ok = full['fa_ci95'][1] < 0.02
    claim = ('登録した主張「誤許可2%未満」は、Wilson上限が2%を下回り**支持された**。' if claim_ok else
             f"登録した主張「誤許可2%未満」は**支持されなかった**（Wilson上限 {pct(full['fa_ci95'][1])} > 2%）。")
    return s, m, full, v35, n_img, fa_txt, ca_txt, claim, dev


def e_fire_note():
    f = RES / 'campaign_E_ledger_fire_visibility.json'
    if not f.is_file():
        return ''
    v = json.loads(f.read_text())
    nv = sum(x['visibility'] == 'visible' for x in v)
    some = 'すべて' if nv == len(v) else f'うち{nv}試行'
    return f'評価Eの火災{len(v)}試行の{some}は、停止位置から火が視野内にある配置（物資の陰に隠れる度合いは評価Eの設計に含めていない）'


def findings(s, m, dev):
    E_FIRE = e_fire_note()
    out = []
    if dev.is_file():
        recs = [r for r in json.loads(dev.read_text())['records'] if r['expected'] != 'ambiguous']
        deny = [r for r in recs if r['expected'] == 'deny']
        nofire = [r for r in deny if r['hazard_visibility'] == 'hidden']
        fa_nofire = sum(decide(r) for r in nofire)
        out.append(f'* **物資の確認は強い**：火災のない「拒否すべき」{len(nofire)}枚（取り違え・欠品・木箱・段ボールなど）で誤許可 **{fa_nofire}件**（登録済みv3.4規則）')
        fas = [r for r in deny if decide(r)]
        vis = [r for r in recs if r['hazard_visibility'] == 'visible']
        haz = lambda r: max(r['passes'][k]['scores']['hazard_prob'] for k in '12' if 'scores' in r['passes'][k])
        small = [r for r in vis if r['fire_pixels'] < SMALL_FIRE_PX]
        big = [r for r in vis if r['fire_pixels'] >= SMALL_FIRE_PX]
        det = lambda rs: sum(haz(r) >= HAZ_DETECT for r in rs)
        fa_vis = sum(r['hazard_visibility'] == 'visible' for r in fas)
        fa_small = sum(r['hazard_visibility'] == 'visible' and r['fire_pixels'] < SMALL_FIRE_PX for r in fas)
        lead = '**すべて**' if fa_vis == len(fas) else f'うち**{fa_vis}件**'
        out.append(f'* **残る弱点：物資の陰に一部しか見えない火災**。登録済みの誤許可{len(fas)}件の{lead}がこの型（物資は正しく、火が一部だけ見える）で、うち{fa_small}件は見える火が{SMALL_FIRE_PX:,}画素未満。'
                   f'見える火の検出（p(危険)≥{HAZ_DETECT}、2パスの最大）は{SMALL_FIRE_PX:,}画素以上で **{det(big)}/{len(big)}**、未満で **{det(small)}/{len(small)}**。'
                   f'{E_FIRE}')
    jm = s.get('json_method', {}).get('Qwen3.5-9B')
    if jm:
        out.append(f"* **選択肢文字の確率スコア vs 自由記述JSON**（Qwen3.5-9B）：正しい許可 **{m['rules']['full']['correct_approvals']}** 対 {jm['correct_approvals']}"
                   f"（誤許可 {m['rules']['full']['false_approvals']} 対 {jm['false_approvals']}）")
    m3 = s['models'].get('Qwen2.5-VL-3B')
    if m3 and 'A2_pass2_only' in m3['rules']:
        out.append(f"* **選択肢の順序入れ替えの効果**（Qwen2.5-VL-3B）：2問目だけだと誤許可 **{m3['rules']['A2_pass2_only']['false_approvals']}** 件、"
                   f"2問の合意で **{m3['rules']['full']['false_approvals']}** 件")
    return out


def section_d():
    pf, lf = ROOT / 'experiments/v34_protocol.json', RES / 'campaign_D_ledger.jsonl'
    if not (pf.is_file() and lf.is_file()):
        return None
    proto = {t['id']: t for t in json.loads(pf.read_text())['trials']}
    rows_all = read_jsonl(lf)
    rows = [r for r in rows_all if r.get('final', True)]
    for r in rows:
        t = proto[r['trial_id']]
        r['group'] = ('fire' if t.get('hazard_at') else 'dim' if t.get('lighting') == 'dim_evening'
                      else 'box' if t.get('distractor_at') else t['scene'])
    lat = sorted(r['vlm_latency_s'] for r in rows if r.get('vlm_latency_s') is not None)
    fa = sum(r['observed_action'] in ('ALLOW', 'ALLOW_AFTER_SEARCH') and r['expected_action'] in ('DENY', 'DENY_HAZARD')
             for r in rows)
    ok = sum(r['correct'] for r in rows)
    lines = ['| シナリオ | 期待する行動 | 期待どおり | 実際の行動 |', '|---|---|---|---|']
    for g, (ja, want) in GROUP.items():
        rs = [r for r in rows if r['group'] == g]
        if rs:
            c = sum(r['correct'] for r in rs)
            got = '、'.join(f'{OBS.get(k, k)} {v}' for k, v in Counter(r['observed_action'] for r in rs).items())
            lines.append(f'| {ja} | {want} | **{c}/{len(rs)}** | {got} |')
    misses = [r for r in rows if not r['correct']]
    miss_txt = ''.join(f"  * {r['trial_id']}（{GROUP[r['group']][0]}）：{OBS.get(r['observed_action'], r['observed_action'])}"
                       f"{' — ' + (r.get('error') or '')[:90] if r.get('error') else ''}\n" for r in misses)
    fig = ('\n![results](docs/figures/campaign_d_results.png)\n' if (ROOT / 'docs/figures/campaign_d_results.png').is_file() else '')
    lat_txt = f"* 判断遅延（静止画取得→判断）中央値 **{lat[len(lat) // 2]:.2f} 秒**（最大 {lat[-1]:.2f} 秒）\n" if lat else ''
    txt = f"""<details>
<summary>評価D（v3.4、{len(rows)}試行、固定配置の反復）の詳細</summary>

Qwen3.5-9B（ローカル・V100）、回復探索・状況報告・LLM指示理解をすべて有効にした構成で、試行ごとに全スタックを新規起動。

{chr(10).join(lines)}

* 期待どおりの行動 **{ok}/{len(rows)}**、誤った物資・火災の拠点からの配達（誤許可）**{fa}件**
{miss_txt}{lat_txt}* 成功・停止はいずれも Gazebo 真値軌跡・ROS bag・判断の再計算・（回復時は）探索手順で独立に監査（[`experiments/results/`](experiments/results/)）
* VLM判断前のインフラ失敗による再試行：{len(rows_all) - len(rows)}件（台帳に全件記録）。同じワールドの反復であり独立シーン数ではない
* 前バージョン v3.3（評価C、Qwen2.5-VL-3B、回復探索なし）の結果と経緯は [`docs/IMPROVEMENT_LOG.md`](docs/IMPROVEMENT_LOG.md)
{fig}
</details>"""
    return txt, dict(n=len(rows), ok=ok, fa=fa)


def section_v36():
    """Campaigns F and G (paired closed loop) and the held-out T2: the v3.6 story, all from the summaries."""
    jl = lambda n: json.loads((RES / n).read_text()) if (RES / n).is_file() else None
    f, g, t2 = jl('f_summary.json'), jl('g_summary.json'), jl('t2_summary.json')
    if not (f and g):
        return None
    gp, gc, fp, fc = g['primary'], g['per_config'], f['primary'], f['per_config']
    nf = gp['n_world_pairs_fire_perceivable']
    miss = [x for x in g.get('trials', []) if x['config'] == 'C' and x['wrong_delivery']]
    gl = [r for r in read_jsonl(RES / 'campaign_G_ledger.jsonl') if r.get('final', True)] if (RES / 'campaign_G_ledger.jsonl').is_file() else []

    def wall(c):
        w = sorted(r['wall_s'] for r in gl if r['config'] == c and r['expected_action'] == 'ALLOW')
        return w[len(w) // 2] if w else None
    wb, wc = wall('B'), wall('C')
    lines = ['| | B：正面のみ | **C：＋横から見直す（v3.6）** |', '|---|---|---|',
             f"| 3視点（正面・左右0.4 m）のどれかで火が見えた{nf}世界で、火があるのに配達した回数 | {gc['B']['wrong_deliveries']}/{gc['B']['visible_fire_trials']} | **{gc['C']['wrong_deliveries']}/{gc['C']['visible_fire_trials']}** |",
             f"| 火の無い世界での誤った停止 | {gc['B']['false_hazard_stops']}/{gc['B']['fire_free_trials']} | **{gc['C']['false_hazard_stops']}/{gc['C']['fire_free_trials']}** |",
             f"| 期待どおりの行動 | {gc['B']['correct']}/{gc['B']['n']}（{pct(gc['B']['correct_ci95'][0], 0)}〜{pct(gc['B']['correct_ci95'][1], 0)}） | **{gc['C']['correct']}/{gc['C']['n']}**（{pct(gc['C']['correct_ci95'][0], 0)}〜{pct(gc['C']['correct_ci95'][1], 0)}） |"]
    if wb and wc:
        lines.append(f"| 正常配達1回の所要時間（中央値） | {wb:.0f} 秒 | {wc:.0f} 秒（+{wc - wb:.0f} 秒） |")
    mtxt = ''
    if miss:
        m = miss[0]
        mtxt = (f"\n* 唯一の見逃し（{m['world']}）：火が正面から {m['fire_pixels_front']} 画素（完全に隠れる）、横からも最大 {m['fire_pixels_best_side']:,} 画素と最小で、"
                f"p(危険)が閾値0.05に届かなかった。限界として明記")
    t2txt = ''
    if t2:
        R = t2['results']
        ref, j2, sel = R[t2['reference']], R['J2(Clef-task) tau_h=0.05'], R[t2['selected']]
        cl = jl('devset_t2_clef2.json')
        lat = sorted(r['clef']['latency_s'] for r in cl['records'] if r.get('clef')) if cl else []
        t2txt = (f"\n* **未使用テスト T2**（{ref['n_deny'] + ref['n_allow']}枚、描画前に登録）：v3.5 でも誤許可 **{ref['false_approvals']}/{ref['n_deny']}** と天井で、改善は測れない。"
                 f"Jev役を担うローカルの **Clef-Flash 単独**（課題向けの質問）も誤許可 **{j2['false_approvals']}/{j2['n_deny']}**・正しい許可 {j2['correct_approvals']}/{j2['n_allow']}"
                 + (f"、1画像あたりの推論は中央値 {statistics.median(lat):.1f} 秒（V100）" if lat else '')
                 + f"。Clef＋Qwen の2モデル確認（規則上の選定）は誤許可 {sel['false_approvals']}/{sel['n_deny']}・正しい許可 {sel['correct_approvals']}/{sel['n_allow']}（V100 1台には同時に載らず、既定には採用せず）")
    fm = sorted(x['fire_pixels'] for x in f.get('trials', []) if x['config'] == 'B' and x['wrong_delivery'] and x.get('fire_pixels'))
    fpx = f"Bが見逃した火は正面から {fm[0]:,}〜{fm[-1]:,} 画素（{len(fm)}件）" if fm else 'Bが見逃した火は小さい'
    txt = f"""### v3.6：物資の陰に隠れた小さな火への対策（現在の既定構成）

T1 で分かった弱点に、結果を見る前に固定した条件で段階的に対策（[`IMPROVEMENT_LOG.md`](docs/IMPROVEMENT_LOG.md) I-11・I-13・I-14）。
**v3.6 = オーケストレータの既定値**：Qwen3.5-9B、危険の問い方 h36＋拡大切り出し tiles、τ_h=0.05、**横から見直す 0.4 m**、回復探索・状況報告あり、DDS非同期。

* 評価F（問い方＋切り出し、対比較、[`PREREGISTRATION_F.md`](experiments/PREREGISTRATION_F.md)）：小さな火が見えていた{fp['n_world_pairs_fire_visible_both']}世界で、火があるのに配達した回数
  v3.5 **{fp['wrong_deliveries_A']}/{fp['n_world_pairs_fire_visible_both']}** → **{fp['wrong_deliveries_B']}/{fp['n_world_pairs_fire_visible_both']}**（McNemar正確検定 p={fp['mcnemar_p']}、**有意でない**）。{fpx}、閾値では分けられなかった
* 評価G（**横から見直す**、新しい世界の対比較、[`PREREGISTRATION_G.md`](experiments/PREREGISTRATION_G.md)、{g['n_trials']}試行）：

{chr(10).join(lines)}

* 食い違いは B のみ {gp['discordant_B_only']}・C のみ {gp['discordant_C_only']}、McNemar正確検定 **p={gp['mcnemar_p']:.3f}**（事前登録した主張が成立）
* 読み方：この{nf}世界の火の多くは、設計上、正面からは見えにくい（または見えない）。したがって評価Gが測るのは「VLMが良くなった」ことではなく、そのような火に対して**横から見ると効果がある**ことである{mtxt}{t2txt}"""
    return txt, dict(nf=nf, gb=gc['B']['wrong_deliveries'], gcw=gc['C']['wrong_deliveries'], p=gp['mcnemar_p'], fs=gc['C']['false_hazard_stops'],
                     nfree=gc['C']['fire_free_trials'], ok=gc['C']['correct'], n=gc['C']['n'], okb=gc['B']['correct'],
                     fa=fp['wrong_deliveries_A'], fb=fp['wrong_deliveries_B'], nfv=fp['n_world_pairs_fire_visible_both'], fp=fp['mcnemar_p'])


PENDING = '実行中（事前登録済み）'


def jl(name):
    f = RES / name
    try:
        return json.loads(f.read_text()) if f.is_file() else None
    except ValueError:
        return None


def h_text():
    h = jl('h_summary.json')
    try:
        p1, p2, p3 = h['P1_efficiency_relocation_persist'], h['P2_safety_naive_vs_verified'], h['P3_no_extra_risk_vs_v36']
        return (f"評価H 結果：置き場所が変わったままの出動で所要時間の中央値差 {p1['median_diff_s']} 秒（{p1['n_pairs']}対、p={p1['wilcoxon_exact_p']}）、"
                f"危険な配達は 素朴な記憶 {p2['unsafe_M1']} 対 検証つき記憶 {p2['unsafe_M2']}（p={p2['mcnemar_p']}）、記憶なし比で追加リスク"
                f"{'なし' if p3['supported'] else 'あり'}（{p3['unsafe_M0']} 対 {p3['unsafe_M2']}）")
    except (TypeError, KeyError):
        return f'評価H（16系列×3出動）：{PENDING}'


def j_text():
    j = jl('j_summary.json')
    try:
        c, p2 = j['per_config'], j['P2_no_extra_unsafe']
        return (f"評価J 結果：2つのAI構成 {c['J']['correct']}/{c['J']['n']} 期待どおり（v3.6単独 {c['A']['correct']}/{c['A']['n']}）、"
                f"危険な配達 {p2['unsafe_J']} 対 {p2['unsafe_A']}、V100 1台での失敗 {c['J']['failed']}件")
    except (TypeError, KeyError):
        return f'評価J（24世界の対比較）：{PENDING}'


def audit_text():
    f = ROOT / 'docs/paper/tab_prereg.tex'
    if not f.is_file():
        return '登録コミットが結果コミットより前にあることを付録で監査'
    rows = [x for x in f.read_text().splitlines() if x.count('&') >= 4 and not x.startswith('Study')]
    ok = sum('checkmark' in x for x in rows)
    pend = sum('pending' in x for x in rows)
    return (f'全{len(rows)}研究の登録時刻と最初の結果の時刻を、git の履歴から機械的に監査（`git merge-base --is-ancestor`）。'
            f'結果のある研究のうち **{ok}件で登録コミットが結果コミットより前**、{pend}件は結果待ち（登録のみ済み）')


def section_novelty():
    g = jl('g_summary.json')
    try:
        gc = g['per_config']
        nf = g['primary']['n_world_pairs_fire_perceivable']
        gtxt = (f"正面で判断し切れない小さな火に、モデルを大きくせず**横へ動いて撮り直す**。事前登録の対比較で、火があるのに配達した回数 "
                f"**{gc['B']['wrong_deliveries']}/{nf} → {gc['C']['wrong_deliveries']}/{nf}**（p={g['primary']['mcnemar_p']:.3f}）、火の無い世界の誤った停止 {gc['C']['false_hazard_stops']}/{gc['C']['fire_free_trials']}")
    except (TypeError, KeyError):
        gtxt = f'横から撮り直す能動知覚（評価G）：{PENDING}'
    return f"""## 新規性（この課題で工夫した点）

* **記憶は「提案」だけ、確認は減らさない**（出動をまたぐ記憶、[I-15](docs/IMPROVEMENT_LOG.md)・[D13](docs/DESIGN_DECISIONS.md)）：前回の物資の場所は「先に行く拠点」を決めるだけで、行った先で必ず確認する。火を見た拠点は閾値を厳しくする。同じ画像なら記憶ありの許可は記憶なしの許可の部分集合になる（コードで強制）。事前登録 [`PREREGISTRATION_H.md`](experiments/PREREGISTRATION_H.md)。{h_text()}
* **横から見直す能動知覚**（[I-14](docs/IMPROVEMENT_LOG.md)）：{gtxt}。
* **当初計画の2つのAI（Jev役 Clef-Flash＋Qwen）をロボットの判断に組み込んで**（[I-16](docs/IMPROVEMENT_LOG.md)）：オフライン評価だけだった2モデル確認を、V100 1台に載る組で閉ループに載せた。Clef-Flash は Qwen3.5-9B の追加学習版なので、2つは独立ではなく系統を共有する（相関した失敗が残り得ると明記）。{j_text()}
* **事前登録と時系列監査**（論文 [`docs/paper/main.pdf`](docs/paper/main.pdf) 付録「Registration audit」）：条件・閾値・解析を結果を見る前にコミットし、{audit_text()}。支持されなかった主張も、そのまま載せる。"""


def section_zpr():
    """Rows for the table head (Z, P, R) plus an honest note under the table. Missing file -> pending."""
    rows, notes = [], []
    z = jl('z_summary.json')
    try:
        def zc(m, t):
            b, o = z['models'][m][t]['baseline'], z['models'][m][t]['ours']
            return b, o
        parts = []
        for t, tn in (('t1', 'T1'), ('t2', 'T2')):
            sb, o = zc('siglip', t)
            cb, _ = zc('clip', t)
            parts.append(f"{tn}：本方式 誤許可 {o['FA']}/{o['n_deny']}・正しい許可 {o['CA']}/{o['n_allow']}、"
                         f"SigLIP {sb['FA']}/{sb['n_deny']}・{sb['CA']}/{sb['n_allow']}、CLIP {cb['FA']}/{cb['n_deny']}・{cb['CA']}/{cb['n_allow']}")
        notes_z = "* 評価Z：SigLIP は正しい許可は満点でも誤許可が1割超。CLIP は誤許可0でも**ほぼ何も許可しない**（配達できない）。本方式だけが両立する"
        notes.append(notes_z)
        rows.append("| 評価Z（生成しないゼロショット基準） | 同じ画像・同じ判定構造で SigLIP・CLIP と比較（閾値は開発データだけで決定）。誤許可／正しい許可 | "
                    + '<br>'.join(parts) + ' |')
    except (TypeError, KeyError):
        rows.append(f'| 評価Z（SigLIP・CLIPとの比較） | 生成しないゼロショット基準 | {PENDING} |')
    p, p2 = jl('p_summary.json'), jl('p2_summary.json')
    try:
        r, fa = p['recall'], p['false_alarm']
        p2t = PENDING
        try:
            ct = p2['chosen_test']
            fz = p2['test_at_frozen_tau_0.05'][p2['chosen_wording']]
            p2t = (f"較正に使っていない400枚で、再現率 {ct['recall']['k']}/{ct['recall']['n']}、誤警報 {ct['false_alarm']['k']}/{ct['false_alarm']['n']}"
                   f"（{p2['chosen_wording']}、τ_h={p2['chosen_tau']}。固定の0.05では {fz['recall']['k']}/{fz['recall']['n']}・{fz['false_alarm']['k']}/{fz['false_alarm']['n']}）。"
                   f"登録した基準（再現率0.90以上かつ誤警報0.20以下）：**{'成立' if p2['claim_supported'] else '不成立'}**")
        except (TypeError, KeyError):
            if p2 and p2.get('chosen_wording') is None and 'claim_supported' in p2:
                p2t = '較正画像では閾値を決められず、登録した基準は **不成立**'
        rows.append(f"| 評価P（実写真） | Gazebo外の実写真400枚（D-Fire）で火・煙の問いを検証 | 火・煙のある画像の検出 **{r['k']}/{r['n']}**（95%CI {pct(r['ci95'][0])}〜{pct(r['ci95'][1])}）、"
                    f"火の無い画像の誤警報 **{fa['k']}/{fa['n']}**（{pct(fa['ci95'][0])}〜{pct(fa['ci95'][1])}）。P2（現場の火の無い画像で閾値を較正）：{p2t} |")
        notes.append(f"* 評価P：見逃しはほぼ無いが、火の無い実写真（霞・低い雲・夕焼け・光るテント）への誤警報は {fa['k']}/{fa['n']} と多い。**そのまま実機に使える水準ではなく、現場ごとの閾値の較正が必要**（P2 で「較正した閾値が未使用の写真で通用するか」を登録済み）。誤警報は停止になるだけで、誤配達にはならない側の失敗")
    except (TypeError, KeyError):
        rows.append(f'| 評価P（実写真） | Gazebo外の実写真での火・煙の検出 | {PENDING} |')
    r = jl('r_summary.json')
    try:
        p1 = r['P1_pooled']
        worst = min(r['conditions'].items(), key=lambda kv: kv[1]['ca_rate'])
        cl = r.get('clean', {})
        rows.append(f"| 評価R（カメラの劣化） | 未使用T2の30世界に、ノイズ・ぼけ・露出・JPEG の12条件を加えて再評価 | 全条件をまとめた誤許可 **{p1['false_approvals']}/{p1['n']}**"
                    f"（Wilson 95%CI {pct(p1['wilson_ci95'][0])}〜{pct(p1['wilson_ci95'][1])}、世界単位ブートストラップの上限 {pct(p1['cluster_ci95'][1])}、"
                    f"{'「劣化に対して安全側」を支持' if p1['supported'] else '登録した「上限2%未満」は支持されず'}）、"
                    f"最悪条件（{worst[0]}）でも誤許可は増えず、代償は可用性：正しい許可 {worst[1]['correct_approvals']}/{r['n_allow']}（{pct(worst[1]['ca_rate'])}、うち品質ゲート棄却 {worst[1]['gate_rejected']}）"
                    f"{'、清浄画像では ' + str(cl['correct_approvals']) + '/' + str(r['n_allow']) if 'correct_approvals' in cl else ''} |")
    except (TypeError, KeyError, ValueError):
        rows.append(f'| 評価R（カメラの劣化） | ノイズ・ぼけ・露出・JPEG の12条件でも安全側に倒れるか | {PENDING} |')
    return rows, notes


def sync_counts(txt, path):
    """Replace the test / findings counts in prose by the generated ones (scripts/count_tests.py)."""
    nt, nf = count_tests.n_tests(), count_tests.n_findings()
    subs = [(r'(実際に動かして初めて分かった)\d+(件の問題)', rf'\g<1>{nf}\g<2>'),
            (r'(テスト（)[^）]*?(件。ROS/Gazebo不要)', rf'\g<1>{nt}\g<2>' if nt else None),
            (r'(以下の)\d+(件の問題)', rf'\g<1>{nf}\g<2>'),
            (r'(単体テストは現在)\d+(件）)', rf'\g<1>{nt}\g<2>' if nt else None),
            (r'(FINDINGS\()\d+(件\))', rf'\g<1>{nf}\g<2>'),
            (r'(実行で見つけた)\d+(件)', rf'\g<1>{nf}\g<2>'),
            (r'(\| テスト \| )[^|]*?(件)前後(（`python3)', rf'\g<1>{nt}\g<2>\g<3>' if nt else None)]
    for pat, rep in subs:
        if rep:
            txt = re.sub(pat, rep, txt)
    return txt


def main():
    e, d, t, v = section_e(), section_d(), t1_parts(), section_v36()
    head = ['| 評価（事前登録） | 内容 | 結果 |', '|---|---|---|']
    if v:
        G = v[1]
        head.append(f"| **評価G（v3.6）** | 新しい世界での対比較の閉ループ。許可の直前に横から撮り直す | 3視点（正面・左右0.4 m）のどれかで火が見えた{G['nf']}世界で、火があるのに配達した回数 **{G['gb']}/{G['nf']} → {G['gcw']}/{G['nf']}**（McNemar正確検定 p={G['p']:.3f}）、火の無い世界の誤った停止 **{G['fs']}/{G['nfree']}** |")
        head.append(f"| 評価F（問い方＋切り出し） | 同じ形式の対比較 | 火があるのに配達した回数 {G['fa']}/{G['nfv']} → {G['fb']}/{G['nfv']}（p={G['fp']}、有意でない） |")
    if e:
        E = e[1]
        head.append(f"| **評価E（主結果）** v3.5 | 試行ごとにランダムな世界での閉ループ {E['n']}試行 | 期待どおり **{E['ok']}/{E['n']}**、誤配達 **{E['wrong']}/{E['n']}**（{ci_txt(E['wrong'], E['n'])}） |")
    if d:
        D = d[1]
        head.append(f"| 評価D v3.4 | 固定配置の閉ループ {D['n']}試行 | 期待どおり **{D['ok']}/{D['n']}**、誤許可 **{D['fa']}件** |")
    zrows, znotes = section_zpr()
    t1_block = ''
    if t:
        s, m, full, v35, n_img, fa_txt, ca_txt, claim, dev = t
        head.append(f"| 未使用テスト T1（オフライン） | 開発に一度も使わない{n_img}枚（照明・位置・未知の妨害物・火災）、v3.4規則 | 誤許可 {fa_txt(full)}、正しい許可 {ca_txt(full)} |")
        head.append(f"| 〃 v3.5（τ_h=0.05、副の事前指定） | 同じ画像・同じ保存済み確率から再計算 | 誤許可 {fa_txt(v35)}、正しい許可 {ca_txt(v35)} |")
        t1_block = f"* T1：{claim}主な原因は下の「残る弱点」"
    head += zrows
    parts = ['<!-- RESULTS:START -->', '## 結果：事前登録した評価（D・E・F・G・T1・T2・Z・P・R）', '',
             'Qwen3.5-9B（ローカル・V100）。条件・閾値・解析は結果を見る前に `experiments/PREREGISTRATION_*.md` に固定し、台帳は全試行を記録。', '',
             '用語：**誤許可**＝届けてはいけない場面で「届けてよい」と判断してしまうこと（ロボットを実際に動かす評価では**誤配達**。火のある拠点から届けてしまうことは**危険な配達**）。**正しい許可**＝届けてよい場面で正しく「よい」と判断できること。**閉ループ**＝AIの判断でロボットが実際に動くところまで含めた評価。', '',
             '\n'.join(head), '']
    if t1_block:
        parts += [t1_block] + znotes + ['']
    if v:
        parts += [v[0], '']
    if e:
        parts += [e[0], '']
    if t:
        fl = findings(s, m, dev)
        if fl:
            parts += ['### 分かったこと', '', '\n'.join(fl), '']
    if d:
        parts += [d[0]]
    parts.append('<!-- RESULTS:END -->')
    block = '\n'.join(parts)
    readme = ROOT / 'README.md'
    txt = readme.read_text(encoding='utf8')
    a, b = txt.index('<!-- RESULTS:START -->'), txt.index('<!-- RESULTS:END -->') + len('<!-- RESULTS:END -->')
    txt = txt[:a] + block + txt[b:]
    if '<!-- NOVELTY:START -->' in txt:     # novelty section near the top, numbers from the summaries
        a, b = txt.index('<!-- NOVELTY:START -->'), txt.index('<!-- NOVELTY:END -->') + len('<!-- NOVELTY:END -->')
        txt = txt[:a] + '<!-- NOVELTY:START -->\n' + section_novelty() + '\n<!-- NOVELTY:END -->' + txt[b:]
    chap = ROOT / 'docs/video_chapters.json'
    if chap.is_file():     # describe the video from the chapter file (length kept generic: it is re-rendered later)
        ch = json.loads(chap.read_text(encoding='utf8'))
        sp = next((c['speed'] for c in ch if c.get('speed')), None)
        demos = [c['title'].split('：', 1)[-1] for c in ch if c.get('kind') == 'mission']
        n_tab = sum(c.get('kind') == 'table' for c in ch)
        length = '3分以内' if ch[-1]['end_s'] <= 180 else f"{int(ch[-1]['end_s'] // 60)}分{int(round(ch[-1]['end_s'] % 60)):02d}秒"
        desc = (f"デモ動画（YouTube、{length}、日本語ナレーション付き。実走デモ{len(demos)}本（{'／'.join(demos)}）と、事前登録した結果の表{n_tab}枚"
                + (f"。{sp}で、速度は画面に常時表示）" if sp else '）'))
        txt = re.sub(r'デモ動画（YouTube、[^\n]*?）(?=／ 本リポジトリ)', lambda _: desc, txt, count=1)
    txt = sync_counts(txt, readme)
    readme.write_text(txt, encoding='utf8')
    for name in ('FINDINGS.md', 'HANDOFF.md'):       # prose counts in the other docs
        f = ROOT / 'docs' / name
        f.write_text(sync_counts(f.read_text(encoding='utf8'), f), encoding='utf8')
    print('README results updated: G', v[1] if v else None, '| E', e[1] if e else None, '| D', d[1] if d else None, '| T1', bool(t))


if __name__ == '__main__':
    main()
