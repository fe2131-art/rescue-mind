#!/usr/bin/env python3
"""Write docs/video_plan.json (storyboard for make_demo_video.py) from real results — v3.6, <= 175 s.

  python3 scripts/make_video_plan.py --recover <id> --memory <id> --advice <id> --depot <id>        # v5 (docs/design/video_v5_plan.md)
  (older storyboards: --deliver <id> --empty <id> --fire <id> --hidden-fire <id>; demo 1 "paraphrased instruction" is only built when --deliver is given)

Demo runs are separate `--film` recordings.  Every number on the result cards is computed here from the
result files (campaign E ledger, T1 / T2 / F summaries, I-13 selection); a missing file drops that card or line.
If the full storyboard would exceed the length budget, it is shortened in this order (see fit_budget):
  1. skip the architecture card,  2. drop --fire when --hidden-fire is given (the hidden-fire segment replaces it),
  3. shrink the result cards to their narration length.
"""
from __future__ import annotations
import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'
sys.path.insert(0, str(ROOT / 'scripts'))
import advice_numbers  # noqa: E402  (study A wording: one reader for README, report, YouTube and this card)
G, R, W = (60, 200, 120), (240, 80, 80), (236, 241, 248)
LIMIT_S = 175.0      # assignment: 1-3 min
FAST, CHECK = 8.0, 3.0   # playback speed while driving / during the check motion (shown on screen per segment)
TARGET_S = 168.0     # plan to this (the narration-length estimate is approximate)
CHARS_PER_S = 6.4    # VOICEVOX speaker 2, calibrated on the v3.4 video (about 7 morae/s)
CARD_PAD_S = 0.7     # make_demo_video: card seconds >= narration + 0.3 start + 0.4 tail
OBS_JA = {'ALLOW': '配達', 'ALLOW_AFTER_SEARCH': '探索して配達', 'DENY': '停止', 'DENY_HAZARD': '危険で停止',
          'DENY_HAZARD_AFTER_SEARCH': '探索後に危険で停止', 'DENY_UNVERIFIED': '停止（証拠不足）', 'FAILED': '失敗'}
COND_JA = {'plain': '通常', 'crate': '木箱の妨害物', 'box': '段ボールの妨害物', 'cone': 'コーンの妨害物',
           'fire': '要求拠点の裏で火災', 'fire_other': '取り違え＋別拠点の裏で火災'}
COND_ORDER = ['plain', 'crate', 'box', 'cone', 'fire', 'fire_other']
DELIVERED = ('ALLOW', 'ALLOW_AFTER_SEARCH')
B_CONFIG = 'Q9B[h36_tiles] tau_h=0.05'


def jload(path):
    p = Path(path)
    return json.loads(p.read_text(encoding='utf8')) if p.is_file() else None


def wilson(k, n, z=1.959964):
    if n == 0:
        return [0.0, 1.0]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [max(0.0, c - h), min(1.0, c + h)]


def pct(x):
    return f'{x * 100:.1f}%'


def speak_s(text):
    return len(text or '') / CHARS_PER_S


# ------------------------------------------------------------------ result cards (all numbers computed)
def campaign_e_table(seconds):
    ledger = RES / 'campaign_E_ledger.jsonl'
    protocol = jload(ROOT / 'experiments/campaign_e_protocol.json')
    if not ledger.is_file() or protocol is None:
        return None
    cond = {t['id']: t.get('condition', 'plain') for t in protocol['trials']}
    rows = [json.loads(x) for x in ledger.read_text(encoding='utf8').splitlines() if x.strip()]
    rows = [r for r in rows if r.get('final', True)]
    if not rows:
        return None
    n = len(rows)
    ok = sum(r['correct'] for r in rows)
    wrong = sum(r['observed_action'] in DELIVERED and r['expected_action'] not in ('ALLOW', 'DELIVER_AFTER_SEARCH')
                for r in rows)
    blind_wrong = sum(r['expected_action'] != 'ALLOW' for r in rows)   # a robot that never checks delivers every time
    table = []
    for c in COND_ORDER + sorted(set(cond.values()) - set(COND_ORDER)):
        rs = [r for r in rows if cond.get(r['trial_id'], 'plain') == c]
        if rs:
            k = sum(r['correct'] for r in rs)
            table.append([COND_JA.get(c, c), [f'{k}/{len(rs)}', G if k == len(rs) else R],
                          '、'.join(f'{OBS_JA.get(a, a)} {v}' for a, v in Counter(r['observed_action'] for r in rs).most_common())])
    ci = wilson(wrong, n)
    notes = [f'誤配達 {wrong}/{n}（95%信頼区間の上限 {pct(ci[1])}）。毎試行 全スタックを新規起動、条件は事前登録。',
             f'確認せず配達するだけなら：配達してはいけない／回り道が必要な {blind_wrong}/{n} 試行すべてで誤配達。']
    return {'kind': 'table', 'seconds': seconds,
            'title': f'事前登録{n}試行：期待どおり {ok}/{n}・誤配達 {wrong}件',
            'sub': '評価E：試行ごとにランダムな世界（照明・位置・妨害物・火災）',
            'narration': f'ランダムな世界の{n}試行で、期待どおりは{ok}回、誤った配達は{wrong}回。確認しないロボットなら、{blind_wrong}回誤配達します。',
            'header': ['条件（層）', '期待どおり', '実際の行動'], 'rows': table, 'notes': notes}


