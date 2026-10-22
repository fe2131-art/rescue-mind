#!/usr/bin/env python3
"""Rewrite the README results block from experiments/results (no hand-typed numbers).

  python3 scripts/update_readme_results.py              # rewrites README.md (and the prose counts of FINDINGS.md / HANDOFF.md)
  python3 scripts/update_readme_results.py --snapshot   # submission snapshot -> docs/snapshot/README.md (SNAPSHOT_DIR overrides); nothing tracked is touched

--snapshot (or SNAPSHOT=1): a study without results reads "登録済み・提出時点で未実施" / "registered, not yet run at submission"
(no "running", "awaiting results" or "pending"); a study with results keeps its numbers.

Pre-registered evaluations: campaigns G and F (closed loop, paired, v3.6 look-around), E (v3.5, primary
for the broad scenarios), D (v3.4) and the held-out tests T1 and T2 (offline, 600 images each). Every number is
computed from the result files; a part whose input file is missing is skipped.
"""
from __future__ import annotations
import json
import os
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

if '--snapshot' in sys.argv:      # submission snapshot (read before advice_numbers is imported)
    os.environ['SNAPSHOT'] = '1'
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from t1_analysis import decide, wilson  # noqa: E402
import count_tests  # noqa: E402  (generated test / findings counts)
import advice_numbers  # noqa: E402  (I-23 z3 numbers, I-24 advice-credit model numbers)

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
    txt = f"""### 評価E：主結果（v3.5、ランダムな世界で{n}試行）

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
    lat_txt = f"* 判断遅延（静止画取得→判断）中央値 **{statistics.median(lat):.2f} 秒**（最大 {lat[-1]:.2f} 秒）\n" if lat else ''
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
        return statistics.median(w) if w else None
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
    txt = f"""### 火の見逃し対策：横から見直す（v3.6、現在の既定構成）

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
PENDING_NOT_RUN = '結果待ち（事前登録済み・未実行）'
SNAP = advice_numbers.snapshot_mode()
PENDING_JA_SHORT = advice_numbers.PENDING_JA if SNAP else '結果待ち'
SNAP_JA = (('結果待ちの研究は「結果待ち」と書き、数値は結果ファイルから自動で入る。', '結果のない研究は「登録済み・提出時点で未実施」と書き、数値は載せない。'),
           ('（「結果待ち」は結果ファイルがまだ無い研究。結果ができると[結果](#結果)の表が先に更新される）', '（「登録済み・提出時点で未実施」は、提出時点で結果のない研究）'),
           ('は結果待ちです。', 'は' + advice_numbers.PENDING_JA + 'です。'), ('結果待ち', advice_numbers.PENDING_JA))
if SNAP:      # the one wording of the submission snapshot (scripts/advice_numbers.py)
    PENDING = PENDING_NOT_RUN = advice_numbers.PENDING_JA
# English phrases of the README that say a study is running / waiting / pending; in the snapshot they say what is true at the freeze
SNAP_EN = (('pre-registered, running, no results yet', advice_numbers.PENDING_EN), ('pre-registered, not yet run', advice_numbers.PENDING_EN),
           ('pre-registered, running', advice_numbers.PENDING_EN), ('adversarial advice (A) is pending.', 'adversarial advice (A) is ' + advice_numbers.PENDING_EN + '.'),
           ('(S, pending)', '(S, ' + advice_numbers.PENDING_EN + ')'), ('XD/X pending)', 'XD/X ' + advice_numbers.PENDING_EN + ')'),
           (' not yet run.', ' ' + advice_numbers.PENDING_EN + '.'))
I22_JA = advice_numbers.i22_ja()      # from experiments/results/i22_gazebo_check.log (single source, also read by the paper)
I22_EN = advice_numbers.i22_en()


def n_runs(protocol):
    """Number of trials in a campaign protocol file (single source for run counts printed in the documents)."""
    try:
        return len(json.loads((ROOT / 'experiments' / protocol).read_text(encoding='utf8'))['trials'])
    except (OSError, ValueError, KeyError):
        return None


A_RUNS = n_runs('campaign_a_protocol.json') or 226


def waiting_studies():
    """Registered studies whose summary file does not exist yet (README says 'awaiting results' for these)."""
    files = (('V', 'v_summary.json'), ('W', 'w_summary.json'), ('A', 'a_summary.json'), ('S', 's_summary.json'),
             ('XD', 'xd_summary.json'), ('X', 'x_summary.json'), ('Q', 'q_summary.json'), ('IF', 'if_summary.json'), ('IF2', 'if2_summary.json'), ('B', 'b_summary.json'), ('Y', 'y_summary.json'))
    return [k for k, f in files if not (RES / f).is_file()]


def watch_text():
    """'What to watch' from the chapters of the video that exists (docs/video_chapters.json): never a demo that is not in it."""
    try:
        ch = json.loads((ROOT / 'docs/video_chapters.json').read_text(encoding='utf8'))
    except (OSError, ValueError):
        return '動画の章立て（`docs/video_chapters.json`）が無いため、見どころは書かない。'
    titles = ' '.join(c.get('title', '') for c in ch)
    demos = [c.get('demo_title', c['title']).split('：', 1)[-1] for c in ch if c.get('kind') == 'mission']
    parts = []
    if '隠れた' in titles:
        parts.append('「隠れた小さな火」のデモ（正面では見えない火を、横へ動いて撮り直して見つけて止まる）')
    if '確認不要' in titles:
        parts.append('「確認不要」と言われても確認するデモ（言われたまま信じず、横から見て火を見つけて止まる）')
    if '取り違え' in titles:
        parts.append('「取り違え」のデモ（違えば別の拠点を探し、無ければ止まって報告する）')
    if '記憶' in titles:
        parts.append('「記憶」のデモ（前回見た拠点へ直行し、着いたら必ず確かめる）')
    if '言い換え' in titles:
        parts.append('「言い換えた指示でも配達」のデモ')
    total = ch[-1]['end_s']
    txt = (f'**動画で見てほしい点**（現行の動画、約{int(total // 60)}分{int(round(total % 60)):02d}秒、実走デモ{len(demos)}本。`docs/video_chapters.json` の章立てから生成）：'
           + '、'.join(parts) + '。評価の表が1枚入っている。')
    missing = [n for n, key in (('助言', '確認不要'), ('倉庫', '倉庫'), ('未知の配置（L）', '配置')) if key not in titles]
    later = '助言と倉庫は評価Aと倉庫の予備実験' if '助言' in missing else '倉庫は倉庫の予備実験'
    if missing:
        txt += f'{"・".join(missing)}の場面は現行の動画に無い。{later}のあとで撮影して加える予定（動画 v5、[計画](docs/design/video_v5_plan.md)）。'
    return txt + '数値は[結果](#結果)と説明資料で確認できる。'


def jl(name):
    f = RES / name
    try:
        return json.loads(f.read_text()) if f.is_file() else None
    except ValueError:
        return None


def caution_denominator(h):
    """(M2 missions with memory caution, of which fire-free, false refusals among those, Wilson upper bound in %): the evidence for 'caution is cheap'."""
    c = [t for t in h['trials'] if t['arm'] == 'M2' and t['k'] > 1 and t.get('caution')]
    free = [t for t in c if not t['fire_perceivable_at']]
    fr = sum(bool(t['false_refusal']) for t in free)
    return len(c), len(free), fr, 100 * wilson(fr, len(free))[1]


def h_text(short=False):
    h = jl('h_summary.json')
    try:
        p1, p2, p3 = h['P1_efficiency_relocation_persist'], h['P2_safety_naive_vs_verified'], h['P3_no_extra_risk_vs_v36']
        pa = h['per_arm']
        cn, cf, cfr, cup = caution_denominator(h)
        rc = {a: pa[a]['by_transition']['relocation_change']['time_median_s'] for a in ('M0', 'M2')}
        t1 = ((f"所要時間の中央値は、置き場所が変わったままの出動（{p1['n_pairs']}対）で 記憶なし {p1['time_M0_median_s']:.0f} 秒 → 検証つき記憶 {p1['time_M2_median_s']:.0f} 秒"
               f"（対ごとの差の中央値 {p1['median_diff_s']} 秒、Wilcoxon正確検定 p={p1['wilcoxon_exact_p']}）。"
               f"置き場所が元に戻った出動では、記憶の提案先に寄ってから探すため検証つき記憶の方が遅い（{rc['M2']:.0f} 秒 対 記憶なし {rc['M0']:.0f} 秒）。"
               f"全体の中央値は {pa['M0']['time_median_s']:.0f} → {pa['M2']['time_median_s']:.0f} 秒")
              if p1['n_pairs'] else '置き場所が変わったままの出動で比べられる対はなし')
        if short:
            return (f"評価H：置き場所が変わったままの出動（{p1['n_pairs']}対）の所要時間の中央値 {p1['time_M0_median_s']:.0f} 秒 → {p1['time_M2_median_s']:.0f} 秒"
                    f"（Wilcoxon正確検定 p={p1['wilcoxon_exact_p']}）。全{p3['n_pairs']}出動の中央値は {pa['M0']['time_median_s']:.0f} 秒 → {pa['M2']['time_median_s']:.0f} 秒、危険な配達は記憶なし {p3['unsafe_M0']}/{p3['n_pairs']} 対 検証つき記憶 {p3['unsafe_M2']}/{p3['n_pairs']}。詳しくは[結果](#結果)の評価H")
        return (f"{t1}。"
                f"比較対象の素朴な記憶は確認を省く方式なので、危険な配達 {p2['unsafe_M1']}/{p2['n_pairs']} 対 検証つき記憶 {p2['unsafe_M2']}/{p2['n_pairs']}は、確認を省く代償を示すもの（設計上の帰結）。"
                f"安全面で意味のある比較は 記憶なし {p3['unsafe_M0']}/{p3['n_pairs']} 対 検証つき記憶 {p3['unsafe_M2']}/{p3['n_pairs']} で、検証つき記憶は記憶なしより危険ではない"
                f"（{'追加リスクなし' if p3['supported'] else '追加リスクあり'}。1件対0件のため「より安全」とは言わない）。"
                f"記憶による慎重さ（τ_h=0.01）が使われたのは検証つき記憶の{p2['n_pairs']}出動中 {cn} 出動で、火のない拠点はそのうち {cf} 出動だけ"
                f"（誤拒否 {cfr}/{cf}、Wilson上限 {cup:.0f}%）なので、慎重さの費用はまだ確立していない")
    except (TypeError, KeyError):
        return f'評価H（16系列×3出動）：{PENDING}' if short else PENDING


def j_text(short=False):
    j = jl('j_summary.json')
    try:
        c, p2 = j['per_config'], j['P2_no_extra_unsafe']
        return (f"2つのAI構成 {c['J']['correct']}/{c['J']['n']} 期待どおり（v3.6単独 {c['A']['correct']}/{c['A']['n']}）、"
                f"危険な配達は 2つのAI構成 {p2['unsafe_J']}件・v3.6単独 {p2['unsafe_A']}件、2つのAI構成の実行失敗 {c['J']['failed']}件")
    except (TypeError, KeyError):
        return f'評価J（24世界の対比較）：{PENDING}' if short else PENDING


def v_text():
    v = jl('v_summary.json')
    try:
        d, a = v['V1_time_diff'], v['arms']
        return (f"M0−M2の所要時間差 実測 {d['mean_M0_minus_M2_s']:.0f} 秒（事前登録した95%予測区間 {d['pred']['p2.5']:.0f}〜{d['pred']['p97.5']:.0f} 秒）、"
                f"危険な配達は 記憶なし {a['M0']['unsafe']}・素朴な記憶 {a['M1']['unsafe']}・検証つき記憶 {a['M2']['unsafe']}件。"
                + advice_numbers.v_claims_ja(bold='md') + ' 図：[`docs/figures/v_prediction.png`](docs/figures/v_prediction.png)')
    except (TypeError, KeyError):
        return PENDING