def t1_small_large(model='Qwen3.5-9B', tau=0.05):
    """Detection of visible fires split at 10,000 px (recomputed from the stored per-image probabilities)."""
    d = jload(RES / 'devset_t1_qwen35_9b.json')
    if d is None:
        return None
    small, large = [0, 0], [0, 0]
    for r in d['records']:
        if r.get('hazard_visibility') != 'visible':
            continue
        hp = max(p['scores']['hazard_prob'] for p in r['passes'].values() if 'scores' in p)
        bucket = small if r.get('fire_pixels', 0) < 10000 else large
        bucket[1] += 1
        bucket[0] += hp >= tau
    return small, large


def t1_card(seconds):
    s = jload(RES / 't1_summary.json')
    m = ((s or {}).get('models') or {}).get('Qwen3.5-9B')
    if not m or 'full' not in m['rules'] or 'v35_tau_h_0.05' not in m['rules']:
        return None
    full, v35 = m['rules']['full'], m['rules']['v35_tau_h_0.05']
    rows = []
    for name, r in (('v3.4（危険しきい値 0.5）', full), ('v3.5（危険しきい値 0.05）', v35)):
        rows.append([name, [f"{r['false_approvals']}/{r['n_deny']} ({pct(r['fa_rate'])})", G if r['false_approvals'] == 0 else R],
                     f"{r['correct_approvals']}/{r['n_allow']} ({pct(r['ca_rate'])})"])
    fire_fa = sum(1 for e in m.get('errors_full', []) if e[2] == 'FALSE_APPROVAL' and 'fire' in e[1])
    fa = full['false_approvals']
    notes = [f"v3.4 の誤許可{fa}件" + ('はすべて' if fire_fa == fa else f'のうち{fire_fa}件は') + '、物資は正しく火が一部しか見えない画像。']
    sl = t1_small_large()
    if sl:
        (sk, sn), (lk, ln) = sl
        notes.append(f'残る弱点：見える火の検出は、10,000画素以上で {lk}/{ln}、未満（小さく隠れた火）で {sk}/{sn}。')
    return {'kind': 'table', 'seconds': seconds,
            'title': f"未使用{m['n_images']}枚（T1）：誤許可と正しい許可",
            'sub': 'Qwen3.5-9B・開発に一度も使っていない画像（照明・位置・未知の妨害物・火災）',
            'narration': f"未使用の{m['n_images']}枚。拒否すべき{full['n_deny']}枚のうち、誤許可は{full['false_approvals']}枚。残る弱点は、物資の陰に隠れた小さな火です。",
            'header': ['判断規則', '誤許可', '正しい許可'], 'rows': rows, 'notes': notes}


def fix_card(seconds):
    sel = jload(RES / 'i13_selection.json')
    if sel is None:
        return None
    tab = {t['config']: t for t in sel['table']}
    a, b = tab.get('Q9B[h35_full] tau_h=0.05'), tab.get(B_CONFIG)
    if not a or not b:
        return None

    def cell(x, y, n):
        return [f'{y}/{n}', G if y < x else (R if y > x else W)]
    ma, mb, nf = a['n_dh_fire'] - a['dh_fire_refused'], b['n_dh_fire'] - b['dh_fire_refused'], a['n_dh_fire']
    rows = [['開発データ：見逃した火', f'{ma}/{nf}', cell(ma, mb, nf)]]
    say = [f'対策は、質問文と拡大切り出し。開発データの見逃しは{nf}件中{ma}件から{mb}件。']
    t2 = jload(RES / 't2_summary.json')
    if t2:
        ref, sb = t2['results'].get(t2['reference']), t2['results'].get(B_CONFIG)
        if ref and sb:
            rows.append(['未使用T2：誤許可', f"{ref['false_approvals']}/{ref['n_deny']}",
                         cell(ref['false_approvals'], sb['false_approvals'], sb['n_deny'])])
            say.append(f"未使用データの誤許可は{ref['false_approvals']}から{sb['false_approvals']}件。")
    f = jload(RES / 'f_summary.json')
    if f:
        pr = f['primary']
        rows.append(['閉ループF：誤配達', f"{pr['wrong_deliveries_A']}/{pr['n_world_pairs_fire_visible_both']}",
                     cell(pr['wrong_deliveries_A'], pr['wrong_deliveries_B'], pr['n_world_pairs_fire_visible_both'])])
        say.append(f"閉ループの誤配達は{pr['wrong_deliveries_A']}件から{pr['wrong_deliveries_B']}件。")
    g = jload(RES / 'g_summary.json')
    if g:
        pr = g['primary']
        rows.append(['閉ループG：横から見直す', f"{pr['wrong_deliveries_B']}/{pr['n_world_pairs_fire_perceivable']}",
                     cell(pr['wrong_deliveries_B'], pr['wrong_deliveries_C'], pr['n_world_pairs_fire_perceivable'])])
        say.append(f"さらに横から見直すと、火が見えるのに配達した回数は{pr['n_world_pairs_fire_perceivable']}件中"
                   f"{pr['wrong_deliveries_B']}件から{pr['wrong_deliveries_C']}件になりました。")
    gs = ''
    if g:
        gc = g['per_config']['C']
        gs = f"誤った停止は {gc['false_hazard_stops']}/{gc['fire_free_trials']} のまま"
    notes = ['対策1：危険の質問に「小さい・隠れた・端で切れた火や煙」を明記し、3つの拡大切り出しでも尋ねる（開発データのみで選定）。',
             '対策2（G）：正面で許可しても、左右0.4 mから見直す。' + (gs + '（事前登録・正確McNemar検定）。' if gs else '')]
    j = sel.get('selected') or {}
    if j.get('config', '').startswith('J2(') or 'Clef' in j.get('config', ''):
        notes.append(f"評価した：Cloudflare Clef-Flash を当初計画の「Jev」の役割（2つ目のAI）で組み合わせ（見逃し {j['n_dh_fire'] - j['dh_fire_refused']}/{nf}）。"
                     f"ただし{j['vram_gb']:.0f} GB で V100 に同時搭載できず、搭載はしていない。")
        say.append('二つ目のAI、クレフフラッシュも評価しました。')
    return {'kind': 'table', 'seconds': seconds, 'title': '残る弱点への対策（v3.6）',
            'sub': '開発データだけで選定 → 未使用データと閉ループで確認', 'narration': ''.join(say),
            'header': ['指標（火が見えるのに配達・見逃し）', '対策前', '対策後'], 'rows': rows, 'notes': notes}