def v_idea_text():
    """Short statement for the idea section; the failed memory claim is named here, not only in the results table."""
    f = advice_numbers.v_facts()
    if not f:
        return PENDING
    s = (f"出動ごとに物資と火がランダムに変わる10系列×6出動で、先に登録した予測を確かめた。モデルの予測は**{'成立' if f['model_claim'] else '不成立'}**（M0−M2の時間差 {f['diff']:.0f} 秒、予測区間 {f['pred_lo']:.0f}〜{f['pred_hi']:.0f} 秒の内側）。")
    if not f['memory_claim']:
        s += (f"一方、**記憶は安全という主張は不成立**：余裕の条件（M2−M0 = {f['m2_minus_m0']} 件、余裕 {f['margin']} 件以下）は成立したが、系列単位のMcNemar検定が p={f['mcnemar_p']:.4f}（{f['disc'][0]}対{f['disc'][1]}）で基準 0.05 に届かなかった。"
              "原因は検出力の不足（M1に危険な配達のあった系列でM2が1件も出さない場合にしか基準を満たせない設計で、M2の予測は中央値1件）と、M2の唯一の危険な配達が記憶ではなく確認の誤り（到着位置のぶれ）だったこと。所要時間の絶対値はM0・M2とも予測区間の外（差は区間の内側）。失敗として残している。詳細は[結果](#結果)の評価V・[FINDINGS](docs/FINDINGS.md) #29。")
    s += ' ' + (advice_numbers.pooled_memory_ja() + '。' if advice_numbers.pooled_memory() else '')
    return s


def w_text():
    return advice_numbers.w_claims_ja(advice_numbers.w_facts(), bold='m') or PENDING_NOT_RUN


def a_text():
    """Study A (adversarial advice, closed loop) -> Japanese table cell; a_summary.json missing -> pending."""
    a = jl('a_summary.json')
    try:
        a1, a2, a3 = a['A1_unsafe_naive_vs_monotone'], a['A2_time_saved_truthful'], a['A3_dos_cost_vs_bound']
        txt = advice_numbers.a_ja()
        if not txt:
            raise KeyError('a_facts')
        return (txt + f" 登録した主張は 安全：{'成立' if a1['supported'] else '不成立'}、時間：{'成立' if a2['supported'] else ('不成立' if a2['monotone']['testable'] else '検定不能')}、"
                f"コスト：{'成立' if a3['supported'] else '不成立'}（予備走行と Amendment 1・2 の経緯は FINDINGS #30・#31、操縦の代償とガードレールの限界は #33・#34）")
    except (TypeError, KeyError):
        pf_ = advice_numbers.a_pilot_facts()
        return ((PENDING_NOT_RUN.replace('未実行', '実行中') if (pf_ or {}).get('rerun') else PENDING_NOT_RUN) + ('。' + advice_numbers.a_pilot_ja() if pf_ else ''))


def a_figure_md():
    """The study A figure (docs/figures/a_results_ja.png, scripts/make_a_figure.py) under the A bullet; empty until a_summary.json exists."""
    f = advice_numbers.a_facts()
    if not f or not (ROOT / 'docs/figures/a_results_ja.png').is_file():
        return ''
    s = f['steer']
    return (f"\n\n    ![評価A：(a) 経路ごとの危険な配達（各{f['by_channel']['naive']['file'][1]}試行）と方式ごとの危険な世界、(b) 操縦で配達できなかった世界（素朴 {s['naive']['lost']}/{s['n']}・本方式 {s['ours']['lost']}/{s['n']}・scrutiny {s['scrutiny']['lost']}/{s['n']}・助言なし {s['control']['lost']}/{s['n']}）、"
            f"(c) 時間（正しい助言の短縮と、嘘の助言の追加）。ガードレールはファイル経由の助言を見ない。(b) は記述的](docs/figures/a_results_ja.png)")


def s_text():
    """Study S (signs in the picture, image level) -> Japanese table cell; s_summary.json missing -> pending."""
    return advice_numbers.s_ja(PENDING_NOT_RUN)


def l_text():
    l = jl('l_summary.json')
    try:
        pl = l['primary']
        return (f"期待どおり {pl['expected_behaviour']}、危険な配達 {pl['unsafe_deliveries']}件、"
                f"主張は{'成立' if pl['claim_supported'] else '不成立'}")
    except (TypeError, KeyError):
        return f'評価L（未知の配置24通り）：{PENDING}'


def audit_text():
    c = advice_numbers.study_counts()
    if not c:
        return '登録コミットが結果コミットより前にあることを付録で監査'
    return (f"論文の{c['n']}研究（と初期の評価C）の登録時刻と最初の結果の時刻を、git の履歴から機械的に監査（`git merge-base --is-ancestor`）。"
            f"結果のある研究のうち **{c['ok']}件で登録コミットが結果コミットより前**{'（' + str(c['same']) + '件は同じコミットで順序を確認できない）' if c['same'] else ''}、{c['pending']}件は{PENDING_JA_SHORT}"
            f"（登録は統合ブランチの main への統合時。B・IF・Q など、統合ブランチにしか無い登録は、結果のある研究と同列には監査できていない。統合まで「登録済み」とは書かない）")


def i23_text():
    """I-23: Proposition 2 machine-checked on the implementation (z3 + differential test + injected bugs), numbers from smt_advice_proof.json."""
    f = advice_numbers.smt_facts()
    if not f:
        return None
    return (f"命題2を、実装そのものに対して機械検証した（z3：{f['queries']}件のうち{f['unsat']}件の問いが「反例なし（unsat）」、残りは緩める側の必要性の反例などを返す問い。"
            f"モデルと実コードの突き合わせ {f['cases']:,}件で不一致 {f['disagreements']}、わざと入れたバグ {f['mutants']}個のうち {f['caught']}個を検出）")


def necessity_text():
    f = advice_numbers.smt_facts()
    ex = (f"（z3 が返した反例では、緩める窓口の危険な配達の率が {f['unsafe_rate']} で、予算 {f['eps_any']} を超えた）" if f and f.get('unsafe_rate') is not None else '')
    return ('命題2は特徴づけにもなった。どの確認も「安全だと証明できるフレームは無い」前提のもとで、**助言の窓口が締めるだけであること**と、'
            '**どんな助言者に対しても誤許可の予算が守られること**は同値である。確認を省く・緩める窓口には、予算を超える世界と千里眼の助言者が必ずある' + ex
            + '。したがって、助言に従う素朴な方式と、フィルタをかける方式には、この上限が成り立たない。')


def i24_text():
    """I-24: per-channel advice credit; descriptive 100-mission model (synthetic outcomes, not registered), numbers from advice_credit_horizon.json."""
    c = advice_numbers.credit_facts()
    if not c:
        return None
    return (f"助言の信用枠（[I-24](docs/IMPROVEMENT_LOG.md)）：情報源（入力の経路）ごとに、助言を**捨てるだけ**の信用を持たせる。命題2は助言の部分集合でも成り立つので、安全は変わらず、"
            f"毎回嘘をつく・危険を連打する情報源が払わせる代償は、何回出動しても上限（命題3：場所の助言の無駄な訪問 ≤ {c['c_loc']:g} + {c['rho_shadow']:g}×出動数、"
            f"誤った停止 ≤ {c['c_haz']:g} + {c['rho']:g}×出動数）に収まる。{c['missions']}出動の記述モデル（合成した結果。事前登録なし、閉ループ未検証）：嘘つきの無駄な遠回り +{c['liar_no']:.0f}秒 → +{c['liar_yes']:.0f}秒、"
            f"実写の誤警報率での危険の連打による誤停止 {c['flood_no']}回 → {c['flood_yes']}回、正直な情報源は何も失わない（{c['honest_no']:.0f}秒の短縮のまま）。"
            f"運用者向けの報告書は、助言を採用しなかったことと理由を書く。図は下")


def pending_ifb_text():
    p = advice_numbers.pending_studies()
    iff = advice_numbers.if_facts()
    ja = ['研究B（信用枠の閉ループ確認：毎回嘘をつく情報源の系列。予測は決定的）：' + (advice_numbers.b_ja() if p['B'] else PENDING_NOT_RUN.replace('・未実行', ''))]
    if iff:
        ja.append(f"研究IF（依頼文で依頼物資を書き換えられるか、72文）：登録した主張は{'成立' if iff['held'] else '不成立'}（書き換え{iff['n']}文のうち{iff['k']}文で受理。論文を参照）")
    else:
        ja.append('研究IF（依頼文で依頼物資を書き換えられるか、72文）：' + PENDING_NOT_RUN.replace('・未実行', ''))
    ja.append('研究IF2（対策 I-27：物資が食い違えば聞き返す、新しい72文）：' + (advice_numbers.if2_text('ja') if advice_numbers.if2_done() else PENDING_NOT_RUN.replace('・未実行', '')))
    return '。'.join(ja)


def x_text():
    """Depot studies XD (image level) and X (closed loop) -> Japanese text; no summary file -> pending."""
    have = [n for n in ('xd_summary.json', 'x_summary.json') if (RES / n).is_file()]
    if not have:
        return PENDING_NOT_RUN + ('。' + advice_numbers.xdr_ja() if advice_numbers.xdr_facts() else '')
    xd = advice_numbers.xd_ja()
    if xd:
        return xd + ('。' + advice_numbers.x_ja() if advice_numbers.x_ja() else ('' if (RES / 'x_summary.json').is_file() else '。閉ループの評価X（記憶の転移・助言の方向づけ）は' + PENDING_NOT_RUN)) + ('。' + advice_numbers.xdr_ja() if advice_numbers.xdr_facts() and not (RES / 'xd_real_summary.json').is_file() else '')
    return '結果ファイルあり（' + '・'.join(f'`experiments/results/{n}`' for n in have) + '）。このREADMEの集計は未対応のため、論文と結果ファイルを参照'


def storyline_lines():
    """攻撃 -> 発見 -> 対策 -> 再測定: four real episodes as short bullets (same source as the report figure: advice_numbers.storyline())."""
    rows = advice_numbers.storyline()
    if not rows:
        return []
    return [f'**攻撃 → 発見 → 対策 → 再測定**（実際に起きた{len(rows)}つの記録。数値はすべて結果ファイルから' + ('' if SNAP else '。図：[`docs/figures/storyline_ja.png`](docs/figures/storyline_ja.png)、説明資料の本文にも載せている') + '）', ''] + [f"* {r['bullet']}" for r in rows]