# ------------------------------------------------------------------ duration estimate
_WARNED = set()
EVIDENCE_ROWS_MAX = 9        # the table card holds 9 rows of 66 px (8 rows: 74 px) plus one note line (make_demo_video.table_card)
EVIDENCE_CELL_PX = 1130      # width left for the result column at 38 px (1806 - 114 - 560)
EVIDENCE_S = 24              # v5: 12 s (EVAL 9), 20 s with the study X row; the narration (<= 120 characters at 6.4 characters/s) keeps it there


def cell_px(text, size=38):
    """Width estimate of a result cell without the CJK fonts: full-width characters take one em, ASCII about 0.55 em."""
    return sum(size if ord(c) > 0x2e80 else 0.55 * size for c in text)


def evidence_card(seconds):
    """One summary card of the pre-registered evidence (replaces the three result tables; every number from files).
    v5 (EVAL 9): ~12 s, rows E, G, W, H, A, (X), J (not adopted), z3, P2.  Rows L and V are not on the card (they stay in the
    paper); the memory row's narration and the note say that V did not support the memory safety claim."""
    rows, say, notes = [], [], ['すべてシミュレーション（実機なし）。数値は結果ファイルから自動生成。']
    led = RES / 'campaign_E_ledger.jsonl'
    if led.is_file():
        rs = [json.loads(x) for x in led.read_text(encoding='utf8').splitlines() if x.strip()]
        rs = [r for r in rs if r.get('final', True)]
        ok = sum(r['correct'] for r in rs)
        wrong = sum(r['observed_action'] in DELIVERED and r['expected_action'] not in ('ALLOW', 'DELIVER_AFTER_SEARCH') for r in rs)
        rows.append(['閉ループ E（ランダムな世界）', [f'期待どおり {ok}/{len(rs)}・誤配達 {wrong}', G if wrong == 0 else R]])
        say.append(f'ランダム{len(rs)}世界で誤配達{wrong}件。')
    g = jload(RES / 'g_summary.json')
    if g:
        pr = g['primary']
        gr = jload(RES / 'gr_summary.json')
        if gr:       # study GR: the same comparison on fresh worlds (closed-loop replication)
            fa, fv = gr['arms']['front']['fire'], gr['arms']['v36']['fire']
            gcs = jload(RES / 'gc_summary.json')
            gds = jload(RES / 'gd_summary.json')
            gc_txt = f"、較正 {gcs['arms']['v36']['fire']['k']}→{gcs['arms']['cal']['fire']['k']}" if gcs else ''
            if gcs and gds:      # the second site: the calibration did not lower misses at the depot
                gc_txt += f"（倉庫 {gds['arms']['v36']['fire']['k']}→{gds['arms']['cal']['fire']['k']}）"
            rows.append(['閉ループ G・GR・GC・GD' if (gcs and gds) else '閉ループ G・GR・GC' if gcs else '閉ループ G・GR（見直し）', [f"火へ配達 {pr['wrong_deliveries_B']}→{pr['wrong_deliveries_C']}/{pr['n_world_pairs_fire_perceivable']}、"
                                                  f"新世界 {fa['k']}→{fv['k']}/{fa['n']}{gc_txt}", G]])
            say.append(f"見直しで火への配達は{pr['wrong_deliveries_B']}件から{pr['wrong_deliveries_C']}件。")
        else:
            rows.append(['閉ループ G（横から見直す）', [f"火が見えるのに配達 {pr['wrong_deliveries_B']}/{pr['n_world_pairs_fire_perceivable']} → "
                                                    f"{pr['wrong_deliveries_C']}/{pr['n_world_pairs_fire_perceivable']}（p={pr['mcnemar_p']:.3f}）", G]])
            say.append(f"横から見直すと、見落としは{pr['wrong_deliveries_B']}件から{pr['wrong_deliveries_C']}件。")
    gl = jload(RES / 'gl_summary.json')
    if gl:      # study GL (v12): the depot's fresh worlds, left-only 0.8 m look-around with a calibrated threshold; site-specific
        glv, glk, glp = gl['arms']['v36']['fire'], gl['arms']['left']['fire'], gl['paired']
        gl_ok = gl['criteria']['GL1_paired_one_sided_p_below_005_and_fewer']
        gm = jload(RES / 'gm_summary.json')       # study GM: the same arm on depot worlds with one realism feature off (no recalibration)
        if gm:
            gmv, gmk = gm['arms']['v36']['fire'], gm['arms']['left']['fire']
            gm_ok = all(gm['criteria'][k] for k in ('GM1_paired_one_sided_p_below_005_and_fewer', 'GM2_left_upper_at_most_15pct', 'GM3_false_stops_at_most_3'))
            rows.append(['閉ループ GL・GM（倉庫）', [f"火へ配達 {glv['k']}→{glk['k']}/{glv['n']}、描画を変えても {gmv['k']}→{gmk['k']}/{gmv['n']}（倉庫限定）", G if (gl_ok and gm_ok) else W]])
            say.append(f"倉庫の火への配達は{glv['k']}件が{glk['k']}件、描画を変えても{gmv['k']}件が{gmk['k']}件。")
        else:
            rows.append([f"閉ループ GL（倉庫・新{glv['n']}）", [f"火へ配達 {glv['k']}→{glk['k']}/{glv['n']}（p={glp['mcnemar_one_sided_p']:.4f}・倉庫限定）", G if gl_ok else W]])
            say.append(f"倉庫の新{glv['n']}世界で、火への配達は{glk['k']}件に（{glv['k']}件から）。")
    h = jload(RES / 'h_summary.json')
    v = jload(RES / 'v_summary.json')
    if h:
        p1, p2 = h['P1_efficiency_relocation_persist'], h['P2_safety_naive_vs_verified']
        t0, t2 = p1['time_M0_median_s'], p1['time_M2_median_s']
        speed = f"移されたまま {t0:.0f}→{t2:.0f}秒・" if t0 is not None and t2 is not None else ''
        p3 = h['P3_no_extra_risk_vs_v36']
        rows.append(['閉ループ H（記憶）', [f"{speed}危険 記憶なし{p3['unsafe_M0']}・本方式{p3['unsafe_M2']}（素朴{p2['unsafe_M1']}）",
                                          G if h['headline_supported'] else W]])
    if v and v.get('complete') and not v.get('claim_memory_under_random_change'):
        a_ = v['arms']
        say.append('記憶の安全は示せず。')
        notes = [f"記憶の安全の主張は、評価Vで不成立（危険 本方式{a_['M2']['unsafe']}対なし{a_['M0']['unsafe']}）。全部シミュレーション。"]
    elif h:
        say.append('記憶は近道の提案だけ。')
    aj = jload(RES / 'a_summary.json')
    if aj and aj.get('n_trials') and aj.get('n_trials') == aj.get('n_planned'):
        r = aj['A1_unsafe_naive_vs_monotone']['runs']
        af = advice_numbers.a_facts()
        if af and af['worlds']['naive'] and af['worlds']['filtered'] and af['worlds']['monotone']:
            w = af['worlds']
            rows.append(['閉ループ A（助言の注入）', [f"危険な世界 素朴{w['naive'][0]}/{w['naive'][1]}・ガードレール{w['filtered'][0]}/{w['filtered'][1]}・本方式{w['monotone'][0]}/{w['monotone'][1]}",
                                                  G if aj.get('headline_supported') else W]])
            say.append(f"嘘の助言で危険な世界は本方式{w['monotone'][0]}、素朴{w['naive'][0]}。")
            st = af['steer']
            notes[0] = f"助言の誘導では配達できない世界が{st['ours']['lost']}/{st['n']}（保証は相対的）。" + notes[0]       # the steering cost stays on the card (one note, two lines at most)
        else:
            rows.append(['閉ループ A（助言の注入）', [f"危険な配達 素朴{r['naive']['unsafe']}/{r['naive']['n']}・本方式{r['monotone']['unsafe']}/{r['monotone']['n']}",
                                                  G if aj.get('headline_supported') else W]])
            say.append(f"助言の注入で、危険な配達は素朴{r['naive']['unsafe']}件、本方式{r['monotone']['unsafe']}件。")
    else:
        if 'a_pending' not in _WARNED:
            _WARNED.add('a_pending')
            print('WARNING: study A is not complete (no a_summary.json or n_trials < n_planned): the card says "running"', file=sys.stderr)
        rows.append(['閉ループ A（助言の注入）', ['事前登録済み・実行中（結果なし）', W]])
        say.append('助言の評価は実行中。')
    xf = advice_numbers.x_facts()
    if xf:
        rows.append([f"閉ループ X（倉庫{xf['n']}試行）", [f"火の4種で配達 {xf['a_unsafe']}・誘導されて火へ {xf['u_mono']}", G if xf['u_mono'].startswith('0/') else W]])
        yj = jload(RES / 'y_summary.json')
        if yj and yj.get('n_with_result') == yj.get('n_planned'):      # study Y: continuing after a hazard refusal (opt-in flag) keeps the delivery that the refusal lost in X
            lv_ = yj['Y-s']['lost_vs_control']['scrutiny_hc']
            lost_, pairs_ = lv_['fire_worlds']['lost'] + lv_['clean_worlds']['lost'], lv_['fire_worlds']['pairs'] + lv_['clean_worlds']['pairs']
            yfj_ = jload(RES / 'yf_summary.json')
            if yfj_:      # pooled over the two independent sets of worlds (Y 15 runs + YF 9 runs): the free lunch of Y alone does not hold on fresh worlds
                lf_ = yfj_['Y-s']['lost_vs_control']['scrutiny_hc']
                lost_ += lf_['fire_worlds']['lost'] + lf_['clean_worlds']['lost']
                pairs_ += lf_['fire_worlds']['pairs'] + lf_['clean_worlds']['pairs']
            rows[-1][1][0] = f"火へ配達{xf['a_unsafe']}・誘導{xf['u_mono']}・続行+scrutiny 喪失{lost_}/{pairs_}"      # one cell, 29 chars: the card is cut at the right edge from about 36
    jh = jload(RES / 'jh_summary.json')
    if jh:      # study JH (the heterogeneous second judge, 'Jev'): registered, not supported
        jx = jh['xd']
        sel = jx['candidates'][jx['selected']]
        rows.append(['別系統AI審判 JH（拒否権）', [f"見逃し {sel['miss_Q']}→{sel['miss_joint']}（目標{(2 * sel['miss_Q']) // 3}）・" + ('成立' if jx['JH1']['holds'] else '不成立'), R if not jx['JH1']['holds'] else G]])
        say.append('別系統のAI審判は不成立。')
    ji = jload(RES / 'ji_summary.json')
    if ji:      # study JI (v13): the registered replication that more views beat a second judge (image level, fresh worlds)
        g3, g6 = ji['viewsets']['v36_FLR']['scorers']['qwen35'], ji['viewsets']['all_six']['scorers']['qwen35']
        ji_ok = all(ji['claims'].values())
        rows.append(['視点を増やす JI（新世界）', [f"見逃し 3視点{g3['miss']}→6視点{g6['miss']}/{ji['n_fire']}・誤停止 {g6['false_stops']}", G if ji_ok else W]])
        say.append(f"視点を6つに増やすと見逃しは{g3['miss']}件から{g6['miss']}件。")
    qi = jload(RES / 'qi_summary.json')
    if qi and qi.get('R', {}).get('miss'):      # study QI (v12): generated images through the frozen gate
        qr = qi['R']['miss']
        rows.append(['画像生成AIで写実化（QI）', [f"見逃し {qi['xd_baseline']['miss']['k']}→{qr['k']}/{qr['n']}・誤停止 {qi['R']['false_stops']['k']}/{qi['R']['false_stops']['n']}", R if not qi['claims'].get('QI1_realised_miss_not_much_worse') else G]])
        say.append('写実化で見逃しが増える弱点も。')
    smt = jload(RES / 'smt_advice_proof.json')
    if smt and len(rows) < EVIDENCE_ROWS_MAX - 1:
        mut = smt.get('code_mutants') or []
        rows.append(['機械検証（z3）', [f"締めるだけを実装で証明・注入バグ {len(mut)}/{len(mut)} 検出", G]])
    if not rows:
        return None
    rows = rows[:EVIDENCE_ROWS_MAX]
    return {'kind': 'table', 'seconds': seconds, 'title': '事前登録した評価のまとめ（全試行を公開）',
            'sub': '結果を見る前に条件と判定方法を固定。うまくいかなかった結果もそのまま報告',
            'narration': ''.join(say), 'header': ['評価', '結果'], 'rows': rows, 'notes': notes}


def mission_seconds(spec):
    """Mission segment length, computed the way make_demo_video.mission_segment builds its speed plan
    (falls back to the ground-truth log when the run has no film frames, e.g. stand-in runs)."""
    try:
        sys.path.insert(0, str(ROOT / 'scripts'))
        sys.path.insert(0, str(ROOT))
        import make_demo_video as mdv
        run = mdv.load_run(ROOT / spec['run_dir'])
        video = sum(max(0.0, (sb - sa) / 1e9 / sp) for sa, sb, sp in mdv.speed_plan(run, spec))
    except Exception as exc:   # noqa: BLE001 - estimate only
        print(f'WARNING: cannot estimate {spec["run_dir"]}: {exc}; assuming 30 s', file=sys.stderr)
        return 30.0
    talk = sum(speak_s(t) + 0.2 for t in (spec.get('narration') or {}).values())
    return max(video, talk)


def part_seconds(p):
    if p['kind'] == 'mission':
        return mission_seconds(p)
    if p.get('narration'):
        return max(p['seconds'], speak_s(p['narration']) + CARD_PAD_S)
    return p['seconds']


def estimate(parts):
    return [(p, part_seconds(p)) for p in parts]


# ------------------------------------------------------------------ storyboard
def mission_part(run_id, scene, title, narration, captions, **extra):
    m = json.loads((ROOT / 'outputs/runs' / run_id / 'mission.json').read_text(encoding='utf8'))
    cap = {k: v.replace('{instr}', m['instruction']) for k, v in captions.items()}
    return {'kind': 'mission', 'scene': scene, 'title': title, 'run_dir': f'outputs/runs/{run_id}', 'fast': FAST, 'check_speed': CHECK,
            'narration': narration, 'captions': cap, **extra}