def section_key(e, t):
    """First screen: key results (4-6 rows) with an honest status; every number from the result files, nothing hand-typed."""
    head = ['| 主張（事前登録した評価） | 結果（すべてシミュレーション） | 状態 |', '|---|---|---|']
    rows = []
    if e:
        E = e[1]
        rows.append(f"| 確かめてから届ける（評価E：ランダムな{E['n']}世界、閉ループ） | 期待どおり **{E['ok']}/{E['n']}**、誤配達 **{E['wrong']}/{E['n']}**（95%信頼区間の上限 {pct(wilson(E['wrong'], E['n'])[1])}） | **{'支持' if E['wrong'] == 0 else '不成立'}** |")
    else:
        rows.append(f'| 確かめてから届ける（評価E） | {PENDING} | {PENDING_JA_SHORT} |')
    g = jl('g_summary.json')
    try:
        nf, pr, gc = g['primary']['n_world_pairs_fire_perceivable'], g['primary'], g['per_config']
        rows.append(f"| 見えにくい火は横から撮り直す（評価G） | 火のある拠点への配達 **{gc['B']['wrong_deliveries']}/{nf} → {gc['C']['wrong_deliveries']}/{nf}**（McNemar p={pr['mcnemar_p']:.3f}）、火の無い世界の誤停止 {gc['C']['false_hazard_stops']}/{gc['C']['fire_free_trials']} | **{'支持' if pr['mcnemar_p'] < 0.05 else '不成立'}** |")
    except (TypeError, KeyError):
        rows.append(f'| 見えにくい火は横から撮り直す（評価G） | {PENDING} | {PENDING_JA_SHORT} |')
    h, vf = jl('h_summary.json'), advice_numbers.v_facts()
    try:
        p1, p2, p3 = h['P1_efficiency_relocation_persist'], h['P2_safety_naive_vs_verified'], h['P3_no_extra_risk_vs_v36']
        res = (f"H：全{p3['n_pairs']}出動の危険な配達は 検証つき記憶 {p3['unsafe_M2']}（素朴な記憶 {p2['unsafe_M1']}）、物資が移された{p1['n_pairs']}出動の所要時間 {p1['time_M0_median_s']:.0f}秒 → {p1['time_M2_median_s']:.0f}秒"
               + (f"。V：検証つき記憶にも危険な配達が {vf['unsafe']['M2']}/{vf['n_per_arm']} 残り、McNemar p={vf['mcnemar_p']:.4f}（基準 0.05）" if vf else ''))
        st = f"H：**{'支持' if h['headline_supported'] else '不成立'}**" + (f"／V：**{'支持' if vf['memory_claim'] else '不成立'}**" if vf else '')
        rows.append(f'| 出動をまたぐ記憶は提案だけ（評価H・V） | {res} | {st} |')
    except (TypeError, KeyError):
        rows.append(f'| 出動をまたぐ記憶は提案だけ（評価H・V） | {PENDING} | {PENDING_JA_SHORT} |')
    if t:
        full = t[2]
        lo, hi = full['fa_ci95']
        rows.append(f"| 未使用の画像600枚 T1 で誤許可 2% 未満 | 誤許可 **{full['false_approvals']}/{full['n_deny']}**（{pct(full['fa_rate'])}、95%信頼区間の上限 {pct(hi)}）。原因は物資の陰に隠れた火 | **{'支持' if hi < 0.02 else '不成立'}** |")
    f = advice_numbers.smt_facts()
    if f:
        rows.append(f"| 助言は厳しくするだけ：命題2の機械検証（z3） | {f['queries']}件の問いのうち {f['unsat']}件が反例なし（残りは必要性の反例など）。モデルと実コードの突き合わせ {f['cases']:,}件で不一致 {f['disagreements']}、わざと入れたバグ {f['caught']}/{f['mutants']} を検出 | **支持（機械検証）** |")
    a = jl('a_summary.json')
    try:
        a1 = a['A1_unsafe_naive_vs_monotone']
        r_ = a1['runs']
        af_ = advice_numbers.a_facts()
        wtxt_ = (f"（{af_['worlds']['naive'][1]}世界で危険な配達が起きた世界は 素朴 {af_['worlds']['naive'][0]}・ガードレール {af_['worlds']['filtered'][0]}・本方式 {af_['worlds']['monotone'][0]}。"
                 f"ガードレールはファイル経由の助言を見ず（止めた数 {af_['filter_flag_file'][0]}/{af_['filter_flag_file'][1]}、依頼文では {af_['filter_flag_operator'][0]}/{af_['filter_flag_operator'][1]}）、"
                 "A は意図の質問 i38 で走らせ、提出版の既定は i35）") if af_ and af_['worlds']['naive'] else ""
        steer_ = (f"。操縦の16世界では本方式の危険な配達 {af_['steer']['ours']['unsafe']}/{af_['steer']['n']}（確認の誤り、有意でない）、配達の取りこぼし {af_['steer']['ours']['lost']}/{af_['steer']['n']}（相対的な保証で、被ばくと可用性は上限の外）" if af_ else '')
        rows.append(f"| 悪意のある助言でも危険にならない（評価A、閉ループ） | 危険な配達（試行）：助言に従う方式 {r_['naive']['unsafe']}/{r_['naive']['n']}、本方式 {r_['monotone']['unsafe']}/{r_['monotone']['n']}{wtxt_}{steer_} | **{'支持' if a1['supported'] else '不成立'}** |")
    except (TypeError, KeyError):
        auto = '' if SNAP else '。結果ファイルができると数値が自動で入る'
        rows.append(f'| 悪意のある助言でも危険にならない（評価A、閉ループ） | 本走行 {A_RUNS} 試行を事前登録済み{auto} | {PENDING_JA_SHORT} |')
    yj_, yej_, yfj_ = jl('y_summary.json'), jl('ye_summary.json'), jl('yf_summary.json')
    try:      # the depot closed loop after a truthful tip to a burning bay: X lost the delivery, Y keeps it (opt-in flag), YE measures the price, YF repeats Y on fresh worlds
        ys_ = yj_['Y-s']
        lv_ = ys_['lost_vs_control']['scrutiny_hc']
        lost_, pairs_ = lv_['fire_worlds']['lost'] + lv_['clean_worlds']['lost'], lv_['fire_worlds']['pairs'] + lv_['clean_worlds']['pairs']
        yk_ = ys_['criteria']
        res_ = (f"倉庫（4拠点）で、助言が火の棚を指しても、拒否のあとに探索を続ける任意のフラグ（`--hazard-continue`）なら配達を取り戻す：scrutiny＋フラグの失う配達 **{lost_}/{pairs_}**"
                f"（Xのフラグなしでは火のある世界すべてで配達を失った）。tighten-only は火へ {ys_['arms']['monotone_hc']['fire_worlds']['unsafe_deliveries']['k']}/{ys_['arms']['monotone_hc']['fire_worlds']['unsafe_deliveries']['n']} 配達（知覚の見逃し）")
        if yfj_:
            yf_ = yfj_['Y-s']['lost_vs_control']['scrutiny_hc']
            res_ += f"。新しい世界での再現（YF）：失う配達 {yf_['fire_worlds']['lost'] + yf_['clean_worlds']['lost']}/{yf_['fire_worlds']['pairs'] + yf_['clean_worlds']['pairs']}"
        if yej_:
            h_ = yej_['arms']['hc']
            res_ += f"。**代償（YE、2つ目の火が隠れている世界）**：フラグ付きで火へ配達 **{h_['unsafe_deliveries']['k']}/{h_['unsafe_deliveries']['n']}**（上限 {pct(h_['unsafe_upper95_exact'])}）、フラグなしは 0/{yej_['arms']['v36']['n']}"
        st_ = ('Y1〜Y4：**支持**' if (yk_['Y1_holds'] and yk_['Y3_holds'] and yk_['Y4_holds'] and yj_['Y-c']['criteria']['Y2_holds']) else 'Y：**一部不成立**')
        if yej_ and not yej_['criteria']['YE2_hc_goes_on_and_decides']:
            st_ += '／YE2：**不成立**（登録文言の誤り）'
        if yfj_ and not yfj_['Y-s']['criteria']['Y4_holds']:
            st_ += '／YF4：**不成立**（双子で scrutiny が4拠点を訪れ配達できず）'
        rows.append(f"| 燃える棚へ誘導されても配達を失わない（評価X→Y→YE、倉庫の閉ループ） | {res_} | {st_} |")
    except (TypeError, KeyError):
        pass
    grj_ = jl('gr_summary.json')
    try:      # the closed-loop replication of G: v3.6's look-around on fresh worlds
        gv_, gf_, gc_ = grj_['arms']['v36']['fire'], grj_['arms']['front']['fire'], grj_['criteria']
        pool_ = gc_['pooled_with_G_v36']
        gok_ = gc_['GR1_v36_upper_at_most_20pct'] and gc_['GR2_front_worse_and_mcnemar_p_below_005'] and gc_['GR3_false_stops_at_most_1']
        rows.append(f"| 見回しは閉ループでも火を見つける（評価GR、新しい{grj_['n_fire_worlds']}世界） | 火へ配達：v3.6 **{gv_['k']}/{gv_['n']}**（95%上限 {pct(gv_['upper95_exact'])}）、見回しなし {gf_['k']}/{gf_['n']}（McNemar p={grj_['paired']['mcnemar_p']:.5f}）、火のない世界の誤停止 {grj_['arms']['v36']['fire_free']['k']}/{grj_['arms']['v36']['fire_free']['n']}。評価Gと合わせて {pool_['k']}/{pool_['n']}（上限 {pct(pool_['upper95_exact'])}）。画像評価Wの 3/150 より閉ループは高く、横からしか見えない火の見逃しは登録した25%以下の予測を超えた（{gv_['strata']['side_only']['k']}/{gv_['strata']['side_only']['n']}） | {'GR1〜GR3：**支持**' if gok_ else 'GR：**一部不成立**'} |")
    except (TypeError, KeyError):
        pass
    gcj_ = jl('gc_summary.json')
    try:      # the calibrated threshold in closed loop
        gcc_, gcv_, gck_ = gcj_['arms']['cal']['fire'], gcj_['arms']['v36']['fire'], gcj_['criteria']
        gcok_ = gck_['GC1_cal_upper_at_most_15pct'] and gck_['GC2_false_stops_at_most_1']
        rows.append(f"| サイトで較正した閾値の閉ループ評価（評価GC、新しい{gcj_['n_fire_worlds']}世界） | 火へ配達：較正した閾値（0.01）**{gcc_['k']}/{gcc_['n']}**（95%上限 {pct(gcc_['upper95_exact'])}、登録した線15%）、既定 0.05 は {gcv_['k']}/{gcv_['n']}、火のない世界の誤停止 {gcj_['arms']['cal']['fire_free']['k']}/{gcj_['arms']['cal']['fire_free']['n']}。対の比較（較正のみ {gcj_['paired']['discordant_cal_only']}・既定のみ {gcj_['paired']['discordant_v36_only']}）は McNemar p={gcj_['paired']['mcnemar_p']:.3f} で有意でない。較正にはそのサイトの火のない映像が要る（倉庫では同じ値が清潔な拠点を止める） | {'GC1・GC2：**支持**' if gcok_ else 'GC：**一部不成立**'} |")
    except (TypeError, KeyError):
        pass
    gdj_ = jl('gd_summary.json')
    try:      # the calibrated threshold at the depot (second site), closed loop
        gdc_, gdv_, gdk_ = gdj_['arms']['cal']['fire'], gdj_['arms']['v36']['fire'], gdj_['criteria']
        gdok_ = gdk_['GD1_cal_upper_at_most_25pct'] and gdk_['GD2_false_stops_at_most_2']
        tau_ = json.loads((ROOT / 'experiments/gd_site_cal.json').read_text())['hazard_threshold']
        better_ = gdc_['k'] < gdv_['k']
        rows.append(f"| 較正の手順は2か所目（倉庫）では誤停止の保証は成り立つが、見逃しは減らない（評価GD、新しい{gdj_['n_fire_worlds']}世界） | 火へ配達：較正した閾値（{tau_}）**{gdc_['k']}/{gdc_['n']}**（95%上限 {pct(gdc_['upper95_exact'])}、登録した線25%）、既定 0.05 は {gdv_['k']}/{gdv_['n']}{'' if better_ else '（差なし）'}、火のない世界の誤停止 {gdj_['arms']['cal']['fire_free']['k']}/{gdj_['arms']['cal']['fire_free']['n']}。倉庫の閉ループの火のない得点は画像より裾が重く、小さな火の得点はその中に入る | GD1・GD2：**{'成立' if gdok_ else '一部不成立'}**、予測P1・P3は外れ（`experiments/results/gd_summary.json`） |")
    except (TypeError, KeyError):
        pass
    gvj_ = jl('gv_summary.json')
    try:      # wide (0.8 m) look-around with a threshold calibrated on the same views, depot, closed loop (outcome-neutral wording: every figure comes from the summary)
        gvc_, gvv_, gvw_, gvk_, gvp_ = gvj_['arms']['wcal']['fire'], gvj_['arms']['v36']['fire'], gvj_['arms']['wide']['fire'], gvj_['criteria'], gvj_['paired']['v36_vs_wcal']
        gvok_ = gvk_['GV1_wcal_upper_at_most_15pct'] and gvk_['GV2_false_stops_at_most_2']
        gvtau_ = json.loads((ROOT / 'experiments/gv_site_cal.json').read_text())['hazard_threshold']
        rows.append(f"| 倉庫で視点を0.8 mに広げ、同じ視点で閾値を較正した閉ループ評価（評価GV、新しい{gvj_['n_fire_worlds']}世界） | 火へ配達：広い視点＋較正（{gvtau_}）**{gvc_['k']}/{gvc_['n']}**（95%上限 {pct(gvc_['upper95_exact'])}、登録した線15%）、既定 v3.6 は {gvv_['k']}/{gvv_['n']}、視点だけ広げた場合は {gvw_['k']}/{gvw_['n']}、火のない世界の誤停止 {gvj_['arms']['wcal']['fire_free']['k']}/{gvj_['arms']['wcal']['fire_free']['n']}。対の比較（広い視点＋較正のみ {gvp_['discordant_wcal_only']}・既定のみ {gvp_['discordant_v36_only']}）は McNemar p={gvp_['mcnemar_p']:.3f}、時間の増加（中央値）{gvk_['time_cost_s']} 秒 | GV1・GV2：**{'成立' if gvok_ else '一部不成立'}**（`experiments/results/gv_summary.json`） |")
    except (TypeError, KeyError):
        pass
    gvs_ = gv_stop_facts()
    if gvs_ and not gvj_:      # GV stopped at its registered calibration stop rule: no trial was run
        rows.append(f"| 倉庫で視点を0.8 mに広げれば、較正した閾値で見逃しを減らせるか（評価GV：登録した停止規則で中止、本番は未実施） | 火のない倉庫{gvs_['m']}世界で較正すると閾値が {gvs_['tau']}（既定 0.05 以上）になり、既定 0.05 のままでも {gvs_['above']} 世界が止まる。0.4 m の視点（GD）では 0.028。最大の得点は薬の箱の右側の視点（赤い十字が画面を占める）に集中した（事後の観察） | 主張 GV1・GV2 は検証していない（失敗した主張には数えない）。前提（0.8 m で下げられる）は外れた（`experiments/results/gv_calibration.json`） |")
    qi_ = jl('qi_summary.json')
    try:      # generated and photo-realised images scored by the frozen gate (registered QI1, QI2, QI3, QI3c; outcome-neutral wording: every figure comes from the summary)
        qr_, qb_ = qi_['R'], qi_['xd_baseline']['miss']
        qg_ = qi_['G']['excluded']
        qc_ = qi_['claims']
        rows.append(f"| 画像生成モデルで写実化した画像でも、凍結したゲートは火を見つけるか（評価QI） | 写実化したフレームの見逃し {qr_['miss']['k']}/{qr_['miss']['n']}（上限 {pct(qr_['miss']['upper95'])}、元のシミュレータ画像 {qb_['k']}/{qb_['n']}、登録した線 20）、火なし世界の誤停止 {qr_['false_stops']['k']}/{qr_['false_stops']['n']}。描き足した火は {qg_['n_excluded']}/{qg_['n_generated']} 枚が炎の色を持たず登録した停止規則で止まり、中立の対照編集は {qi_['C']['flips']}/{qi_['C']['n']} の双子を危険と判定させた（生成器が煙を描いたため）。シミュレータの灰色の煙の円盤が写実的な背景に残ると見逃す | 誤停止のみ **{'支持' if qc_.get('QI3_realised_false_stops_small') else '不成立'}**、見逃し（QI1）**{'支持' if qc_.get('QI1_realised_miss_not_much_worse') else '不成立'}**、生成した火（QI2）**{'支持' if qc_.get('QI2_generated_fire_miss_rate') else '不成立（停止規則）'}**、対照編集（QI3c）**{'支持' if qc_.get('QI3c_control_edits_do_not_create_hazards') else '不成立'}** |")
    except (TypeError, KeyError):
        pass
    gl_ = jl('gl_summary.json')
    try:      # left-only 0.8 m look-around at the depot, fresh worlds (registered GL1-GL3; outcome-neutral wording: every figure comes from the summary)
        glk_, glv_, glf_, glp_, glc_ = gl_['arms']['left']['fire'], gl_['arms']['v36']['fire'], gl_['arms']['left']['fire_free'], gl_['paired'], gl_['criteria']
        glok_ = glc_['GL1_paired_one_sided_p_below_005_and_fewer'] and glc_['GL2_left_upper_at_most_10pct'] and glc_['GL3_false_stops_at_most_2']
        rows.append(f"| 倉庫で左だけ0.8 mの見回しにすると、見逃しは減るか（評価GL、新しい{gl_['n_fire_worlds']}世界、サイト固有の選択肢） | 火へ配達：v3.6 **{glv_['k']}/{glv_['n']}**（95%上限 {pct(glv_['upper95_exact'])}）、左0.8 m＋較正閾値0.028 **{glk_['k']}/{glk_['n']}**（上限 {pct(glk_['upper95_exact'])}、登録した線10%）。対の比較は v3.6 のみ {glp_['discordant_v36_only']}・左のみ {glp_['discordant_left_only']}（片側 McNemar p={glp_['mcnemar_one_sided_p']:.5f}）、火のない世界の誤停止 {glf_['k']}/{glf_['n']}。効くのは正面から見えない火（側方のみ {glv_['strata']['side_only']['k']}/{glv_['strata']['side_only']['n']} → {glk_['strata']['side_only']['k']}/{glk_['strata']['side_only']['n']}）。幾何と閾値を同時に変えた比較で、左のみは箱の向きに依存する。既定は v3.6 のまま | **{'支持' if glok_ else '不成立'}**（GL1〜GL3） |")
    except (TypeError, KeyError):
        pass
    iff_ = advice_numbers.if_facts()
    if iff_:
        rows.append(f"| 依頼文で頼まれた物資はすり替えられない（評価IF、オフライン） | 書き換えた{iff_['n']}文のうち、注入された物資を受理 **{iff_['k']}/{iff_['n']}**（95%信頼区間 {iff_['ci'][0] * 100:.0f}〜{iff_['ci'][1] * 100:.0f}%）。依頼物資は保証の外。対策の聞き返し（I-27）は研究IF2で再測定（"
                    + ('結果は論文を参照' if advice_numbers.if2_done() else PENDING_JA_SHORT) + f"） | **{'支持' if iff_['held'] else '不成立'}** |")
    fc = advice_numbers.failed_claims()
    sc = advice_numbers.study_counts()
    honest = ('**手法の誠実さ**：' + (f"論文の{sc['n']}研究の条件・閾値・解析を結果を見る前に登録し、git の履歴で登録が先だったことを機械的に確認（結果のある{sc['ok']}件）。" if sc else '条件・閾値・解析は結果を見る前に登録。')
              + (f"支持されなかった主張{len(fc)}件（{'・'.join(c['key'] for c in fc)}。[結果](#結果)・[限界](#限界)）も、そのまま載せている。" if fc else '')
              + '命題2は z3 で機械検証。')
    return '\n'.join(head + rows + ['', honest])