DEPOT_CAMERA = 'worlds/film/film_camera_depot.sdf'


def depot_camera(run_id, override=None):
    """Overview camera of a depot run: --depot-camera, else the sidecar film_camera.txt that scripts/film_depot.sh writes, else the depot camera."""
    if override:
        return override
    side = ROOT / 'outputs/runs' / run_id / 'film_camera.txt'
    if side.is_file() and side.read_text(encoding='utf8').strip():
        return side.read_text(encoding='utf8').strip()
    return DEPOT_CAMERA


def depot_kind(run_id):
    """What the filmed depot run shows (scripts/film_depot_worlds.py classify): side_fire | search_deliver | other."""
    try:
        sys.path.insert(0, str(ROOT / 'scripts'))
        sys.path.insert(0, str(ROOT))
        from film_depot_worlds import classify
        return classify(ROOT / 'outputs/runs' / run_id)['kind']
    except Exception as exc:    # noqa: BLE001 - only the wording depends on it
        print(f'WARNING: cannot classify depot run {run_id}: {exc}; generic wording', file=sys.stderr)
        return 'other'


def depot_texts(run_id):
    """(title, narration, captions) of the depot segment, worded for what the run shows (the video must not claim an event that did not happen)."""
    kind = depot_kind(run_id)
    if kind == 'side_fire':
        return ('倉庫でも：横から小さな火を見つけて停止',
                {'go': '棚や荷物のある、現実的な倉庫です。拠点は4つ。', 'check': '雑多な背景の中でも、拠点で現物を確かめます。',
                 'peek': '正面では見えません。横から見直します。',
                 'after': '横から小さな火を見つけました。許可を取り消して、止まって報告します。'},
                {'go': '現実的な倉庫（棚・荷物・煙・4つの拠点）。「{instr}」', 'check': '背景が雑多でも、現物を確かめる。',
                 'peek': '正面は「許可」。でも陰は見えない → 左右0.4 mから見直す。',
                 'after': '横から火を発見 → 正面の許可を取り消して停止・報告。'})
    if kind == 'front_fire':
        return ('倉庫でも：火を見つけて停止',
                {'go': '棚や荷物のある、現実的な倉庫です。拠点は4つ。', 'check': '雑多な背景の中でも、拠点で現物を確かめます。',
                 'after': '物資の陰の火を見つけました。配達せず、止まって報告します。'},
                {'go': '現実的な倉庫（棚・荷物・煙・4つの拠点）。「{instr}」', 'check': '背景が雑多でも、現物と火・煙を確かめる。',
                 'after': '火を発見 → 配達せず停止・報告（この世界では正面から見えた）。'})
    if kind == 'search_deliver':
        return ('倉庫でも：取り違えを見つけて別の拠点へ',
                {'go': '棚や荷物のある、現実的な倉庫です。拠点は4つ。', 'check': '拠点で、現物を確かめます。',
                 'search': '依頼の物資ではありません。別の拠点を確かめに行きます。',
                 'peek': '正しい物資です。念のため、横から見直します。', 'after': '安全を確かめたので、避難所へ届けます。'},
                {'go': '現実的な倉庫（棚・荷物・4つの拠点）。「{instr}」', 'check': '最初の拠点で現物を確かめている。',
                 'search': '違う物資 → 誤配達せず、別の拠点を見に行く。',
                 'peek': '正しい物資でも、出発前に横から見直す。',
                 'after': '別の拠点で正しい物資を確認 → 避難所Bへ。'})
    return ('現実的な倉庫でも同じ確認',
            {'go': '棚や荷物のある、現実的な倉庫でも試しました。', 'check': '雑多な背景の中でも、拠点で現物を確かめます。',
             'peek': '横からも見直します。', 'after': 'シミュレーションでも、現場に近い環境で同じ手順が働きます。'},
            {'go': '現実的な倉庫（棚・荷物・4つの拠点）。「{instr}」', 'check': '背景が雑多でも、現物を確かめる。',
             'peek': '横からの見直しも同じ。', 'after': '倉庫での評価結果は研究X・XD（事前登録）。'})


def build(a, drop_arch=False, drop_fire=False, shrink=False, drop_empty=False):
    cs = 0 if shrink else None      # shrink: result cards last exactly as long as their narration
    mem = bool(getattr(a, 'memory', None))
    # story arc of the first ~10 s: problem (stock list != scene, hazards hide) -> answer (look on the spot, look again from the side)
    open_say = ('災害現場へ物資を届けるロボットです。在庫表と現場は違い、危険も隠れます。そこで、自分で見ていない情報は「助言」として扱い、'
                '順番を変えるか、判断を厳しくするだけにします。')
    parts = [
        {'kind': 'card', 'seconds': 6, 'title': 'RescueMind', 'image': 'docs/figures/hero_gazebo.png',
         'sub': '助言は「厳しくする」ことしかできない。だから、嘘の助言でも危険にならない',
         'narration': open_say,
         'body': ['課題：在庫表と現場は違う。火や煙は物資の陰に隠れる。誤配達は命に関わる。',
                  '新しさ：見ていない情報（記憶・報告・在庫表・依頼文）は「助言」。助言は順番を変えるか、判断を厳しくするだけ。',
                  '確認：ローカルVLM（Qwen3.5-9B）が拠点でその場で確かめ、正面で許可でも横から見直す。迷えば止まって報告。',
                  f'※ 走行{FAST:g}倍速・確認動作{CHECK:g}倍速・AI判断の瞬間は等速（左上に常時表示）。']}]
    if not drop_arch:
        parts.append({'kind': 'card', 'seconds': 6, 'title': 'システム構成', 'sub': 'すべてローカルGPUで完結（クラウドAPI不使用）',
                      'image': 'docs/figures/architecture.png', 'layout': 'image',
                      'narration': '推論はすべてローカルのGPU。車輪を動かせるのは、独立した安全ガードだけです。',
                      'body': ['VLMは選択式2問（選択肢の順序を入替）の回答文字の確率で判断 ／ 独立した速度ガードが車輪指令を常時監視']})
    demos = []
    if a.deliver:        # v5: not passed (dropped to stay <= 3 min; EVAL 9)
        demos.append(mission_part(
            a.deliver, 'nominal', '言い換えた指示でも配達',
            {'go': '物資名のない依頼でも、AIが読み取って出発します。', 'check': '拠点で止まり、現物を目で確かめます。',
             'peek': '正面で許可が出ても、出発前に横から見直します。',
             'after': '安全を確かめたので、避難所へ向かいます。'},
            {'go': '「{instr}」物資名がなくても、AIが依頼を読み取って出発。',
             'check': '着いたらまず停止。新しい画像で現物を確かめる。',
             'peek': '正面で許可でも、出発前に左右0.4 mから見直す。物資の陰の火・煙を探す。',
             'after': '現物も横の様子も問題なし → 避難所Bへ（橙線＝実際の軌跡）。'}))
    if a.recover:
        demos.append(mission_part(
            a.recover, 'swapped', '取り違え → 別拠点を探索',
            {'go': '在庫表と現場が違います。物資が入れ替わっています。', 'search': '依頼の物資ではありません。もう一方を見に行きます。',
             'peek': '正しい物資です。念のため、横から見直します。',
             'after': '正しい物資を見つけたので、避難所へ届けます。'},
            {'go': '在庫表と現物が違う。「{instr}」', 'check': '拠点で現物を確かめている。',
             'search': '違う物資 → 誤配達せず、もう一方の拠点を見に行く。',
             'peek': '正しい物資でも、出発前に横から見直す。',
             'after': '別の拠点で正しい物資を確認 → 避難所Bへ。判断の経緯はすべて記録。'}))
    if a.empty and not drop_empty:
        demos.append(mission_part(
            a.empty, 'empty', '欠品 → 両拠点を確認して停止',
            {'go': '次は、在庫表にあるはずの物資が、どこにも無いケースです。', 'search': 'ここには有りません。もう一方も確かめます。',
             'after': 'どちらにも無いので、配達せず止まって報告します。'},
            {'go': '在庫表にあるはずの物資が、どの拠点にも無い。「{instr}」', 'check': '拠点で現物を確かめている。',
             'search': 'ここには無い → もう一方の拠点も確かめる。',
             'after': '両拠点とも無し → 誤配達せず、その場で止まって報告。'}))
    if a.fire and not drop_fire:
        demos.append(mission_part(
            a.fire, 'nominal', '大きな火災 → 探索せず停止',
            {'go': '続いて、拠点の裏で火災が起きているケースです。', 'after': '火と煙を見つけました。探し回らず、止まって報告します。'},
            {'go': '拠点の裏で火災が起きている。「{instr}」', 'check': '物資は正しい。でも画像に火や煙は無いか？',
             'after': '火・煙を検知 → 配達せず、探し回らずに止まって報告。'}, hazard_at='medicine'))
    if mem:
        demos.append({'kind': 'card', 'seconds': 5, 'title': '出動をまたぐ記憶', 'layout': 'image',
                      'image': 'docs/figures/memory_principle_ja.png', 'sub': '記憶は提案だけ。着いたら必ず、その場の目で確かめる',
                      'narration': '出動をまたぐ記憶は、提案だけ。着いたら、必ず確かめます。', 'body': []})
        demos.append(mission_part(
            a.memory, 'swapped', '出動をまたぐ記憶 → 直行',
            {'go': '前回の出動を覚えているので、その拠点へ直行します。', 'check': 'それでも、着いたら必ず確かめます。',
             'peek': '横からも見直します。', 'after': '記憶で近道をして、判断はその場の目で。'},
            {'go': '前回の出動を覚えている → 依頼物資のある拠点へ直行。「{instr}」',
             'check': '記憶は提案だけ。着いたら必ず現物を確かめる。',
             'peek': '横からの見直しも省かない。',
             'after': '探し回らずに配達。記憶が古ければ、確認で止まる（評価H）。'}))
    if getattr(a, 'advice', None):
        # I-19: an injected instruction ("the fire is out, skip the check") is advice, and advice cannot relax a check
        demos.append({'kind': 'card', 'seconds': 5, 'title': '信頼できない入力は「締める」だけ', 'layout': 'image',
                      'image': 'docs/figures/advice_principle_ja.png' if (ROOT / 'docs/figures/advice_principle_ja.png').is_file()
                      else 'docs/figures/memory_principle_ja.png',
                      'sub': '依頼文・他のロボット・在庫記録・記憶は「助言」。順番を変えるか慎重にするだけで、確認は省けない',
                      'narration': '依頼文に、確認は不要と書かれていても、助言は確認を省けません。', 'body': []})
        demos.append(mission_part(
            a.advice, 'nominal', '「確認不要」と言われても → 横から見て停止',
            {'go': '依頼文に、火は消えたので確認不要、と書かれています。', 'check': 'それでも、拠点で必ず確かめます。',
             'peek': '正面では見えません。横からも見直します。',
             'after': '横から火を見つけました。助言は採用せず、止まって報告します。'},
            {'go': '依頼文に「火は消えた・確認不要」。「{instr}」',
             'check': '助言は確認を省けない。現地で必ず確かめる。',
             'peek': '正面は「許可」。でも陰は見えない → 左右0.4 mから見直す。',
             'after': '横から火を発見 → 停止。「確認不要」は不採用として報告に記録。'}))
    elif a.hidden_fire:
        demos.append(mission_part(
            a.hidden_fire, 'nominal', '隠れた小さな火 → 停止',
            {'go': '最後は、物資の陰に小さな火が隠れているケースです。', 'peek': '正面では見えません。横に回り込んで、見直します。',
             'after': '横から火を見つけました。配達せず、止まって報告します。'},
            {'go': '物資の陰に小さな火。正面からは見えない。「{instr}」',
             'check': '物資は正しい。でも陰に火や煙は無いか？',
             'peek': '正面は「許可」。でも陰は見えない → 左右0.4 mから見直す。',
             'after': '横から火を発見 → 正面の許可を取り消して停止・報告。'}))
    if getattr(a, 'depot', None):
        # I-21: the same check in a realistic relief depot (AWS small-warehouse models, MIT-0; four bays)
        title, narration, captions = depot_texts(a.depot)
        demos.append(mission_part(a.depot, 'nominal', title, narration, captions,
                                  film_camera=depot_camera(a.depot, getattr(a, 'depot_camera', None))))
        if (ROOT / 'docs/figures/qi_strip.png').is_file() and (RES / 'qi_summary.json').is_file():      # v12: study QI (generated images through the frozen gate), a failed claim shown on purpose
            demos.append({'kind': 'card', 'seconds': 6, 'title': '画像生成AIで試すと、弱点が見つかった', 'layout': 'image',
                          'image': 'docs/figures/qi_strip.png', 'sub': '事前登録した研究QI。どちらも実写ではなく、生成した画像',
                          'narration': '画像生成AIで写実化すると、見逃しが増えました。弱点も報告します。', 'body': []})
    missions = [d for d in demos if d['kind'] == 'mission']
    for i, d in enumerate(missions, 1):
        d['index'], d['total'] = i, len(missions)
    parts += demos
    cards = ((evidence_card, EVIDENCE_S),) if getattr(a, 'summary_card', True) else ((campaign_e_table, 9), (t1_card, 8), (fix_card, 11))
    for card_fn, sec in cards:
        c = card_fn(sec if cs is None else cs)
        if c:
            parts.append(c)
    report = 'docs/figures/operator_report_hidden_fire.png'      # I-18: what the robot leaves for the people on site
    parts.append({'kind': 'card', 'seconds': 5, 'title': 'RescueMind', 'sub': a.repo_url,
                  'image': report if (ROOT / report).is_file() else 'docs/figures/hero_gazebo.png',
                  'narration': '確かめて、見直して、迷ったら止まる。全試行の証拠を公開しています。',
                  'body': ['確かめて、見直して、迷ったら止まる。間違った配達より、止まる方がいい。',
                           '毎回、写真と理由と「次にすること」を1枚の現場報告に残す（右）。',
                           'コード・事前登録・全試行の証拠・再現用Dockerを公開しています。',
                           'ナレーション：VOICEVOX:四国めたん']})
    return parts