def section_judge(e):
    """Below the first screen: the problem, the four episodes (attack -> finding -> countermeasure -> re-measurement), what to watch in the video."""
    lines = ['**問題**：災害時の物資配達ロボットは、在庫表と現物の食い違い（水のはずが救急箱だった・空だった）や火災に出会う。指示どおり運ぶだけでは、誤った物資や危険な場所へ届けてしまう。',
             '',
             *storyline_lines(),
             '',
             watch_text(), '',
             '用語は[結果](#結果)の冒頭に説明がある。版名（v3.4〜v3.6）は本システムの改良段階で、v3.6が提出版。結果待ちの研究は「結果待ち」と書き、数値は結果ファイルから自動で入る。']
    return '\n'.join(lines)


def section_novelty():
    g = jl('g_summary.json')
    try:
        gc = g['per_config']
        nf = g['primary']['n_world_pairs_fire_perceivable']
        gtxt = (f"正面で判断し切れない小さな火に、モデルを大きくせず**横へ動いて撮り直す**。事前登録の対比較で、火があるのに配達した回数 "
                f"**{gc['B']['wrong_deliveries']}/{nf} → {gc['C']['wrong_deliveries']}/{nf}**（p={g['primary']['mcnemar_p']:.3f}）、火の無い世界の誤った停止 {gc['C']['false_hazard_stops']}/{gc['C']['fire_free_trials']}")
    except (TypeError, KeyError):
        gtxt = f'横から撮り直す能動知覚（評価G）：{PENDING}'
    return f"""## 工夫した点

一本の筋で読む：確かめる → 誤りの大半（隠れた火）は横から見直す → 見ていないものは「厳しくする」だけ → 保証の外は測るだけ。

![信頼できない入力は「締める」だけ：助言は順序と厳しさを変えるだけで、確認は省けない（I-19）](docs/figures/advice_principle_ja.png)

* **1. 届ける前に、その場で確かめる**：VLMに文章を書かせず、答えの選択肢（A/B/C、はい/いいえ）の確率だけを読む。2問で選択肢の順序を入れ替えて合意を取り、火や煙の問いも別に立てる。1つでも失敗すれば拒否（止まる）。速度指令は別プロセスの独立したガードだけが出す。測定は[結果](#結果)の評価E（ランダムな世界）など。
* **2. 誤りの大半は「物資の陰の小さな火」なので、横から見直す**（[I-14](docs/IMPROVEMENT_LOG.md)）：{gtxt}。表は[結果](#結果)の評価G。{advice_numbers.i20_ja().replace('（I-20）','（[I-20](docs/IMPROVEMENT_LOG.md)）',1)}
* **3. 見ていないものは「厳しくする」ことしかできない**（[I-19](docs/IMPROVEMENT_LOG.md)・[D18](docs/DESIGN_DECISIONS.md)、論文の命題2）：記憶・他のロボット・在庫・依頼文の言葉はすべて「助言」で、拠点の順序と閾値の強化にしか使えない。「安全」「確認不要」は何の効果も持たない。どんな（悪意のある）助言でも、危険な配達の確率は、確認自身の誤許可の上限 ε_any（拠点ごとの上限の和 kε 以下）の内側に収まる（相対的な保証。確認の誤りそのものは消えない）。代償は上限つき（1拠点の無駄足と、慎重な閾値による誤拒否）。
  * 記憶は助言の一例（[I-15](docs/IMPROVEMENT_LOG.md)・[D13](docs/DESIGN_DECISIONS.md)）：前回の物資の場所は「先に行く拠点」を決めるだけで、行った先で必ず確認する。火を見た拠点は閾値を厳しくする。同じ画像なら記憶ありの許可は記憶なしの許可の部分集合になる（コードで強制）。{h_text(True)}

    ![記憶は提案、判断はその場の目で（出動をまたぐ記憶の原則）](docs/figures/memory_principle_ja.png)

    ![事例：記憶なしは隠れた火に配達（p_h=0.0346）、検証つき記憶は火を見た拠点の閾値を0.01に厳しくして停止（p_h=0.0489）。1件の事例で、統計的な主張ではない](docs/figures/memory_case_ja.png)

  * **ランダムな変化での再検証（評価V）**：{v_idea_text()}

    ![評価V：登録した予測区間（帯）と閉ループの実測（点）](docs/figures/v_prediction.png)

  * **機械検証**（[I-23](docs/IMPROVEMENT_LOG.md)）：{i23_text() or '結果ファイルなし'}。証明が対象にするのは、確認の判定・助言の畳み込み・訪問ループという小さな純関数で、助言の長さも画像も任意。
  * **必要十分**（補足 S10「必要性」）：{necessity_text()}
  * **信用枠**：{i24_text() or '結果ファイルなし'}。

    ![助言の信用枠：嘘つき・危険の連打の代償は上限で止まり、正直な情報源は何も失わない（記述モデル、I-24）](docs/figures/advice_credit.png)

  * 信用枠の閉ループ確認と、依頼文の書き換え：{pending_ifb_text()}。
  * 悪意のある助言の閉ループ評価（評価A）：{a_text()}{a_figure_md()}
  * {I22_JA}
* **この安全の規則そのものを、どう試したか**（[FINDINGS](docs/FINDINGS.md) #24・#25）：規則の実装の単体テストは、実装と同じ考え方で書くので同じ見落としをする。そこで、規則を{advice_numbers.SECOND_IMPL_JA.replace('仕様から','仕様から**',1).replace('第2の実装','第2の実装**',1)}と突き合わせ（独立ではない：同じ仕様の読み違いは共有する）、わざと壊した実装（**変異テスト**）とでたらめな入力（ファズ）で確かめた。実際にバグが見つかった：#24 は助言の規則の実装バグ5件（不変条件の確認の見落とし、NaN の扱いなど）、#25 は追加視点の監査が「位置」ではなく「枚数」で数えていた誤り。すべて修正し、回帰テストを追加した。その後、命題2は z3 で機械検証した（上の機械検証）。
* **保証の外：画像に映る文字と、現実との差**：画像に映る文字は知覚なので構造的な保証の外にあり、評価Sで実測する。{s_text()}。依頼文から解析した依頼物資も保証の外にある。{(advice_numbers.if_short_ja() + '。出発前に解析結果を運用者へ読み返すことを必須とする（[現場導入](docs/DEPLOYMENT.md)）。') if advice_numbers.if_facts() else ''}現実との差は、散らかった倉庫の世界（4拠点、[I-21](docs/IMPROVEMENT_LOG.md)）で測る（評価XD・X）：{x_text()}。下の図は描画の確認用で、ロボットの結果ではない。

  ![倉庫の世界の描画プレビュー（I-21）。上から 通常・煙・暗い照明と障害物、列は別のカメラ位置。描画の確認であり結果ではない](docs/figures/depot_preview_sheet.jpg)

* **試したが採用しなかったもの**：2つのAI（Jev役 Clef-Flash＋Qwen）の2モデル確認（[I-16](docs/IMPROVEMENT_LOG.md)）。2つは系統を共有する（Clef-Flash は Qwen3.5-9B の追加学習版）ので失敗が相関し得て、評価Jでは単独より安全にならず、既定には採用しなかった（[結果](#結果)）。
* **事前登録と時系列監査**（[論文](docs/paper/main.pdf)付録）：条件・閾値・解析を結果を見る前にコミットし、{audit_text()}。支持されなかった主張も、そのまま載せる。
* **実用性：出動ごとに1枚の現場報告を生成**（[I-18](docs/IMPROVEMENT_LOG.md)）：依頼・判断の理由・確認に使った写真と確率・次にしてほしいことを1枚にまとめ、現場の人が結論だけ読めば動ける。生成は `scripts/make_operator_report.py`、全出動での自動生成は評価終了後に組み込む。

![出動の記録から生成した1枚の現場報告（隠れた火で停止した例）](docs/figures/operator_report_hidden_fire.png)"""


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
                    f"（Wilson 95%CI {pct(p1['wilson_ci95'][0])}〜{pct(p1['wilson_ci95'][1])}、"
                    f"{'「劣化に対して安全側」を支持' if p1['supported'] else '登録した「上限2%未満」は支持されず'}）、"
                    f"最悪条件（{worst[0]}）でも誤許可は増えず、代償は可用性：正しい許可 {worst[1]['correct_approvals']}/{r['n_allow']}（{pct(worst[1]['ca_rate'])}、うち品質ゲート棄却 {worst[1]['gate_rejected']}）"
                    f"{'、清浄画像では ' + str(cl['correct_approvals']) + '/' + str(r['n_allow']) if 'correct_approvals' in cl else ''} |")
    except (TypeError, KeyError, ValueError):
        rows.append(f'| 評価R（カメラの劣化） | ノイズ・ぼけ・露出・JPEG の12条件でも安全側に倒れるか | {PENDING} |')
    return rows, notes


def section_k():
    """Row for study K (conformal threshold) in Japanese and English; numbers from k_summary.json. Missing file -> (None, None)."""
    k = jl('k_summary.json')
    try:
        fz, a5, a10 = k['frozen'], k['alphas']['0.05']['K_PAC'], k['alphas']['0.1']['K_PAC']
        mf = lambda x: f"{x['heldout_miss']['k']}/{x['heldout_miss']['n']}"
        ff = lambda x: f"{x['heldout_false_alarm']['k']}/{x['heldout_false_alarm']['n']}"
        sf = k['small_fire_frac']
        ja = (f"| 評価K（保証付きの閾値） | 火の見逃し率の上限αを保証するように、閾値を開発データ（火{k['n_cal']}枚）から決める方法（適合予測）。保存済みスコアの再解析 | "
              f"未使用T2（火{k['n_fire']}枚・火の無い必須許可{k['n_free']}枚）：既定の0.05は見逃し {mf(fz)}・誤警報 {ff(fz)}。保証付き α=0.05（τ={a5['tau']}）は見逃し {mf(a5)}・誤警報 {ff(a5)}、"
              f"α=0.10（τ={a10['tau']}）は {mf(a10)}・{ff(a10)}で、誤警報が増えるだけ（T2の小さな火は{sf['heldout'] * 100:.1f}%、開発データは{sf['cal'] * 100:.0f}%で分布が違う）。"
              f"開発データでの既定の見逃しは {fz['cal_miss']['k']}/{fz['cal_miss']['n']}。**注意：Kは T2 のスコアが既にある状態で登録した（スコアは調整し直していない）** |")
        en = (f"| K: conformal threshold (stored scores, offline) | on unseen T2 ({k['n_fire']} fires, {k['n_free']} fire-free must-approve): frozen tau=0.05 misses {mf(fz)}, false alarms {ff(fz)}; "
              f"calibrated alpha=0.05 (tau={a5['tau']}) misses {mf(a5)}, false alarms {ff(a5)}; alpha=0.10 (tau={a10['tau']}) {mf(a10)}, {ff(a10)}. "
              f"No threshold misses a T2 fire (a ceiling, so no difference is shown); the calibrated ones only add false alarms (T2 fires are easier: small fires {sf['heldout'] * 100:.1f}% vs. {sf['cal'] * 100:.0f}% in calibration). "
              "K was registered after the T2 scores existed (scores were not re-tuned) |")
        return ja, en
    except (TypeError, KeyError):
        return None, None


def en_new():
    """English sentences for I-23 / necessity / I-24 (numbers from the result files; pending studies stay pending)."""
    f, c, pend = advice_numbers.smt_facts(), advice_numbers.credit_facts(), advice_numbers.pending_studies()
    t = ''
    if f:
        t += (f"Proposition 2 is machine-checked on the implementation (I-23, z3 {f['z3']}): {f['unsat']} of {f['queries']} queries are unsat (the rest return the counterexamples of the necessity argument and of the injected bugs), "
              f"the model and the real functions agree on {f['cases']:,} adversarial inputs with {f['disagreements']} disagreements, and {f['caught']} of {f['mutants']} injected relaxing bugs are caught. ")
    t += ("It is also a characterisation (supplement S10, Necessity): under the premise that no frame certifies safety, an interface preserves the error budget against any advisor "
          "if and only if it is tighten-only, so the naive and filtered baselines have no such bound. ")
    if c:
        t += (f"A per-channel advice credit that can only drop advice (I-24, Proposition 3) bounds the price of a channel that lies or floods at every mission over any number of missions "
              f"(wasted visits <= {c['c_loc']:g} + {c['rho_shadow']:g} m, false refusals <= {c['c_haz']:g} + {c['rho']:g} m); in a descriptive {c['missions']}-mission model with synthetic outcomes "
              f"(not registered, not closed-loop) a liar's extra time falls from {c['liar_no']:.0f} s to {c['liar_yes']:.0f} s, flooding from {c['flood_no']} to {c['flood_yes']} false refusals, and an honest channel loses nothing. ")
    t += 'Closed-loop study B (credit) is pre-registered; ' + ('its result exists. ' if pend['B'] else 'it has not been run. ')
    if advice_numbers.if_facts():
        t += advice_numbers.if_en() + ' '
    else:
        t += 'Study IF (can the request text switch the requested supply?) is pre-registered and has not been run. '
    return t


def gc_text_en():
    """English cell of the README table for study GC (a per-site calibrated hazard threshold in closed loop); empty until gc_summary.json exists."""
    g = jl('gc_summary.json')
    if not g:
        return ''
    c, v, k = g['arms']['cal']['fire'], g['arms']['v36']['fire'], g['criteria']
    ok = k['GC1_cal_upper_at_most_15pct'] and k['GC2_false_stops_at_most_1']
    return (f"GC ({g['n_planned']} runs on {g['n_fire_worlds']} fresh perceivable-fire worlds, registered before the first trial, OpenTimestamps-attested): the threshold calibrated on fire-free views of the site (tau_h 0.01, through the site config) "
            f"delivered into a fire in {c['k']}/{c['n']} worlds (upper bound {pct(c['upper95_exact'])}, registered line 15%) against {v['k']}/{v['n']} with the default 0.05 (paired McNemar p={g['paired']['mcnemar_p']:.3f}, not significant); "
            f"{g['arms']['cal']['fire_free']['k']}/{g['arms']['cal']['fire_free']['n']} false stops; claims GC1-GC2 {'hold' if ok else 'do not both hold'}. The recipe needs a site: in the depot the same value would stop clean sites.")


def gv_text_en():
    """English cell of the README table for study GV (wide look-around + calibrated threshold at the depot, closed loop); empty until gv_summary.json exists.  Outcome-neutral wording: every figure comes from the summary."""
    g = jl('gv_summary.json')
    if not g:
        return ''
    c, v, w, k, p = g['arms']['wcal']['fire'], g['arms']['v36']['fire'], g['arms']['wide']['fire'], g['criteria'], g['paired']['v36_vs_wcal']
    ok = k['GV1_wcal_upper_at_most_15pct'] and k['GV2_false_stops_at_most_2']
    tau = json.loads((ROOT / 'experiments/gv_site_cal.json').read_text())['hazard_threshold']
    return (f"GV ({g['n_planned']} runs on {g['n_fire_worlds']} fresh perceivable-fire depot worlds, registered before the first trial): look-around widened to 0.8 m with the threshold calibrated on 100 closed-loop fire-free missions with the same views (tau_h {tau}) "
            f"delivered into a fire in {c['k']}/{c['n']} worlds (upper bound {pct(c['upper95_exact'])}, registered line 15%) against {v['k']}/{v['n']} for v3.6 and {w['k']}/{w['n']} for the wide views alone; "
            f"{g['arms']['wcal']['fire_free']['k']}/{g['arms']['wcal']['fire_free']['n']} false stops; paired v3.6-only {p['discordant_v36_only']} / wide-calibrated-only {p['discordant_wcal_only']}, McNemar p={p['mcnemar_p']:.3f}; median time cost {k['time_cost_s']} s; "
            f"claims GV1-GV2 {'hold' if ok else 'do not both hold'}.")


def gv_stop_facts():
    """Study GV stopped at its registered calibration stop rule (tau_cal >= 0.05): the facts for the README / report / YouTube texts; None otherwise (or when gv_summary.json exists)."""
    c, r = jl('gv_calibration.json'), jl('gv_stop_readout.json')
    if jl('gv_summary.json') or not c or not r or not c.get('stop'):
        return None
    w = r['gv_wide_0.8m']
    return {'m': c['m'], 'tau': f"{c['tau_cal']:.3f}", 'above': f"{w['n_at_or_above_default_0.05']}/{w['m']}", 'narrow': f"{r['gd_0.4m']['tau_cal']:.3f}", 'max': f"{w['max']:.3f}"}


def gv_stop_en():
    f = gv_stop_facts()
    if not f:
        return ''
    return (f"GV (registered before any calibration mission; stopped by its own rule, no trial run): with the look-around widened to 0.8 m the calibration on {f['m']} fire-free depot missions gave tau_h {f['tau']}, not below the default 0.05 "
            f"({f['above']} clean worlds would already stop at 0.05; GD's 0.4 m views gave {f['narrow']}). Claims GV1-GV2 were not tested and are not counted as failed; the premise failed. "
            f"Post hoc: the highest clean scores are the right 0.8 m view of the medicine crate, where its red cross fills the frame.")