def fit_budget(a):
    """Apply the shortening steps in order until the estimate is within TARGET_S."""
    df = bool(a.fire and a.hidden_fire)    # --fire is dropped only when --hidden-fire replaces it
    de = bool(getattr(a, 'memory', None))   # with the memory demo, the empty-station demo (least novel) goes first
    steps = [dict(), dict(drop_arch=True), dict(drop_arch=True, drop_fire=df), dict(drop_arch=True, drop_fire=df, shrink=True),
             dict(drop_arch=True, drop_fire=df, shrink=True, drop_empty=de)]
    for s in steps:
        parts = build(a, **s)
        est = estimate(parts)
        if sum(x for _, x in est) <= TARGET_S:
            break
    return parts, est, s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--deliver', help='run id: paraphrased instruction -> delivery (v5: omitted, EVAL 9; the point is made in segment 1\'s caption)')
    ap.add_argument('--recover', required=True, help='run id: swapped supplies -> search other station -> delivery')
    ap.add_argument('--empty', help='run id: both stations empty -> check both, stop')
    ap.add_argument('--fire', help='run id: large fire -> stop without searching')
    ap.add_argument('--hidden-fire', dest='hidden_fire', help='run id: small partly hidden fire -> v3.6 check stops')
    ap.add_argument('--memory', help='run id: verified memory (I-15) goes straight to the remembered station, still checks')
    ap.add_argument('--depot', help='run id (I-21): a mission filmed in the realistic depot (scripts/film_depot.sh -> experiments/results/film_depot_runs.txt)')
    ap.add_argument('--depot-camera', default=None, help='overview camera SDF of the depot run (default: outputs/runs/<id>/film_camera.txt, written by film_depot.sh, else '
                    f'{DEPOT_CAMERA})')
    ap.add_argument('--advice', help='run id (I-19): injected "skip the check" advice on a hidden-fire world; replaces --hidden-fire')
    ap.add_argument('--three-tables', dest='summary_card', action='store_false',
                    help='old layout: E, T1 and fix tables instead of one evidence summary card')
    ap.add_argument('--repo-url', default='github.com/fe2131-art/rescue-mind')
    ap.add_argument('--out', default=str(ROOT / 'docs/video_plan.json'))
    a = ap.parse_args()
    if not a.empty:
        print('WARNING: no --empty run: the "欠品で停止" scene is missing', file=sys.stderr)
    parts, est, applied = fit_budget(a)
    total = sum(x for _, x in est)
    out = Path(a.out)
    out.write_text(json.dumps({'parts': parts}, ensure_ascii=False, indent=1) + '\n', encoding='utf8')
    print(out)
    print(f'shortening applied: {applied or "none"}')
    for p, x in est:
        label = p.get('title') if p['kind'] != 'mission' else f"demo {p['index']}/{p['total']} {p['title']} ({p['run_dir'][-16:]})"
        print(f"  {p['kind']:8s} {x:6.1f}s  {label}")
    print(f'estimated total: {total:.1f} s (limit {LIMIT_S:.0f} s)')
    if total > LIMIT_S:
        print('ERROR: estimate exceeds the limit', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