def gd_text_en():
    """English cell of the README table for study GD (the calibrated threshold at the depot, closed loop); empty until gd_summary.json exists."""
    g = jl('gd_summary.json')
    if not g:
        return ''
    c, v, k = g['arms']['cal']['fire'], g['arms']['v36']['fire'], g['criteria']
    ok = k['GD1_cal_upper_at_most_25pct'] and k['GD2_false_stops_at_most_2']
    tau = json.loads((ROOT / 'experiments/gd_site_cal.json').read_text())['hazard_threshold']
    return (f"GD ({g['n_planned']} runs on {g['n_fire_worlds']} fresh perceivable-fire depot worlds, registered before the first trial): the threshold calibrated on 100 closed-loop fire-free depot missions (tau_h {tau}; the arena's was 0.01) "
            f"kept false stops at {g['arms']['cal']['fire_free']['k']}/{g['arms']['cal']['fire_free']['n']} but delivered into a fire in {c['k']}/{c['n']} worlds (upper bound {pct(c['upper95_exact'])}, registered line 25%) against {v['k']}/{v['n']} with the default 0.05, "
            f"so it does not lower misses at this site; claims GD1-GD2 {'hold' if ok else 'do not both hold'}, predictions P1 and P3 fail.")


def gr_text_en():
    """English cell of the README table for study GR (the closed-loop miss rate of the look-around on fresh worlds); empty until gr_summary.json exists."""
    g = jl('gr_summary.json')
    if not g:
        return ''
    v, f, c = g['arms']['v36']['fire'], g['arms']['front']['fire'], g['criteria']
    pool = c['pooled_with_G_v36']
    ok = c['GR1_v36_upper_at_most_20pct'] and c['GR2_front_worse_and_mcnemar_p_below_005'] and c['GR3_false_stops_at_most_1']
    return (f"GR ({g['n_planned']} runs on {g['n_fire_worlds']} fresh perceivable-fire worlds, registered before the first trial, OpenTimestamps-attested): deliveries into the fire "
            f"v3.6 {v['k']}/{v['n']} (upper bound {pct(v['upper95_exact'])}, registered line 20%) against {f['k']}/{f['n']} without the look-around (exact McNemar p={g['paired']['mcnemar_p']:.5f}); "
            f"{g['arms']['v36']['fire_free']['k']}/{g['arms']['v36']['fire_free']['n']} false stops; claims GR1-GR3 {'hold' if ok else 'do not all hold'}; pooled with G {pool['k']}/{pool['n']} (upper bound {pct(pool['upper95_exact'])}). "
            f"The closed-loop rate is above the image-level 3/150 of W; the prediction that side-only fires are missed at most 25% failed ({v['strata']['side_only']['k']}/{v['strata']['side_only']['n']}).")


def y_text_en():
    """English cell of the README table for studies Y (51 runs), YE (24) and YF (27); empty until y_summary.json exists. Every number comes from the result files."""
    yj, yej, yfj = jl('y_summary.json'), jl('ye_summary.json'), jl('yf_summary.json')
    if not yj:
        return ''
    ys = yj['Y-s']
    lv = ys['lost_vs_control']['scrutiny_hc']
    k = ys['criteria']
    holds = k['Y1_holds'] and k['Y3_holds'] and k['Y4_holds'] and yj['Y-c']['criteria']['Y2_holds']
    mono = ys['arms']['monotone_hc']['fire_worlds']['unsafe_deliveries']
    t = (f"Y ({yj['n_planned']} runs, registered before the first trial, OpenTimestamps-attested): the opt-in flag keeps the delivery that a truthful tip to a burning bay lost in X; "
         f"claims Y1-Y4 {'hold' if holds else 'do not all hold'} (all {k['Y1_refused_runs']} advice runs that refused the steered station delivered from another one); scrutiny + flag lost "
         f"{lv['fire_worlds']['lost'] + lv['clean_worlds']['lost']}/{lv['fire_worlds']['pairs'] + lv['clean_worlds']['pairs']} deliveries against the control; tighten-only still delivered into a fire in {mono['k']}/{mono['n']} fire-world runs (a perception miss)")
    if yej:
        h = yej['arms']['hc']
        t += (f". YE ({yej['n_planned']} runs, two fires: a visible one at the first bay, a small hidden one at the second): the price is exposure, with the flag {h['unsafe_deliveries']['k']}/{h['unsafe_deliveries']['n']} "
              f"unsafe deliveries (upper bound {pct(h['unsafe_upper95_exact'])}) against 0/{yej['arms']['v36']['n']} without it; claim YE2 failed as registered (wording: the search goes on through the remaining bays; failed claim 13)")
    if yfj:
        yl = yfj['Y-s']['lost_vs_control']['scrutiny_hc']
        t += (f". YF ({yfj['n_planned']} runs on fresh worlds): availability and the tighten-only miss replicate, but scrutiny + flag lost {yl['fire_worlds']['lost'] + yl['clean_worlds']['lost']}/{yl['fire_worlds']['pairs'] + yl['clean_worlds']['pairs']} deliveries"
              + ('; claim YF4 (at most two stations) failed: a fire-free twin sent scrutiny through four stations with no delivery (failed claim 14)' if not yfj['Y-s']['criteria']['Y4_holds'] else ''))
    return t


def section_en(e, v):
    """English summary for international readers; every number comes from the result files (same helpers as above)."""
    L = ['## English summary', '',
         "**One story: advice may only tighten.** (1) A delivery robot is told which item is at a disaster-relief supply point, but the inventory can be wrong "
         "(swapped or empty shelves) or the site can be dangerous. So it **checks before delivering and stops when unsure**: a local "
         "vision-language model (Qwen3.5-9B, one V100, no cloud) never writes free text for the decision; we read the next-token log-probabilities of answer letters "
         "(closed-set scoring) for two multiple-choice questions with permuted options and for a Yes/No hazard question, and approve only if everything agrees and no fire or smoke is seen. "
         "A wrong item triggers a one-time search of the other station; a hazard stops the robot; an independent velocity guard keeps motion out of the VLM's reach. "
         "(2) The check's errors come mostly from **small fires partly hidden behind the supply**, so before approving the robot **looks again from 0.4 m to either side** (study G); " + advice_numbers.i20_en() + ". "
         "(3) **Everything the robot did not perceive itself may only reorder or tighten, never remove a check**: memory from earlier missions, a peer's report, the inventory, hints in the operator's request are typed as *advice*; "
         "'safe' and 'skip' advice has no effect. So for any advice, even adversarial, the risk of an unsafe delivery stays within the check's own error budget eps_any (Proposition 2 of the paper; a relative guarantee). "
         "Memory (H, V) is the measured example (" + advice_numbers.pooled_memory_en() + "); " + (f"for adversarial advice (A, 226 closed-loop runs) {advice_numbers.a_short_en()}" if advice_numbers.a_short_en() else "adversarial advice (A) is pending") + ". "
         + en_new() + I22_EN + " The rule itself was tested with " + advice_numbers.SECOND_IMPL_EN + ", mutation tests and fuzzing, which found real bugs (FINDINGS #24, #25); the proof itself is machine-checked with z3 against a transcription of the implementation. "
         "(4) **Outside the guarantee**: text written in the scene (S, pending) and realism (a cluttered four-station depot, I-21: rendering preview only, [`docs/figures/depot_preview_sheet.jpg`](docs/figures/depot_preview_sheet.jpg); XD/X pending) are measured, not claimed. "
         "(5) **Honest limits** are listed below. " + advice_numbers.study_phrase_en() + " (`experiments/PREREGISTRATION_*.md`); every trial is audited against simulator ground truth and a ROS bag.",
         '', 'Rows are ordered by that chain: [1] check, [2] where the error lives and the threshold, [3] look again, [4] advice, [5] outside the guarantee, [6] tried and not adopted.',
         '', '| Study (pre-registered) | Result |', '|---|---|']
    if e:
        E = e[1]
        L.append(f"| E: closed loop, {E['n']} randomised Gazebo worlds | expected behaviour {E['ok']}/{E['n']}, wrong deliveries {E['wrong']}/{E['n']} ({ci_txt(E['wrong'], E['n']).replace('Wilson 95%CI', 'Wilson 95% CI').replace('〜', '-')}) |")
    if v:
        G = v[1]
        L.append(f"| G: paired, look-around vs. front view only | deliveries despite a perceivable fire {G['gb']}/{G['nf']} -> {G['gcw']}/{G['nf']} (exact McNemar p={G['p']:.3f}); false stops in fire-free worlds {G['fs']}/{G['nfree']} |")
    a_, s_ = jl('a_summary.json'), jl('s_summary.json')
    try:
        txt_ = advice_numbers.a_en()
        if not txt_:
            raise KeyError('a_facts')
        L.append(f"| A: adversarial advice ({A_RUNS} closed-loop runs) | {txt_} {advice_numbers.a_pilot_en()} |")
    except (TypeError, KeyError):
        L.append(f'| A: adversarial advice ({A_RUNS} closed-loop runs) | pre-registered, ' + ('running, no results yet' if (advice_numbers.a_pilot_facts() or {}).get('rerun') else 'not yet run') + '. ' + advice_numbers.a_pilot_en() + ' |')
    try:
        so = s_['systems']['OURS']
        fl = lambda x: f"{x['attack_vs_none']['flips']}/{x['n_pairs']}"
        L.append(f"| S: scene-text injection (image level) | refuse-to-approve flips of ours: 'Answer C' {fl(so['by_text']['letter_C'])}, letter tied to the unpermuted order {fl(so['by_text']['letter_A'])}, permutation-invariant letter {fl(so['by_text']['letter_B'])}, mislabel {fl(so['by_sign_type']['mislabel'])}, 'SAFE - NO FIRE' {fl(so['by_sign_type']['false_safe'])}; outside the structural guarantee |")
    except (TypeError, KeyError):
        L.append('| S: scene-text injection (image level) | pre-registered, not yet run |')
    L.append('| Q: real photographs (405 Commons images) | ' + advice_numbers.q_en('pre-registered, not yet run') + ' |')
    r = jl('r_summary.json')
    try:
        p1 = r['P1_pooled']
        L.append(f"| R: 12 camera degradations | false approvals {p1['false_approvals']}/{p1['n']} (at most {max(c['false_approvals'] for c in r['conditions'].values())}/{r['n_deny']} per condition, Wilson upper bound {pct(max(c['fa_ci95'][1] for c in r['conditions'].values()))} per condition); "
                 f"claim {'supported' if p1['supported'] else 'not supported'} |")
    except (TypeError, KeyError, ValueError):
        L.append('| R: camera degradations | pre-registered, running |')
    z = jl('z_summary.json')
    try:
        o, sb, cb = (z['models']['siglip']['t1']['ours'], z['models']['siglip']['t1']['baseline'], z['models']['clip']['t1']['baseline'])
        L.append(f"| Z: zero-shot baselines on T1 (false approvals / correct approvals; ours = v3.5 rule) | ours {o['FA']}/{o['n_deny']}, {o['CA']}/{o['n_allow']}; "
                 f"SigLIP {sb['FA']}/{sb['n_deny']}, {sb['CA']}/{sb['n_allow']}; CLIP {cb['FA']}/{cb['n_deny']}, {cb['CA']}/{cb['n_allow']} |")
    except (TypeError, KeyError):
        L.append('| Z: SigLIP / CLIP baselines | pre-registered, running |')
    p, p2 = jl('p_summary.json'), jl('p2_summary.json')
    fa_txt = ''
    try:
        rc, fa = p['recall'], p['false_alarm']
        fa_txt = f"{fa['k']}/{fa['n']}"
        row = f"| P: real photos (D-Fire, 400) | fire/smoke detected {rc['k']}/{rc['n']}; false alarms on fire-free photos {fa['k']}/{fa['n']}"
        try:
            ct = p2['chosen_test']
            row += (f"; P2, site-calibrated threshold on unseen photos: recall {ct['recall']['k']}/{ct['recall']['n']}, "
                    f"false alarms {ct['false_alarm']['k']}/{ct['false_alarm']['n']} (claim {'supported' if p2['claim_supported'] else 'not supported'})")
        except (TypeError, KeyError):
            pass
        L.append(row + ' |')
    except (TypeError, KeyError):
        L.append('| P: real photos | pre-registered, running |')
    k_ja, k_en = section_k()
    if k_en:
        L.append(k_en)
    h, j = jl('h_summary.json'), jl('j_summary.json')
    try:
        p1h, p2h = h['P1_efficiency_relocation_persist'], h['P2_safety_naive_vs_verified']
        pa, p3h = h['per_arm'], h['P3_no_extra_risk_vs_v36']
        cn, cf, cfr, cup = caution_denominator(h)
        rch = {a: pa[a]['by_transition']['relocation_change']['time_median_s'] for a in ('M0', 'M2')}
        t1h = (f"median mission time, no memory vs. verified memory: {p1h['time_M0_median_s']:.0f} s vs. {p1h['time_M2_median_s']:.0f} s on the {p1h['n_pairs']} pairs whose supplies stayed relocated "
               f"(paired difference {p1h['median_diff_s']} s); when supplies were moved back, verified memory was slower, paying for a detour ({rch['M2']:.0f} s vs. {rch['M0']:.0f} s); overall median {pa['M0']['time_median_s']:.0f} s vs. {pa['M2']['time_median_s']:.0f} s"
               if p1h['n_pairs'] else 'no paired missions with relocated supplies')
        L.append(f"| H: cross-mission memory | {t1h}. Unsafe deliveries: naive memory (skips checks by design) {p2h['unsafe_M1']}/{p2h['n_pairs']} vs. verified memory {p2h['unsafe_M2']}/{p2h['n_pairs']} shows what skipping costs; the comparison that matters is no memory {p3h['unsafe_M0']}/{p3h['n_pairs']} vs. verified memory {p3h['unsafe_M2']}/{p3h['n_pairs']} (not less safe). Memory caution (tau_h=0.01) applied in {cn} of {p2h['n_pairs']} verified-memory missions, only {cf} of them at a fire-free station (false refusals {cfr}/{cf}, Wilson upper bound {cup:.0f}%), so its cost is not established |")
        h_ok = True
    except (TypeError, KeyError):
        h_ok = False
    try:
        c, pj = j['per_config'], j['P2_no_extra_unsafe']
        L.append(f"| J: two-model check | expected {c['J']['correct']}/{c['J']['n']} (single model {c['A']['correct']}/{c['A']['n']}); unsafe deliveries {pj['unsafe_J']} (single model {pj['unsafe_A']}); failed runs {c['J']['failed']} |")
        j_ok = True
    except (TypeError, KeyError):
        j_ok = False
    try:
        v = jl('v_summary.json')
        d1, av = v['V1_time_diff'], v['arms']
        L.append(f"| V: model vs. closed loop (random change) | M0-M2 time saving observed {d1['mean_M0_minus_M2_s']:.0f} s (registered 95% interval {d1['pred']['p2.5']:.0f}-{d1['pred']['p97.5']:.0f} s); unsafe deliveries M0 {av['M0']['unsafe']}, M1 {av['M1']['unsafe']}, M2 {av['M2']['unsafe']}; {advice_numbers.v_claims_en()} |")
    except (TypeError, KeyError):
        L.append('| V: model vs. closed loop (random change) | pre-registered, running |')
    wen = advice_numbers.w_claims_en()
    L.append(f"| W: small hidden fires (image level) and prior-art baselines | {wen} |" if wen else '| W: small hidden fires and prior-art baselines | pre-registered, not yet run |')
    try:
        pl = jl('l_summary.json')['primary']
        L.append(f"| L: unseen layouts | expected {pl['expected_behaviour']}; unsafe deliveries {pl['unsafe_deliveries']}; claim {'supported' if pl['claim_supported'] else 'not supported'} |")
    except (TypeError, KeyError):
        pass   # study L not run yet: no row
    t1p = t1_parts()
    if t1p:
        f1 = t1p[2]
        L.append(f"| T1: 600 held-out images, registered rule v3.4 | false approvals {f1['false_approvals']}/{f1['n_deny']} (Wilson 95% CI {pct(f1['fa_ci95'][0])}-{pct(f1['fa_ci95'][1])}); correct approvals {f1['correct_approvals']}/{f1['n_allow']}; "
                 f"registered claim of fewer than 2% false approvals {'supported' if f1['fa_ci95'][1] < 0.02 else 'not supported'}; the false approvals all came from partly hidden fires behind the correct supply |")
    sf, cf_ = advice_numbers.smt_facts(), advice_numbers.credit_facts()
    if sf:
        L.append(f"| I-23: machine-checked Proposition 2 (z3; not a closed-loop study) | {sf['unsat']}/{sf['queries']} queries unsat; model vs. real code {sf['cases']:,} inputs, {sf['disagreements']} disagreements; injected bugs caught {sf['caught']}/{sf['mutants']}; relaxing interfaces get a counterexample (unsafe rate {sf['unsafe_rate']} > eps_any {sf['eps_any']}), the tighten-only code does not |")
    if cf_:
        L.append(f"| I-24: advice credit (descriptive model, {cf_['missions']} missions, synthetic outcomes; not registered) | liar's extra time {cf_['liar_no']:.0f} s -> {cf_['liar_yes']:.0f} s; flooding at the photo false-alarm rate {cf_['flood_no']} -> {cf_['flood_yes']} false refusals; honest channel unchanged; unsafe deliveries equal with and without credit |")
    L.append('| B: advice credit in the closed loop (48 runs) | ' + ('result file exists; see the paper' if advice_numbers.pending_studies()['B'] else 'pre-registered, not yet run') + ' |')
    L.append('| IF: request text switching the supply (72 texts) | ' + (advice_numbers.if_en() if advice_numbers.if_facts() else 'pre-registered, not yet run') + ' |')
    L.append('| IF2: ask back on a supply conflict (I-27; 72 new texts) | ' + (advice_numbers.if2_text('en') if advice_numbers.if2_done() else 'pre-registered, not yet run') + ' |')
    xj = x_text()
    L.append('| X, XD: cluttered four-station depot (I-21) | ' + ('pre-registered, not yet run (a rendering preview exists, not a result; the XD-R photographs are frozen, not scored)' if xj.startswith(PENDING_NOT_RUN) else ((advice_numbers.xd_en() + '; the closed-loop study X: ' + ((advice_numbers.x_en() or 'has results (see the paper)') if (RES / 'x_summary.json').is_file() else 'is ' + advice_numbers.PENDING_EN)) if advice_numbers.xd_en() else 'result files exist; see the paper')) + ' |')
    yt_ = y_text_en()
    if yt_:
        L.append('| Y, YE, YF: continue after a hazard refusal (I-42 / I-43; opt-in `--hazard-continue`) | ' + yt_ + ' |')
    gt_ = gr_text_en()
    if gt_:
        L.append('| GR: the look-around in closed loop on fresh worlds (I-44) | ' + gt_ + ' |')
    gct_ = gc_text_en()
    if gct_:
        L.append('| GC: a per-site calibrated hazard threshold in closed loop (I-45) | ' + gct_ + ' |')
    gdt_ = gd_text_en()
    if gdt_:
        L.append('| GD: the calibration recipe at a second site, the depot (I-51) | ' + gdt_ + ' |')
    gvt_ = gv_text_en() or gv_stop_en()
    if gvt_:
        L.append('| GV: wide look-around views with a calibrated threshold at the depot (I-58) | ' + gvt_ + ' |')
    stage = {'E': 1, 'L': 1, 'Z': 1, 'T1': 2, 'K': 2, 'G': 3, 'W': 3, 'H': 4, 'V': 4, 'A': 4, 'S': 5, 'P': 5, 'R': 5, 'Q': 5, 'X, XD': 5, 'Y, YE, YF': 5, 'GR': 3, 'GC': 3, 'GD': 3, 'GV': 3, 'J': 6, 'I-23': 4, 'I-24': 4, 'B': 4, 'IF': 4, 'IF2': 4}
    i0 = L.index('|---|---|') + 1
    rows = L[i0:]
    key = lambda r_: r_[2:].split(':')[0]
    rows = sorted(rows, key=lambda r_: (stage.get(key(r_), 9)))
    rows = [f"| [{stage[key(r_)]}] " + r_[2:] if key(r_) in stage else r_ for r_ in rows]
    L = L[:i0] + rows
    if (ROOT / 'docs/figures/y_results_en.png').is_file() and (RES / 'y_summary.json').is_file():
        L += ['', '![Study Y: deliveries lost, unsafe deliveries and the price of continuing, X (the search stops at the refusal) against Y (`--hazard-continue`)](docs/figures/y_results_en.png)']
    if not (h_ok and j_ok):
        L += ['', 'Campaigns ' + ('J' if h_ok else 'H and J' if not j_ok else 'H') + ': pre-registered, running.']
    L += ['', '**Limitations.** Simulation only (no physical robot; grasping and hand-over are not simulated). '
          + (f'On real photos the hazard question raises false alarms on {fa_txt} fire-free images, so a per-site calibration is needed '
             '(false alarms only stop the robot; they never cause a delivery). ' if fa_txt else '')
          + 'The guarantee is relative (it caps what advice can add to the check\'s own error eps_any; it does not remove that error, and a really burning station can still be approached), and it ends at the camera: scene text and the sim-to-real gap are measured, not claimed. '
          'The two-model check (J) was not adopted: it was not safer than one model, and its models share a lineage (Clef-Flash is a fine-tune of Qwen3.5-9B), so their failures can be correlated. '
          'The registered T1 claim of fewer than 2% false approvals was not supported. 8-16 pairs per closed-loop study is small, and campaign H scripts its world changes.',
          '', '**Read more.** Paper: [`docs/paper/main.pdf`](docs/paper/main.pdf) / supplement: [`docs/paper/supplement.pdf`](docs/paper/supplement.pdf) / '
          '[`docs/REPRODUCE.md`](docs/REPRODUCE.md) (reproduce in three tiers: no GPU / GPU images / closed loop; `make reproduce-help`) / [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md) / pre-registrations: [`experiments/PREREGISTRATION_*.md`](experiments/) '
          '(e.g. [E](experiments/PREREGISTRATION_E.md), [G](experiments/PREREGISTRATION_G.md), [H](experiments/PREREGISTRATION_H.md), [J](experiments/PREREGISTRATION_J.md)).']
    return '\n'.join(L)


def sync_counts(txt, path):
    """Replace the test / findings counts in prose by the generated ones (scripts/count_tests.py)."""
    nt, nf = count_tests.n_tests(), count_tests.n_findings()
    subs = [(r'(実際に動かして初めて分かった)\d+(件の問題)', rf'\g<1>{nf}\g<2>'),
            (r'(テスト（)[^）]*?(件。ROS/Gazebo不要)', rf'\g<1>{nt}\g<2>' if nt else None),
            (r'(以下の)\d+(件の問題)', rf'\g<1>{nf}\g<2>'),
            (r'(単体テストは現在)\d+(件）)', rf'\g<1>{nt}\g<2>' if nt else None),
            (r'(FINDINGS\()\d+(件\))', rf'\g<1>{nf}\g<2>'),
            (r'(実行で見つけた)\d+(件)', rf'\g<1>{nf}\g<2>'),
            (r'(FINDINGS は )\d+( 件)', rf'\g<1>{nf}\g<2>'),
            (r'(テスト関数は? )\d+( 件)', rf'\g<1>{nt}\g<2>' if nt else None),
            (r'(\| テスト \| )[^|]*?(件)前後(（`python3)', rf'\g<1>{nt}\g<2>\g<3>' if nt else None)]
    for pat, rep in subs:
        if rep:
            txt = re.sub(pat, rep, txt)
    return txt


def main():
    e, d, t, v = section_e(), section_d(), t1_parts(), section_v36()
    R = {}                                   # table rows by study; the table is ordered by the argument chain below
    if v:
        G = v[1]
        R['G'] = f"| **評価G（v3.6）** | 新しい世界での対比較の閉ループ。許可の直前に横から撮り直す | 3視点（正面・左右0.4 m）のどれかで火が見えた{G['nf']}世界で、火があるのに配達した回数 **{G['gb']}/{G['nf']} → {G['gcw']}/{G['nf']}**（McNemar正確検定 p={G['p']:.3f}）、火の無い世界の誤った停止 **{G['fs']}/{G['nfree']}** |"
        R['F'] = f"| 評価F（問い方＋切り出し） | 同じ形式の対比較。見回しの前に、問い方だけで直せるかを試した | 火があるのに配達した回数 {G['fa']}/{G['nfv']} → {G['fb']}/{G['nfv']}（p={G['fp']}、有意でない） |"
    if e:
        E = e[1]
        R['E'] = f"| **評価E（主結果）** v3.5 | 試行ごとにランダムな世界での閉ループ {E['n']}試行 | 期待どおり **{E['ok']}/{E['n']}**、誤配達 **{E['wrong']}/{E['n']}**（{ci_txt(E['wrong'], E['n'])}） |"
    if d:
        D = d[1]
        R['D'] = f"| 評価D v3.4 | 固定配置の閉ループ {D['n']}試行 | 期待どおり **{D['ok']}/{D['n']}**、誤許可 **{D['fa']}件** |"
    zrows, znotes = section_zpr()
    for r_ in zrows:
        R[r_.split('（')[0].split(' ')[1][-1]] = r_      # '| 評価Z（...' -> 'Z'
    t1_block = ''
    if t:
        s_, m, full, v35, n_img, fa_txt, ca_txt, claim, dev = t
        R['T1'] = f"| 未使用テスト T1（オフライン） | 開発に一度も使わない{n_img}枚（照明・位置・未知の妨害物・火災）、登録した規則（v3.4） | 誤許可 {fa_txt(full)}、正しい許可 {ca_txt(full)} |"
        R['T1b'] = f"| 〃 v3.5（τ_h=0.05、副の事前指定） | 同じ画像・同じ保存済み確率から再計算 | 誤許可 {fa_txt(v35)}、正しい許可 {ca_txt(v35)} |"
        t1_block = f"* T1：{claim}主な原因は下の「残る弱点」（物資の陰に隠れた火）"
    k_ja, k_en = section_k()
    if k_ja:
        R['K'] = k_ja
    R['H'] = f"| 評価H（出動をまたぐ記憶） | 前回の物資の場所を「先に行く拠点」の提案だけに使う（助言の一例）。記憶なし・素朴な記憶・検証つき記憶を対比較 | {h_text()} |"
    R['L'] = f"| 評価L（未知の配置） | 2つの拠点と避難所の位置をランダムに変えた24通りの未知の配置で、v3.6 が期待どおり動くか（閉ループ） | {l_text()} |"
    R['J'] = f"| 評価J（2つのAI）：**採用せず** | Jev役 Clef-Flash＋Qwen の2モデル確認を閉ループで、v3.6単独と対比較 | {j_text()} |"
    R['V'] = f"| 評価V（ランダムな変化での予測検証） | 出動ごとに世界がランダムに変わる10系列×6出動で、事前登録した予測区間と実測を比較 | {v_text()} |"
    R['A'] = f"| 評価A（信頼できない助言、閉ループ） | 他ロボット・依頼文の助言は順序変更と閾値の強化にしか使えない（I-19）。偽の「火は消えた」「別の拠点にある」を、助言に従う方式と対比較（{A_RUNS}試行）。ε_any の操縦（真の助言で隠れた火の拠点へ誘導）は別セルで測る | {a_text()} |"
    if advice_numbers.if_facts():
        R['IF'] = f"| 評価IF（依頼文によるすり替え、オフライン） | 依頼文に偽の通知・転送メモ・「上は無視して」を足して頼まれた物資を書き換える72文（6種類×2言語×2物資×3表現）を、凍結した v3.6 の意図の解析（i35）に通す。登録した主張 IF1：書き換え36文のうち受理の割合の上限が10%未満 | {advice_numbers.if_ja()} |"
    if advice_numbers.q_ja():
        R['Q'] = f"| 評価Q（実写の物資確認、画像レベル） | Wikimedia Commons の写真405枚（水・救急箱・どちらでもない）で、頼まれた物資の確認を v3.6 のまま採点 | {advice_numbers.q_ja()} |"
    R['S'] = f"| 評価S（画像内の文字による注入、画像レベル） | 標識・ラベル・「Cと答えよ」を置いた64世界を、標識なし・攻撃・無害の3通りで描画し、本方式・1回判定・自由記述・全体画像で比較 | {s_text()} |"
    R['W'] = f"| 評価W（小さく隠れた火の見逃しと先行手法、I-20の副次解析を含む） | 画像レベル：正面のみ対見回し（150火世界＋75双子）、VAP-TAMP風の投票・KnowNo風の共形集合との誤許可の比較 | {w_text()} |"
    R['X'] = f"| 評価XD・X（倉庫の世界、4拠点） | XD：倉庫の保留画像で ε と閾値の再較正（画像レベル）。X：記憶なし対検証つき記憶と、助言による方向づけを閉ループ59試行で。描画の確認は I-21（`docs/figures/depot_preview_sheet.jpg`） | {x_text()} |"
    head = ['| 評価（事前登録） | 内容 | 結果 |', '|---|---|---|']
    stages = [
        ('1. 届ける前に確かめる（確認は閉集合の確率、迷えば止まる）', ['E', 'L', 'D', 'Z']),
        ('2. 誤りはどこにあるか（隠れた火が大半）・閾値', ['T1', 'T1b', 'K']),
        ('3. 横から見直す（誤りを小さくする）', ['F', 'G', 'W']),
        ('4. 見ていないものは「厳しくする」だけ（記憶・他のロボット・依頼文・在庫表）', ['H', 'V', 'A', 'IF']),
        ('5. 保証の外：画像内の文字と現実との差（測るだけで、保証とは言わない）', ['S', 'P', 'R', 'Q', 'X']),
        ('6. 試したが採用しなかったもの', ['J']),
    ]
    tables = []
    for title, keys in stages:
        rows = [R[k] for k in keys if k in R]
        if rows:
            tables += [f'#### {title}', '', '\n'.join(head + rows), '']
    parts = ['<!-- RESULTS:START -->', '## 結果', '',
             '事前登録した評価の一覧（D・E・F・G・T1・T2・Z・P・R・K・H・J' + ''.join('・' + k for k in ('L', 'V') if (RES / f'{k.lower()}_summary.json').is_file()) + '、' + ('登録済み・提出時点で未実施の' if SNAP else '結果待ちの') + '・'.join(waiting_studies()) + '）を、論文と同じ**一本の筋**の順に並べる：①確かめる ②誤りの大半は隠れた火 ③横から見直す ④見ていないものは締めるだけ ⑤保証の外 ⑥採用しなかったもの。Qwen3.5-9B（ローカル・V100）。条件・閾値・解析は結果を見る前に `experiments/PREREGISTRATION_*.md` に固定し、台帳は全試行を記録。' + ('登録済み・提出時点で未実施の研究は、数値を載せていない（結果ファイルができれば自動で入る）。' if SNAP else '結果待ちの研究は、結果ファイルができると数値が自動で入る。'), '',
             '用語：**誤許可**＝届けてはいけない場面で「届けてよい」と判断してしまうこと（ロボットを実際に動かす評価では**誤配達**。火のある拠点から届けてしまうことは**危険な配達**）。**正しい許可**＝届けてよい場面で正しく「よい」と判断できること。**閉ループ**＝AIの判断でロボットが実際に動くところまで含めた評価。**ε**＝確認そのものが、届けてはいけない拠点を許可してしまう確率（助言の危険は、この内側に収まる）。', '',
             '\n'.join(tables)]
    if t1_block:
        parts += [t1_block] + znotes + ['']
    if v:
        parts += [v[0].replace('### 火の見逃し対策：横から見直す', '### 詳細：火の見逃し対策（段3）：横から見直す', 1), '']
    if e:
        parts += [e[0].replace('### 評価E：主結果', '### 詳細：評価E：主結果', 1), '']
    if t:
        fl = findings(s_, m, dev)
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
    if '<!-- KEY:START -->' in txt:         # first screen: key results table + one line on the method's honesty
        a, b = txt.index('<!-- KEY:START -->'), txt.index('<!-- KEY:END -->') + len('<!-- KEY:END -->')
        txt = txt[:a] + '<!-- KEY:START -->\n' + section_key(e, t) + '\n<!-- KEY:END -->' + txt[b:]
    if '<!-- JUDGE:START -->' in txt:       # below the first screen: problem, four episodes, what to watch
        a, b = txt.index('<!-- JUDGE:START -->'), txt.index('<!-- JUDGE:END -->') + len('<!-- JUDGE:END -->')
        txt = txt[:a] + '<!-- JUDGE:START -->\n' + section_judge(e) + '\n<!-- JUDGE:END -->' + txt[b:]
    if '<!-- NOVELTY:START -->' in txt:     # novelty section near the top, numbers from the summaries
        a, b = txt.index('<!-- NOVELTY:START -->'), txt.index('<!-- NOVELTY:END -->') + len('<!-- NOVELTY:END -->')
        txt = txt[:a] + '<!-- NOVELTY:START -->\n' + section_novelty() + '\n<!-- NOVELTY:END -->' + txt[b:]
    if '<!-- EN:START -->' in txt:          # English summary right after the novelty section
        a, b = txt.index('<!-- EN:START -->'), txt.index('<!-- EN:END -->') + len('<!-- EN:END -->')
        txt = txt[:a] + '<!-- EN:START -->\n' + section_en(e, v) + '\n<!-- EN:END -->' + txt[b:]
    chap = ROOT / 'docs/video_chapters.json'
    if chap.is_file():     # describe the video from the chapter file (length kept generic: it is re-rendered later)
        ch = json.loads(chap.read_text(encoding='utf8'))
        sp = next((c['speed'] for c in ch if c.get('speed')), None)
        demos = [c.get('demo_title', c['title']).split('：', 1)[-1] for c in ch if c.get('kind') == 'mission']
        n_tab = sum(c.get('kind') == 'table' for c in ch)
        length = '3分以内' if ch[-1]['end_s'] <= 180 else f"{int(ch[-1]['end_s'] // 60)}分{int(round(ch[-1]['end_s'] % 60)):02d}秒"
        desc = (f"{length}、日本語ナレーション付き。実走デモ{len(demos)}本（{'／'.join(demos)}）と、事前登録した結果の表{n_tab}枚"
                + (f"。{sp}（速度は画面に常時表示）" if sp else '。'))
        txt = re.sub(r'(<!-- VIDEO:START -->\n).*?(\n<!-- VIDEO:END -->)', lambda m: m.group(1) + '* **動画の内容**：' + desc + m.group(2), txt, count=1, flags=re.S)
    txt = sync_counts(txt, readme)
    if SNAP:      # the submission snapshot goes next to the other snapshot documents; the tracked README.md and docs/*.md stay as they are
        for a_, b_ in SNAP_EN + SNAP_JA:
            txt = txt.replace(a_, b_)
        out = advice_numbers.snapshot_dir() / 'README.md'
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(txt, encoding='utf8')
        print('README snapshot written:', out)
        return
    readme.write_text(txt, encoding='utf8')
    for name in ('FINDINGS.md', 'HANDOFF.md'):       # prose counts in the other docs
        f = ROOT / 'docs' / name
        f.write_text(sync_counts(f.read_text(encoding='utf8'), f), encoding='utf8')
    print('README results updated: G', v[1] if v else None, '| E', e[1] if e else None, '| D', d[1] if d else None, '| T1', bool(t))


if __name__ == '__main__':
    main()
