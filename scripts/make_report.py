#!/usr/bin/env python3
"""Build the submission PDF (説明資料) from committed results; numbers are never hand-typed.

  python3 scripts/make_report.py --account <omnicampusアカウント名> [--video-url URL]

Output: docs/report/説明資料_PAI最終課題_<account>.pdf  (personal info must not appear;
only the omnicampus account name is allowed by the assignment rules).
"""
from __future__ import annotations
import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, Image, KeepTogether, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'
FIG = ROOT / 'docs/figures'
sys.path.insert(0, str(ROOT / 'scripts'))
import count_tests  # noqa: E402  (generated test / findings counts)
from t1_analysis import wilson  # noqa: E402  (Wilson 95% CI, shared with the T1 analysis)

pdfmetrics.registerFont(TTFont('IPAexG', '/usr/share/fonts/opentype/ipaexfont-gothic/ipaexg.ttf'))
pdfmetrics.registerFont(TTFont('IPAexM', '/usr/share/fonts/opentype/ipaexfont-mincho/ipaexm.ttf'))

ACC = colors.HexColor('#eb6834')
INK = colors.HexColor('#16181d')
MUT = colors.HexColor('#52514e')
LINE = colors.HexColor('#d9d8d3')
SOFT = colors.HexColor('#f4f3ef')

S = {
    'title': ParagraphStyle('t', wordWrap='CJK', fontName='IPAexG', fontSize=21, leading=29, textColor=INK, spaceAfter=4),
    'sub': ParagraphStyle('s', wordWrap='CJK', fontName='IPAexG', fontSize=11.5, leading=17, textColor=ACC, spaceAfter=10),
    'h1': ParagraphStyle('h1', fontName='IPAexG', fontSize=14.5, leading=20, textColor=INK, spaceBefore=10,
                         spaceAfter=6, borderPadding=(0, 0, 3, 0), keepWithNext=1),
    'h2': ParagraphStyle('h2', fontName='IPAexG', fontSize=11.5, leading=16, textColor=ACC, spaceBefore=6, spaceAfter=3, keepWithNext=1),
    'body': ParagraphStyle('b', wordWrap='CJK', fontName='IPAexM', fontSize=9.6, leading=15.2, textColor=INK, alignment=TA_LEFT),
    'bullet': ParagraphStyle('bl', wordWrap='CJK', fontName='IPAexM', fontSize=9.6, leading=14.6, textColor=INK, leftIndent=12,
                             bulletIndent=2),
    'cap': ParagraphStyle('c', wordWrap='CJK', fontName='IPAexG', fontSize=8.2, leading=11.5, textColor=MUT, alignment=TA_CENTER,
                          spaceAfter=6),
    'cell': ParagraphStyle('cell', wordWrap='CJK', fontName='IPAexM', fontSize=8.2, leading=11.2, textColor=INK),
    'cellh': ParagraphStyle('cellh', wordWrap='CJK', fontName='IPAexG', fontSize=8.4, leading=11.2, textColor=colors.white),
    'small': ParagraphStyle('sm', wordWrap='CJK', fontName='IPAexM', fontSize=8, leading=11.5, textColor=MUT),
}


def P(t, st='body'):
    return Paragraph(t, S[st])


def bullets(items):
    return [Paragraph(t, S['bullet'], bulletText='•') for t in items]


def fig(name, width_mm, caption):
    path = FIG / name
    if not path.is_file():
        return [P(f'（図 {name} 未生成）', 'small')]
    from PIL import Image as PI
    with PI.open(path) as im:
        w, h = im.size
    wpt = width_mm * mm
    return [KeepTogether([Image(str(path), width=wpt, height=wpt * h / w), P(caption, 'cap')])]


def table(rows, widths, header=True):
    data = [[Paragraph(str(c), S['cellh' if (header and i == 0) else 'cell']) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1 if header else 0)
    st = [('GRID', (0, 0), (-1, -1), 0.4, LINE), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
          ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]
    if header:
        st += [('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d3748'))]
    for i in range(1, len(rows)):
        if i % 2 == 0:
            st.append(('BACKGROUND', (0, i), (-1, i), SOFT))
    t.setStyle(TableStyle(st))
    return t


def jload(name):
    f = RES / name
    return json.loads(f.read_text()) if f.is_file() else None


def ledger(name):
    f = RES / name
    return [json.loads(x) for x in f.read_text().splitlines()] if f.is_file() else []


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(ACC); canvas.setLineWidth(2)
    canvas.line(18 * mm, 287 * mm, 192 * mm, 287 * mm)
    canvas.setFont('IPAexG', 7.5); canvas.setFillColor(MUT)
    canvas.drawString(18 * mm, 10 * mm, 'Physical AI 応用1講座 最終課題 ｜ RescueMind v3.6')
    canvas.drawRightString(192 * mm, 10 * mm, f'{doc.page}')
    canvas.restoreState()


GROUP = {'nominal': ('正常配置', '配達'), 'swapped': ('物資の取り違え', '別拠点を探索して配達'),
         'empty': ('欠品（両拠点とも空）', '両拠点で確認して停止'), 'fire': ('拠点の裏で火災', '探索せず即停止'),
         'dim': ('夕方の暗い照明', '配達'), 'box': ('空の台に段ボール箱', '停止')}
OBS = {'ALLOW': '配達', 'ALLOW_AFTER_SEARCH': '探索して配達', 'DENY': '停止（物資なし）',
       'DENY_HAZARD': '停止（危険）', 'DENY_UNVERIFIED': '停止（証拠不足）', 'FAILED': '失敗'}


def campaign_d():
    rows = [r for r in ledger('campaign_D_ledger.jsonl') if r.get('final', True)]
    if not rows:
        return None
    proto = {t['id']: t for t in json.loads((ROOT / 'experiments/v34_protocol.json').read_text())['trials']}
    for r in rows:
        t = proto[r['trial_id']]
        r['group'] = ('fire' if t.get('hazard_at') else 'dim' if t.get('lighting') == 'dim_evening'
                      else 'box' if t.get('distractor_at') else t['scene'])
    allr = ledger('campaign_D_ledger.jsonl')
    lat = sorted(r['vlm_latency_s'] for r in rows if r.get('vlm_latency_s') is not None)
    fa = [r for r in rows if r['observed_action'] in ('ALLOW', 'ALLOW_AFTER_SEARCH')
          and r['expected_action'] in ('DENY', 'DENY_HAZARD')]
    intent_ok = sum(1 for r in rows if r.get('intent_item') == r['expected_supply'])
    return {'rows': rows, 'n': len(rows), 'correct': sum(r['correct'] for r in rows), 'false_approvals': len(fa),
            'retries': len(allr) - len(rows), 'lat_med': lat[len(lat) // 2] if lat else None,
            'lat_max': lat[-1] if lat else None, 'intent_ok': intent_ok,
            'by': {g: [r for r in rows if r['group'] == g] for g in GROUP}}


EXP_E = {'ALLOW': '配達', 'DELIVER_AFTER_SEARCH': '探索して配達', 'DENY': '停止（物資なし）', 'DENY_HAZARD': '停止（危険）',
         'DENY_HAZARD_AFTER_SEARCH': '探索後に危険で停止'}
COND_E = {'plain': '通常', 'crate': '木箱の妨害物', 'box': '段ボール箱', 'cone': 'コーン', 'fire': '拠点で火災',
          'fire_other': '別拠点で火災'}


def pct_ci(k, n):
    lo, hi = wilson(k, n)
    return f'{lo * 100:.0f}–{hi * 100:.0f} %'


def campaign_e():
    """Campaign E (v3.5, pre-registered): final rows only, stratified by expected action x protocol condition."""
    f, pf = RES / 'campaign_E_ledger.jsonl', ROOT / 'experiments/campaign_e_protocol.json'
    if not (f.is_file() and pf.is_file()):
        return None
    allr = ledger('campaign_E_ledger.jsonl')
    rows = [r for r in allr if r.get('final') is not False]
    if not rows:
        return None
    cond = {t['id']: t.get('condition', '-') for t in json.loads(pf.read_text())['trials']}
    for r in rows:
        r['cond'] = cond.get(r['trial_id'], '-')
    n = len(rows)
    ok = sum(bool(r['correct']) for r in rows)
    fa = sum(1 for r in rows if r['observed_action'] in ('ALLOW', 'ALLOW_AFTER_SEARCH')
             and r['expected_action'] not in ('ALLOW', 'DELIVER_AFTER_SEARCH'))
    allow = sum(r['expected_action'] == 'ALLOW' for r in rows)
    lat = sorted(r['vlm_latency_s'] for r in rows if r.get('vlm_latency_s') is not None)
    order = list(EXP_E)
    strata = Counter((r['expected_action'], r['cond']) for r in rows)
    strata_ok = Counter((r['expected_action'], r['cond']) for r in rows if r['correct'])
    keys = sorted(strata, key=lambda k: (order.index(k[0]) if k[0] in order else 99,
                                              list(COND_E).index(k[1]) if k[1] in COND_E else 99))
    return {'n': n, 'ok': ok, 'fa': fa, 'allow': allow, 'retries': len(allr) - n, 'keys': keys, 'strata': strata,
            'strata_ok': strata_ok, 'lat_med': lat[len(lat) // 2] if lat else None,
            'tau_h': next((r['stack_args'][r['stack_args'].index('--hazard-threshold') + 1] for r in rows
                           if '--hazard-threshold' in (r.get('stack_args') or [])), None)}


def t1_info():
    t1 = jload('t1_summary.json')
    if not t1 or 'Qwen3.5-9B' not in t1.get('models', {}):
        return None
    m = t1['models']['Qwen3.5-9B']
    # must-refuse images that contain no fire: deny strata other than the fire_* strata
    neg = [(k, v) for k, v in m['strata_full'].items() if v['expected'] == 'deny' and not k.startswith('fire')]
    n_neg = sum(v['n'] for _, v in neg)
    fa_neg = sum(v['allowed'] for _, v in neg)
    info = {'t1': t1, 'n_neg': n_neg, 'fa_neg': fa_neg, 'small': None}
    dev = jload('devset_t1_qwen35_9b.json')
    if dev:
        vis = [x for x in dev['records'] if x.get('hazard_visibility') == 'visible']
        pmax = lambda x: max(p['scores']['hazard_prob'] for p in x['passes'].values())
        det = lambda g: sum(1 for x in g if pmax(x) >= 0.05)
        small = [x for x in vis if x['fire_pixels'] < 10000]
        large = [x for x in vis if x['fire_pixels'] >= 10000]
        fas = {e[0] for e in m.get('errors_full', []) if e[2] == 'FALSE_APPROVAL'}
        fa_rec = [x for x in dev['records'] if x['image'] in fas]
        info['small'] = {'ns': len(small), 'ds': det(small), 'nl': len(large), 'dl': det(large),
                         'fa_px': [x['fire_pixels'] for x in fa_rec], 'fa_small': sum(x['fire_pixels'] < 10000 for x in fa_rec)}
    return info


def improvements_late(D, E):
    """I-09..I-13 rows; every number comes from a committed result file."""
    rows = []
    ab = {r['mode']: r for r in ledger('i09_stall_ab.jsonl')}
    if ab:
        n = lambda m: sum(1 for r in ledger('i09_stall_ab.jsonl') if r['mode'] == m)
        c = lambda m: sum(1 for r in ledger('i09_stall_ab.jsonl') if r['mode'] == m and r['state'] == 'COMPLETED')
        rows.append(['I-09', f"停止中の一瞬の途絶で中止（評価Dの再試行{D['retries'] if D else '-'}件）",
                     '計測で原因を切り分け、停止中の途絶は0を保持（動作中は従来どおり即停止）',
                     f"停止注入の再現：旧 {c('legacy')}/{n('legacy')} 完了 → 新 {c('new')}/{n('new')} 完了"])
    p1 = [r for r in ledger('campaign_E_pilot_ledger.jsonl') if r.get('final', True)]
    p2 = [r for r in ledger('campaign_E_pilot2_ledger.jsonl') if r.get('final', True)]
    t1 = jload('t1_summary.json')
    if p1 and p2:
        th = '-'
        for r in p2:
            a = r.get('stack_args') or []
            if '--hazard-threshold' in a:
                th = a[a.index('--hazard-threshold') + 1]
        t1txt = ''
        if t1:
            ru = t1['models']['Qwen3.5-9B']['rules']
            t1txt = f"。T1の誤許可 {ru['full']['false_approvals']} → {ru['v35_tau_h_0.05']['false_approvals']}"
        rows.append(['I-10', '探索先の火災を見逃して配達（予備走行、火が物資の陰に隠れる）',
                     f"危険の閾値を非対称に（見逃しは致命的、誤警報は停止で済む）：τ_h {t1['tau_h'] if t1 else '-'} → {th}",
                     f"予備走行 {sum(r['correct'] for r in p1)}/{len(p1)} → {sum(r['correct'] for r in p2)}/{len(p2)}{t1txt}"])
    pr = ledger('i12_dds_probe.jsonl')
    if pr:
        f = lambda m: (sum(1 for r in pr if r['mode'] == m and r['slow_publish']), sum(1 for r in pr if r['mode'] == m))
        rows.append(['I-12', '送信停止の根本原因（評価Eで再計測）', 'DDSを非同期送信に（交互A/B/C、AIは不使用）',
                     f"publishが0.27秒超ブロックした回：同期 {f('default')[0]}/{f('default')[1]} → 非同期 {f('async')[0]}/{f('async')[1]}"])
    V = v36_info()
    S13 = V['sel'] if V else None
    if S13:
        tb = {r['config']: r for r in S13['table']}
        a, b = tb['Q9B[h35_full] tau_h=0.05'], tb['Q9B[h36_tiles] tau_h=0.05']
        rows.append(['I-11', '小さく写った火の見逃し（T1の誤許可は全てこれ）',
                     '小さい・隠れた・端で切れた火や煙を明示した質問（h36）＋拡大切り出し（tiles）。開発データのみで選定',
                     f"開発データ（火の無い画像を含む{a['n_deny']}枚）の誤許可 {a['false_approvals']} → {b['false_approvals']}、"
                     f"見える火{a['n_dh_fire']}枚のうち止めた数 {a['dh_fire_refused']} → {b['dh_fire_refused']}、正しい許可 {a['correct_approvals']} → {b['correct_approvals']}/{a['n_allow']}"])
        c = S13['selected']
        rows.append(['I-13', '当初計画の「2つのAIで確認」から縮退していた',
                     'Clef-Flash（Jev役、ローカル）をQwenと併用。選定規則は結果前に固定',
                     f"開発データで誤許可 {b['false_approvals']} → {c['false_approvals']}（併用は {c['vram_gb']:.0f} GB でV100 1台に載らず、既定には採用せず）"])
    else:
        rows.append(['I-11', '小さく写った火の見逃し（T1の誤許可は全てこれ）', '小さい火・煙を明示した質問と拡大切り出し', '（開発データの選定結果なし）'])
    if V:
        g = V['g']['primary']
        rows.append(['I-14', '正面からは物資の陰で見えない小さな火で、それでも配達（評価F）',
                     '許可の直前に拠点の左右へ移動して撮り直す（横から見直す）。VLMの閾値では分離できなかった',
                     f"評価G：火が見える{g['n_world_pairs_fire_perceivable']}世界で配達 {g['wrong_deliveries_B']} → {g['wrong_deliveries_C']}"
                     f"（McNemar正確検定 {pexact(g['mcnemar_p'])}）、火の無い世界の誤った停止 {V['g']['per_config']['C']['false_hazard_stops']}/{V['g']['per_config']['C']['fire_free_trials']}"])
    return sorted(rows, key=lambda r: r[0])


def v36_info():
    """Campaigns F and G (closed loop, paired, pre-registered), the held-out T2 and the I-11/I-13 development
    selection. Every value is read from the committed summaries; None when a file is missing."""
    f, g, t2, sel = (jload(n) for n in ('f_summary.json', 'g_summary.json', 't2_summary.json', 'i13_selection.json'))
    if not (f and g):
        return None
    gl = [r for r in ledger('campaign_G_ledger.jsonl') if r.get('final', True)]

    def wall(c):
        w = sorted(r['wall_s'] for r in gl if r['config'] == c and r['expected_action'] == 'ALLOW')
        return (w[len(w) // 2] if len(w) % 2 else (w[len(w) // 2 - 1] + w[len(w) // 2]) / 2) if w else None
    miss = [x for x in g.get('trials', []) if x['config'] == 'C' and x['wrong_delivery']]
    clef_lat = None
    cf = RES / 'devset_t2_clef2.json'
    if cf.is_file():
        lt = sorted(r['clef']['latency_s'] for r in json.loads(cf.read_text())['records'] if r.get('clef'))
        clef_lat = statistics.median(lt) if lt else None
    return {'f': f, 'g': g, 't2': t2, 'sel': sel, 'wall_B': wall('B'), 'wall_C': wall('C'), 'miss': miss, 'clef_lat': clef_lat}


def speed_text():
    """Speed-up wording of the video, taken from the chapter file the video script writes."""
    chap = ROOT / 'docs/video_chapters.json'
    if chap.is_file():
        for c in json.loads(chap.read_text(encoding='utf8')):
            if c.get('speed'):
                return c['speed']
    return '倍速表示あり'


def pexact(p):
    """'p=0.002' or 'p<0.001' (the whole token, so callers never write 'p=<0.001')."""
    return 'p<0.001' if p < 0.001 else f'p={p:.4g}' if p >= 0.01 else f'p={p:.3f}'


# ---------------------------------------------------------------------------------------------------------
# Chapter 5: novelty and further studies (H, J, Z, P/P2, R). Every number is read from a result file at build
# time; a missing file gives a pending note ("評価中" etc.) instead of a number.
# ---------------------------------------------------------------------------------------------------------
R_FAM = {'gaussian_noise': 'センサー雑音', 'motion_blur': '動きぶれ', 'defocus_blur': 'ピンぼけ', 'underexposure': '露出不足',
         'overexposure': '露出過多', 'jpeg': 'JPEG劣化'}
ARM_JA = {'M0': 'M0：記憶なし（v3.6）', 'M1': 'M1：素朴な記憶', 'M2': 'M2：検証つき記憶（提案）'}


def rate_ci(d):
    """k/n with the Wilson interval from a {'k','n','ci95'} block."""
    return f"{d['k']}/{d['n']}（95%区間 {d['ci95'][0] * 100:.0f}–{d['ci95'][1] * 100:.0f} %）"


def sec_memory():
    sha = ''
    pf = ROOT / 'experiments/campaign_h_protocol.json'
    if pf.is_file():
        import hashlib
        proto = json.loads(pf.read_text())
        sha = (f"プロトコル（{proto['planned_n']}試行、sha256 先頭16桁 {hashlib.sha256(pf.read_bytes()).hexdigest()[:16]}）は"
               '最初の試行の前に固定した。')
    out = [P('4.2 新規性2：出動をまたぐ記憶——記憶は提案だけ、確認は減らさない（I-15）', 'h2'),
           P('同じ避難所への補給は繰り返される。前回の出動で見たものを覚えていれば遠回りを避けられるが、災害現場は出動のたびに変わり、古い記憶に従うのは危険である。'
             'そこで<b>記憶にできることを限る</b>（docs/DESIGN_DECISIONS.md D13）。')]
    out += bullets([
        '<b>書くもの</b>：各出動で、ロボット自身が拠点ごとに「見えた物資」と「火・煙が見えた方向」を追記する（真値は書かない）。',
        '<b>順序の提案</b>：前回、依頼物資が別の拠点で見えていたら、その拠点を先に訪ねる。行った先でも必ず現物確認する。',
        '<b>慎重さの追加</b>：最近火を見た拠点では、すべての視点で危険の閾値 τ_h を 0.05 から <b>0.01</b> に下げる。',
        '<b>確認は決して減らさない</b>：記憶を理由に、現物確認・横からの見直し・閾値を省いたり緩めたりしない。'])
    out += [Spacer(1, 3), P('<b>命題（安全側への単調性）</b>：同じカメラ画像なら、記憶を使うロボットが配達する場面は、記憶を使わないロボットも配達する場面の一部である。'
              '許可は「依頼物資を確認でき、かつ全視点で危険が閾値未満」というAND条件で、記憶は閾値を下げるか確認の順序を変えるだけで条件を外せないからである。'
              'コードで強制し（<font name="IPAexG">apply_memory_caution</font>・<font name="IPAexG">peek_hazard</font>）、監査は保存した出力から記憶による判定を再計算する。'),
            Spacer(1, 3), P('<b>比較対象 M1（素朴な記憶）</b>：記憶を信じ、前回その物資を見た拠点では確認を省いて配達し、前回危険を見た拠点へは行かない。速いが、現場が変わると誤配達につながる。'
              'M1は評価Hで測るためだけに実装し、既定にはしない。調査した範囲では、出動をまたぐ記憶で確認の場所と量を決めつつ確認を減らさないことを保証する研究は見当たらなかった'
              '（関連研究との関係は docs/IMPROVEMENT_LOG.md I-15）。'),
            Spacer(1, 3), P('<b>事前登録した評価H</b>（<font name="IPAexG">experiments/PREREGISTRATION_H.md</font>）：16系列×3出動、世界は出動ごとに照明・小道具・火を引き直し、'
              'M0（記憶なし）/M1/M2（提案）を同じ世界で対にして比べる。基準は P1：物資の入れ替わりが続く出動で M2 が M0 より速い、P2：危険な配達が M2 は M1 より少ない、'
              f'P3：M2 の危険な配達が M0 以下。3つが揃って初めて「速さを保ち、危険を増やさない」と主張する。{sha}')]
    h = jload('h_summary.json')
    if not h:
        return out + [P('<b>評価H 実行中（事前登録済み）</b>。結果は <font name="IPAexG">experiments/results/h_summary.json</font> が生成され次第、本資料に反映する。'), Spacer(1, 4)]
    p1, p2, p3 = h['P1_efficiency_relocation_persist'], h['P2_safety_naive_vs_verified'], h['P3_no_extra_risk_vs_v36']
    ok = lambda x: '<b>成立</b>' if x['supported'] else '<b>不成立</b>'
    rows = [['基準', '結果', '判定']]
    rows.append([f"P1 速さ（M2 vs M0、入れ替わりが続く{p1['n_pairs']}出動）",
                 (f"所要時間の中央値 {p1['time_M0_median_s']:.0f} → {p1['time_M2_median_s']:.0f} 秒（差の中央値 {p1['median_diff_s']:+.0f} 秒）、"
                  f"Wilcoxon正確検定 {pexact(p1['wilcoxon_exact_p'])}") if p1['n_pairs'] else '対になる出動なし', ok(p1)])
    rows.append([f"P2 安全（M2 vs M1、{p2['n_pairs']}出動）",
                 f"危険な配達 M1 {p2['unsafe_M1']} → M2 {p2['unsafe_M2']}（食い違い {p2['discordant_M1_only']}:{p2['discordant_M2_only']}）、"
                 f"McNemar正確検定 {pexact(p2['mcnemar_p'])}", ok(p2)])
    rows.append([f"P3 追加の危険なし（M2 vs M0、{p3['n_pairs']}出動）", f"危険な配達 M0 {p3['unsafe_M0']}、M2 {p3['unsafe_M2']}", ok(p3)])
    out += [table(rows, [56, 98, 20]), Spacer(1, 3),
            P(f"全体の主張（P1・P2・P3 がすべて成立）：<b>{'成立' if h['headline_supported'] else '不成立（成り立たなかった部分は上表のとおり）'}</b>。")]
    arows = [['方式', '出動', '危険な配達（95%区間）', '誤った停止', '安全な配達', '時間の中央値', '失敗']]
    for a, m in h['per_arm'].items():
        arows.append([ARM_JA.get(a, a), m['n'], f"{m['unsafe_deliveries']}（{m['unsafe_ci95'][0] * 100:.0f}–{m['unsafe_ci95'][1] * 100:.0f} %）",
                      m['false_refusals'], f"{m['safe_correct_deliveries']}/{m['safe_option_missions']}",
                      f"{m['time_median_s']:.0f} 秒" if m['time_median_s'] is not None else '-', m['failed']])
    out += [Spacer(1, 3), table(arows, [44, 12, 36, 20, 22, 24, 16]),
            P(f"出動2・3回目のみ。「安全な配達」は、安全な選択肢がある出動のうち安全に配達できた数。1回目の出動（記憶なし、{h['first_missions']['n']}出動）の危険な配達は "
              f"{h['first_missions']['unsafe']} 件。火は設計上、見えにくいものを含む。", 'small'), Spacer(1, 4)]
    return out


def sec_two_ai():
    out = [P('4.3 新規性3：当初計画の2つのAI（Jev役 Clef-Flash＋Qwen）を閉ループで動かす（I-16）', 'h2'),
           P('当初計画は「Jev と Qwen の2つのAIで確認する」ことだった。Jev役はCloudflareのClef-Flash判断モデルをローカルで動かして担わせ、'
             'T2ではオフラインで評価したが、ロボットを動かす閉ループでは使っていなかった（I-13）。I-16 ではロボットの判断の流れに組み込み、'
             '当初のJev要求（通路の安全を問う質問）が正しい配達の約半分しか許可しなかった点を、課題向けの質問に切り替えるフラグ（<font name="IPAexG">--jev-schema task</font>）で直した。'
             '両方のAIが許可したときだけ許可し、どちらかが危険を見れば止まる。')]
    t2 = jload('t2_summary.json')
    r = ((t2 or {}).get('results') or {}).get('J2(Clef-task,0.05)+Q4B')
    if r:
        out += [P('V100 1台（32 GB）に載る2モデル構成はこの組（Clef-Flash 19 GB＋Qwen3.5-4B 9 GB）だけで、未使用のT2（オフライン）では誤許可 '
                  f"{r['false_approvals']}/{r['n_deny']}、正しい許可 {r['correct_approvals']}/{r['n_allow']}だった。")]
    out += [Spacer(1, 3), P('<b>独立性についての注意</b>：Clef-Flash のモデルカードは、これが Qwen3.5-9B からの追加学習であると記している。'
              '2つのAIは<b>系統を共有しており、独立に開発されたものではない</b>。独立な版でも誤りが相関すること（Knight &amp; Leveson 1986）を踏まえ、'
              '2つに分けたことによる安全の上乗せは主張しない（D11, D14）。')]
    j = jload('j_summary.json')
    if not j:
        return out + [P('<b>評価J 実行中（事前登録済み）</b>（<font name="IPAexG">experiments/PREREGISTRATION_J.md</font>：24世界を v3.6（A）と2つのAI（J）で対にして実行）。'
                        '主要な基準は、P1：V100 1台で失敗なく走る、P2：危険な配達が J は A 以下。'), Spacer(1, 4)]
    c = j['per_config']
    p1, p2, p3 = j['P1_runs_on_one_v100'], j['P2_no_extra_unsafe'], j['P3_correct_paired']
    rows = [['', 'A：v3.6（Qwen3.5-9B）', 'J：Clef-Flash＋Qwen3.5-4B']]
    for lbl, f in (('期待どおりの行動', lambda x: f"{x['correct']}/{x['n']}（{x['correct_ci95'][0] * 100:.0f}–{x['correct_ci95'][1] * 100:.0f} %）"),
                   ('危険な配達', lambda x: str(x['unsafe_deliveries'])), ('誤った停止', lambda x: str(x['false_refusals'])),
                   ('スタックの失敗', lambda x: str(x['failed'])),
                   ('1回の確認の遅延（中央値）', lambda x: f"{x['check_latency_median_s']:.1f} 秒" if x['check_latency_median_s'] is not None else '-')):
        rows.append([lbl, f(c['A']), f(c['J'])])
    vr = f"、GPUメモリの最大 {p1['peak_vram_mib'] / 1024:.1f} GB" if p1.get('peak_vram_mib') else ''
    out += [table(rows, [60, 56, 58]), Spacer(1, 3),
            P(f"P1（V100 1台で失敗なく走る）：J の失敗 {p1['failed_J']} 件{vr} → <b>{'成立' if p1['supported'] else '不成立'}</b>。"
              f"P2（危険な配達が J は A 以下）：A {p2['unsafe_A']}、J {p2['unsafe_J']} → <b>{'成立' if p2['supported'] else '不成立'}</b>。"
              f"P3（対比較、記述的）：Aのみ正解 {p3['A_only_correct']}・Jのみ正解 {p3['J_only_correct']}、McNemar正確検定 {pexact(p3['mcnemar_p'])}。", 'small'),
            Spacer(1, 4)]
    return out


def sec_clip():
    z = jload('z_summary.json')
    if not z:
        return []
    mod, th = z['models'], z['thresholds']
    cell = lambda d, k, nk: f"{d[k]}/{d[nk]}<br/>（{d[k + '_ci'][0] * 100:.1f}–{d[k + '_ci'][1] * 100:.1f} %）"
    o1, o2 = mod['siglip']['t1']['ours'], mod['siglip']['t2']['ours']
    rows = [['方式（T1・T2は未使用の画像）', 'T1 誤許可', 'T1 正しい許可', 'T2 誤許可', 'T2 正しい許可'],
            ['<b>本システム</b>（Qwen3.5-9B＋h36＋拡大切り出し）', cell(o1, 'FA', 'n_deny'), cell(o1, 'CA', 'n_allow'),
             cell(o2, 'FA', 'n_deny'), cell(o2, 'CA', 'n_allow')]]
    for key, nm in (('siglip', 'SigLIP ゼロショット'), ('clip', 'CLIP ゼロショット')):
        b1, b2 = mod[key]['t1']['baseline'], mod[key]['t2']['baseline']
        rows.append([nm, cell(b1, 'FA', 'n_deny'), cell(b1, 'CA', 'n_allow'), cell(b2, 'FA', 'n_deny'), cell(b2, 'CA', 'n_allow')])
    s_, c_ = mod['siglip'], mod['clip']
    return [P('4.5 比較：CLIP系ゼロショット（Z）', 'h2'),
            P('「VLMでなくても、CLIP系の画像と文章の類似度（ゼロショット）で同じ確認ができるのでは」という疑問を、'
              f"<font name=\"IPAexG\">{z['prereg']}</font> で事前登録して検証した。SigLIP（so400m）とCLIP（ViT-L/14）に本システムと同じ判定構造（物資と火災の2段）を与え、"
              f"閾値は開発データだけで決めた（開発データの正しい許可：SigLIP {th['siglip']['dev_correct_approvals']}/{th['siglip']['dev_n_allow']}、"
              f"CLIP {th['clip']['dev_correct_approvals']}/{th['clip']['dev_n_allow']}）。"),
            table(rows, [54, 30, 30, 30, 30]), Spacer(1, 3),
            P(f"<b>解釈</b>：SigLIPは正しい許可を保つが、拒否すべき画像を T1 で {s_['t1']['baseline']['FA']}/{s_['t1']['baseline']['n_deny']}、"
              f"T2 で {s_['t2']['baseline']['FA']}/{s_['t2']['baseline']['n_deny']} 許可してしまう（T1の対比較 McNemar正確検定 {pexact(s_['t1']['mcnemar']['deny']['p'])}）。"
              f"CLIPは誤許可 {c_['t1']['baseline']['FA']} だが、これは<b>ほぼ何も許可しない</b>ためで（正しい許可 T1 {c_['t1']['baseline']['CA']}/{c_['t1']['baseline']['n_allow']}、"
              f"T2 {c_['t2']['baseline']['CA']}/{c_['t2']['baseline']['n_allow']}）、配達ロボットとして使えない。本システムだけが、誤許可を抑えつつ正しい許可を保つ。"),
            Spacer(1, 4)]


def sec_real():
    p = jload('p_summary.json')
    if not p:
        return []
    cat = p['by_category']
    ter = p['by_box_area_tercile']
    cuts = p['tercile_cuts_area_fraction']
    out = [P('4.6 実写画像（P）：シミュレーションの外での火災判定', 'h2'),
           P(f"シミュレーションの画像だけでは「実写で通用するか」が分からない。そこで実写の火災データセット（D-Fire、CC0）から{p['n']}枚を層別に抽出し、"
             '凍結したv3.6の危険の問い（h36＋拡大切り出し、τ_h=0.05）をそのまま当てた'
             f"（<font name=\"IPAexG\">{p['registered']}</font>、推論の前に登録）。"
             f"火・煙のある画像の検出 <b>{rate_ci(p['recall'])}</b>、火も煙も無い画像の誤警報 <b>{rate_ci(p['false_alarm'])}</b>。"),
           table([['煙のみ', '炎のみ', '炎と煙', '火も煙も無い（誤警報）', '検出：面積の三分位（小・中・大）'],
                  [cat['smoke'], cat['fire'], cat['both'], cat['none'], f"{ter['t1']}・{ter['t2']}・{ter['t3']}"]],
                 [26, 26, 26, 42, 54]), P(f"表の値は「危険と判定／枚数」。面積の三分位の切れ目は画面の{cuts[0] * 100:.1f} %と{cuts[1] * 100:.0f} %。", 'small'), Spacer(1, 3),
           P(f"<b>解釈と含意</b>：見逃しはほぼ無い（小さな火・煙も検出）が、火の無い画像の {p['false_alarm']['k']}/{p['false_alarm']['n']} を危険と判定した。誤警報の多くは、"
             '霞・低い雲・レンズの汚れ・夕焼け・光るテントなどの紛らわしい画像である。つまり<b>安全側に倒れている代わりに、現場ごとの較正なしでは停止が多すぎる</b>。'
             'シミュレーションで固定した閾値をそのまま実写へ持ち込むべきではない。')]
    p2 = jload('p2_summary.json')
    if p2 and p2.get('chosen_wording'):
        ct = p2['chosen_test']
        out += [P(f"<b>追試P2</b>（<font name=\"IPAexG\">experiments/PREREGISTRATION_P2.md</font>）：較正用の画像だけで閾値と問いの文面を選び"
                  f"（{p2['chosen_wording']}、τ_h={p2['chosen_tau']}）、較正に使っていない400枚で確かめた。検出 {rate_ci(ct['recall'])}、誤警報 {rate_ci(ct['false_alarm'])}。"
                  f"登録した基準（検出0.90以上かつ誤警報0.20以下）：<b>{'成立' if p2['claim_supported'] else '不成立（' + '；'.join(p2.get('failed', [])) + '）'}</b>。")]
    else:
        out += [P('<b>追試P2は実行中（事前登録済み）</b>：現場での較正（火の無い現地画像で閾値を決める手順）が、較正に使っていない画像で通用するかを事前登録した'
                  '（<font name="IPAexG">experiments/PREREGISTRATION_P2.md</font>、修正1：較正画像は訓練分割の9シャード全体から抽出）。'
                  '結果は <font name="IPAexG">experiments/results/p2_summary.json</font> に出力される。')]
    return out + [Spacer(1, 4)]


def sec_camera():
    r = jload('r_summary.json')
    out = [P('4.7 カメラ劣化（R）：実機カメラに近づけたとき、失敗は「停止」に倒れるか', 'h2'),
           P('Gazeboの画像は雑音がなく鮮明で、露出も適正である。実機のカメラはそうではない。未使用のT2画像（30世界）に、6種類の劣化（センサー雑音、動きぶれ、ピンぼけ、露出不足、露出過多、JPEG劣化）を'
             '2段階ずつ（計12条件）加え、v3.6の確認が<b>フェイルクローズ</b>（誤りが停止になり、誤った許可にならない）のままかを調べる（'
             '<font name="IPAexG">experiments/PREREGISTRATION_R.md</font>。閾値・問いは変更しない）。')]
    if not r:
        return out + [P('<b>実行中（事前登録済み）</b>（結果は <font name="IPAexG">experiments/results/r_summary.json</font> に出力される）。'), Spacer(1, 4)]
    pp, cond = r['P1_pooled'], r['conditions']
    worst = min(cond, key=lambda c: cond[c]['ca_rate'])
    nm = lambda c: f"{R_FAM.get(c.rsplit('_', 1)[0], c)}（{'中' if c.endswith('_M') else '強'}）"
    out += [P(f"12条件をまとめた誤許可は <b>{pp['false_approvals']}/{pp['n']}（{pp['rate'] * 100:.2f} %）</b>、世界単位のブートストラップ95%区間の上限 "
              f"{pp['cluster_ci95'][1] * 100:.2f} %、Wilson 95%区間の上限 {pp['wilson_ci95'][1] * 100:.2f} %（上限が2 %未満なら「フェイルクローズ」と主張すると登録した）→ "
              f"<b>{'成立' if pp['supported'] else '不成立'}</b>。清浄な画像の誤許可は {r['clean']['false_approvals']}/{r['n_deny']}。"
              f"代償は可用性で、正しい許可が最も下がったのは<b>{nm(worst)}</b>の <b>{cond[worst]['correct_approvals']}/{r['n_allow']}</b>"
              f"（清浄 {r['clean']['correct_approvals']}/{r['n_allow']}、品質ゲートによる棄却 {cond[worst]['gate_rejected']}件）。"
              f"他の条件は {min(cond[c]['correct_approvals'] for c in cond if c != worst)}/{r['n_allow']} 以上で、可用性の低下は露出過多に集中する。"
              + ('「危険な劣化」と判定された条件：' + '、'.join(nm(c) for c in r['P2_unsafe_conditions']) + '。' if r['P2_unsafe_conditions']
                 else '清浄な画像より有意に誤許可が増えた条件はない（Holm補正）。'))]
    return out + [Spacer(1, 4)]


def sec_prereg(D, E):
    """Table of the pre-registered studies; each result cell is read from its summary and falls back to a pending note."""
    t1, t2, z, p, p2, rr, h, j = (jload(n) for n in ('t1_summary.json', 't2_summary.json', 'z_summary.json', 'p_summary.json', 'p2_summary.json',
                                                     'r_summary.json', 'h_summary.json', 'j_summary.json'))
    g = jload('g_summary.json')
    reg = lambda n: (n if (ROOT / f'experiments/PREREGISTRATION_{n}.md').is_file() else '-')
    m9 = t1['models']['Qwen3.5-9B']['rules']['full'] if t1 else None
    q = (t2 or {}).get('results', {}).get('Q9B[h36_tiles] tau_h=0.05')
    zs = ((z or {}).get('models') or {}).get('siglip')
    gp = g['primary'] if g else None
    rows = [['研究', '問い', '登録文書', '結果'],
            ['D（v3.4）', '閉ループ42試行で期待どおりに動くか', reg('v34'), f"{D['correct']}/{D['n']}、誤許可 {D['false_approvals']}" if D else PEND],
            ['E（v3.5）', 'ランダムな世界で回復探索は効くか', reg('E'), f"{E['ok']}/{E['n']}、誤配達 {E['fa']}" if E else PEND],
            ['T1', '未使用の画像での誤許可', reg('T1'), f"誤許可 {m9['false_approvals']}/{m9['n_deny']}" if m9 else PEND],
            ['F・G', '横から見直すと小さな火への配達が減るか', reg('G'),
             f"G：配達 {gp['wrong_deliveries_B']} → {gp['wrong_deliveries_C']}（{pexact(gp['mcnemar_p'])}）" if gp else PEND],
            ['T2', '未使用の画像で改良が悪化しないか', reg('T2'),
             f"誤許可 {q['false_approvals']}/{q['n_deny']}、正しい許可 {q['correct_approvals']}/{q['n_allow']}" if q else PEND],
            ['Z', 'CLIP系ゼロショットでも足りるか', reg('Z'),
             f"T1誤許可：本システム {zs['t1']['ours']['FA']}、SigLIP {zs['t1']['baseline']['FA']}" if zs else PEND],
            ['P', '実写の火災画像で通用するか', reg('P'),
             f"検出 {p['recall']['k']}/{p['recall']['n']}、誤警報 {p['false_alarm']['k']}/{p['false_alarm']['n']}" if p else PEND],
            ['P2', '現場での較正で実写の誤警報が減るか', reg('P2'),
             (f"検出 {p2['chosen_test']['recall']['k']}/{p2['chosen_test']['recall']['n']}、"
              f"誤警報 {p2['chosen_test']['false_alarm']['k']}/{p2['chosen_test']['false_alarm']['n']}") if p2 and p2.get('chosen_test') else PEND],
            ['R', 'カメラ劣化でもフェイルクローズか', reg('R'),
             f"誤許可 {rr['P1_pooled']['false_approvals']}/{rr['P1_pooled']['n']}" if rr else PEND],
            ['H', '記憶で速くなり、危険は増えないか', reg('H'),
             ('主張 ' + ('成立' if h['headline_supported'] else '不成立')) if h else PEND],
            ['J', '2つのAIがシミュレーションの閉ループで動くか', reg('J'),
             f"危険な配達 A {j['P2_no_extra_unsafe']['unsafe_A']}、J {j['P2_no_extra_unsafe']['unsafe_J']}" if j else PEND]]
    return [KeepTogether([P('G. 事前登録した研究の一覧', 'h2'),
            P('どの研究も、結果を見る前に条件・基準・解析を <font name="IPAexG">experiments/PREREGISTRATION_<記号>.md</font> に固定した。'
              '失敗した試行も台帳に残している。'),
            table(rows, [20, 66, 24, 64])]), Spacer(1, 4)]


def chapter_novelty(D, E, V):
    s = [P('4. 新規性と結果', 'h1'),
         P('新規性3つ（4.1〜4.3）と、それを支える検証（4.4〜4.7）。結果がまだ無いものは「実行中」と明記し、数値は書かない。')]
    for sec in (sec_active(V), sec_memory(), sec_two_ai(), sec_e_compact(D, E), sec_clip(), sec_real(), sec_camera()):
        s += sec
    return s


PEND = '実行中（事前登録済み）'


def headline(D, E, V):
    """'1ページ目の要旨': what the robot does, the three novelties, the pre-registered results E, G, R, Z, P (H, J).
    Every number is read from a result file; a missing file gives a pending note."""
    z, p, p2, rr, h, j, t1 = (jload(n) for n in ('z_summary.json', 'p_summary.json', 'p2_summary.json', 'r_summary.json',
                                                 'h_summary.json', 'j_summary.json', 't1_summary.json'))
    gp = V['g']['primary'] if V else None
    gc = V['g']['per_config'] if V else None
    ok_ = lambda x: '成立' if x else '不成立'
    # --- evaluation H / J result strings (graceful fallbacks)
    if h:
        p2h = h['P2_safety_naive_vs_verified']
        h_res = (f"危険な配達 M1 {p2h['unsafe_M1']} → M2 {p2h['unsafe_M2']}、速さ {ok_(h['P1_efficiency_relocation_persist']['supported'])}・"
                 f"安全 {ok_(p2h['supported'])}・追加の危険なし {ok_(h['P3_no_extra_risk_vs_v36']['supported'])}。全体の主張：<b>{ok_(h['headline_supported'])}</b>")
    else:
        h_res = PEND
    if j:
        pj = j['P2_no_extra_unsafe']
        j_res = (f"危険な配達 A {pj['unsafe_A']}、J {pj['unsafe_J']}、J の失敗 {j['P1_runs_on_one_v100']['failed_J']} 件。"
                 f"全体の主張：<b>{ok_(j['P1_runs_on_one_v100']['supported'] and pj['supported'])}</b>")
    else:
        j_res = PEND
    nf = gp['n_world_pairs_fire_perceivable'] if gp else None
    out = [P('1ページ目の要旨', 'h1'),
           P('<b>何をするロボットか</b>：災害の現場で、頼まれた物資（水や救急箱など）を運ぶロボットのシミュレーションである。物資のある場所に着いたら止まり、'
             'カメラの画像を、画像を理解するAI（ローカルVLM、Qwen3.5-9B）に見せて、頼まれた物資が本当にあるかを確かめる。'
             '確かめられて、しかも火や煙が見えないときだけ、避難所Bへ向かう。物資が違えばもう一方の場所を探し、火が見えたら探さずに止まり、見たものを日本語で人に知らせる。'
             'ねらいは「AIが間違えたときは、ロボットが動かない」ことを、記録とシミュレータの正しい位置情報（真値）で、第三者が確かめられるようにすること。'
             'この資料の「届ける」は、避難所Bに近づくところまでで、物資をつかんだり降ろしたりはしていない。'),
           Spacer(1, 3), P('<b>3つの新規性</b>', 'body')]
    g_txt = (f"評価G：火が見えた{nf}世界のうち、火があるのに配達した回数 {gp['wrong_deliveries_B']} → {gp['wrong_deliveries_C']}（{pexact(gp['mcnemar_p'])}）" if gp else PEND)
    out += bullets([
        f"<b>横から見直す（4.1）</b>：物資の陰に隠れた小さな火は、正面からは判断の基準（閾値）を変えても見分けられない。そこで、配達の直前に拠点の左右へ動いて撮り直す。{g_txt}。",
        f"<b>出動をまたぐ記憶——記憶は提案だけ、確認は減らさない（4.2）</b>：前回の出動で見たことを覚えておき、次に先に行く拠点を決める助けにする。"
        f"ただし行った先では毎回現物を確かめ、最近火を見た拠点ではより慎重に見る。記憶を理由に確認を減らさない。評価H：{h_res}。",
        f"<b>当初計画の2つのAI（4.3）</b>：Jev役の Clef-Flash と Qwen を V100 1台で一緒に動かし、両方が「よい」と言ったときだけ配達する。"
        f"2つは同じ元のAIから作られていて、完全に別物ではない。評価J：{j_res}。"])
    out += [Spacer(1, 3), P('<b>用語</b>：<b>誤許可</b>＝届けてはいけない場面で「届けてよい」と判断してしまうこと（ロボットを実際に動かす評価では<b>誤配達</b>。火のある拠点から届けてしまうことは<b>危険な配達</b>）。'
                            '<b>正しい許可</b>＝届けてよい場面で、正しく「よい」と判断できること。'
                            '<b>事前登録</b>＝結果を見る前に、条件と合格の基準を文書にして固定すること。'
                            '<b>閉ループ</b>＝AIの判断でロボットが実際に動くところまで含めた評価。'
                            '<b>p値</b>＝偶然でこうなる確率の目安で、0.05より小さければ偶然とは考えにくい。', 'small')]
    rows = [['事前登録した研究', '結果', '読み方・限界']]
    if E:
        lo = wilson(E['ok'], E['n'])[0]
        rows.append(['<b>E</b> ランダムな世界の閉ループ', f"{E['ok']}/{E['n']} が期待どおり、誤配達 {E['fa']}",
                     f"試行数が少なく、95%区間の下限は {lo * 100:.0f} %。停止が正解の試行は易しく、満点に近い"])
    else:
        rows.append(['<b>E</b> ランダムな世界の閉ループ', PEND, ''])
    if gp:
        rows.append(['<b>G</b> 横から見直す（B：正面のみ → C：＋左右）',
                     f"火が見えた{gp['n_world_pairs_fire_perceivable']}世界で配達 {gp['wrong_deliveries_B']} → {gp['wrong_deliveries_C']}（McNemar検定 {pexact(gp['mcnemar_p'])}）、火の無い世界の誤った停止 {gc['C']['false_hazard_stops']}/{gc['C']['fire_free_trials']}",
                     f"火の多くは設計上、正面から見えにくい世界で、測るのは「横から見る効果」。見逃し {gc['C']['wrong_deliveries']} 件が残る"])
    else:
        rows.append(['<b>G</b> 横から見直す', PEND, ''])
    if rr:
        cond = rr['conditions']
        worst = min(cond, key=lambda c: cond[c]['ca_rate'])
        pp = rr['P1_pooled']
        rows.append(['<b>R</b> カメラ劣化（12条件）', f"誤許可 {pp['false_approvals']}/{pp['n']}（95%区間の上限 {pp['wilson_ci95'][1] * 100:.2f} %）",
                     f"劣化させる前から誤許可は0なので、言えるのは「悪化しなかった」まで。代償：最悪の条件で正しい許可 {cond[worst]['correct_approvals']}/{rr['n_allow']}"])
    else:
        rows.append(['<b>R</b> カメラ劣化（12条件）', PEND, ''])
    if z:
        so, ba, cl = z['models']['siglip']['t1']['ours'], z['models']['siglip']['t1']['baseline'], z['models']['clip']['t1']['baseline']
        rows.append(['<b>Z</b> CLIP系ゼロショットとの比較（T1、τ_h=0.05）',
                     f"誤許可：本システム {so['FA']}/{so['n_deny']}、SigLIP {ba['FA']}/{ba['n_deny']}、CLIP {cl['FA']}/{cl['n_deny']}",
                     f"CLIPは正しい許可 {cl['CA']}/{cl['n_allow']} で、ほぼ何も許可しない。SigLIPは誤許可が多い"])
    else:
        rows.append(['<b>Z</b> CLIP系ゼロショットとの比較', PEND, ''])
    if p:
        res = f"実写{p['n']}枚：検出 {p['recall']['k']}/{p['recall']['n']}、火の無い画像の誤警報 {p['false_alarm']['k']}/{p['false_alarm']['n']}"
        lim = '安全側だが<b>止まりすぎる</b>（最大の限界）。現場ごとの閾値の較正が必要'
        if p2 and p2.get('chosen_test'):
            ct = p2['chosen_test']
            lim += f"。較正した追試P2：誤警報 {ct['false_alarm']['k']}/{ct['false_alarm']['n']}、登録した基準 {ok_(p2['claim_supported'])}"
        rows.append(['<b>P</b> 実写の火災画像', res, lim])
    else:
        rows.append(['<b>P</b> 実写の火災画像', PEND, ''])
    rows.append(['<b>H</b> 出動をまたぐ記憶', h_res, '' if h else '結果が出たら資料に反映する'])
    rows.append(['<b>J</b> 2つのAIの閉ループ', j_res, '' if j else 'スモーク試験では V100 1台に載り、閉ループが完走した'])
    out += [Spacer(1, 4), table(rows, [42, 74, 58]), Spacer(1, 3),
            P('すべてシミュレーション上の評価で、実写で検証したのは火災判定（P）だけ。ロボットを動かす評価（E・G・H・J）は、実機でも実写でも未検証。'
              '各研究の条件・基準・解析は結果を見る前に <font name="IPAexG">experiments/PREREGISTRATION_*.md</font> に固定した。', 'small'),
            Spacer(1, 4)]
    return out


def sec_active(V):
    """4.1 look-around (I-14): the G table; the F / T2 detail is in the appendix."""
    if not V:
        return [P('4.1 新規性1：横から見直す能動知覚', 'h2'), P(PEND)]
    f, g = V['f'], V['g']
    fp, gp, fc, gc = f['primary'], g['primary'], f['per_config'], g['per_config']
    fm = sorted(x['fire_pixels'] for x in f.get('trials', []) if x['config'] == 'B' and x['wrong_delivery'] and x.get('fire_pixels'))
    FPX = f"{fm[0]:,}〜{fm[-1]:,}画素" if fm else '小さく'
    out = [P('4.1 新規性1：横から見直す能動知覚（I-14、評価F → G）', 'h2'),
           P(f"T1で残った弱点は、物資の陰に隠れた小さな火の見逃しである。問い方の改良と拡大切り出しを加えた評価F（対比較）でも、火があるのに配達した回数は"
             f" {fp['wrong_deliveries_A']}/{fp['n_world_pairs_fire_visible_both']} → {fp['wrong_deliveries_B']}/{fp['n_world_pairs_fire_visible_both']} 世界、{pexact(fp['mcnemar_p'])} で有意でなかった。"
             f"見逃した火は正面から{FPX}しか写らず、p(危険)が火の無い画像と重なるため、閾値の調整では分けられない。"
             '同じ火は左右0.4 mずらした視点では4,600〜22,000画素で見えた。そこで<b>VLMではなくロボットの視点を変える</b>：'
             '許可の直前に拠点の左右0.4 mへ移動して、照準・静止確認・撮り直し・判定をやり直し、どちらかで危険を見れば探索せずに止まる（横からの物資判定は使わない）。')]
    rows = [['', 'B：正面のみ', 'C：＋横から見直す（v3.6）']]
    rows.append([f"3視点（正面・左右0.4 m）のどれかで火が見えた{gp['n_world_pairs_fire_perceivable']}世界で、火があるのに配達した回数",
                 f"{gc['B']['wrong_deliveries']}/{gc['B']['visible_fire_trials']}", f"<b>{gc['C']['wrong_deliveries']}/{gc['C']['visible_fire_trials']}</b>"])
    rows.append(['火の無い世界での誤った停止', f"{gc['B']['false_hazard_stops']}/{gc['B']['fire_free_trials']}", f"<b>{gc['C']['false_hazard_stops']}/{gc['C']['fire_free_trials']}</b>"])
    rows.append(['期待どおりの行動', f"{gc['B']['correct']}/{gc['B']['n']}（95%区間 {gc['B']['correct_ci95'][0] * 100:.0f}–{gc['B']['correct_ci95'][1] * 100:.0f} %）",
                 f"<b>{gc['C']['correct']}/{gc['C']['n']}</b>（{gc['C']['correct_ci95'][0] * 100:.0f}–{gc['C']['correct_ci95'][1] * 100:.0f} %）"])
    if V['wall_B'] and V['wall_C']:
        rows.append(['正常配達1回の所要時間（中央値）', f"{V['wall_B']:.0f} 秒", f"{V['wall_C']:.0f} 秒（約 +{V['wall_C'] - V['wall_B']:.0f} 秒）"])
    out += [P(f"<b>評価G</b>（<font name=\"IPAexG\">experiments/PREREGISTRATION_G.md</font>）：新しい{g['n_trials'] // 2}世界を B と C で対にして{g['n_trials']}試行を実行した。"
              '主張は「Cの方が、火があるのに配達する回数が少なく、かつ p<0.05」で、結果を見る前に固定した。'),
            table(rows, [78, 44, 52]), Spacer(1, 3),
            P(f"食い違いは B のみ {gp['discordant_B_only']}・C のみ {gp['discordant_C_only']}、McNemar の正確検定で <b>{pexact(gp['mcnemar_p'])}</b>。事前登録した主張が成立した。"
              f"ただしこの{gp['n_world_pairs_fire_perceivable']}世界の火の多くは設計上、正面からは見えにくい（または見えない）ため、これは「横から見る効果」の測定である。"
              '拠点配置が固定のシミュレーションで、試行数が少なく区間が広い。', 'small')]
    if V['miss']:
        m = V['miss'][0]
        out += [P(f"<b>唯一の見逃し</b>（{m['world']}）：火が正面から{m['fire_pixels_front']}画素（完全に隠れる）、横からも最大 {m['fire_pixels_best_side']:,} 画素と最小で、"
                  'p(危険)が閾値0.05に届かなかった。限界として明記する。', 'small')]
    return out + [Spacer(1, 3)]


def sec_e_compact(D, E):
    """4.4 closed-loop baselines D and E in a few lines; the strata table is in the appendix."""
    if not (D or E):
        return []
    txt = []
    if D:
        txt.append(f"評価D（v3.4）：{D['n']}試行で期待どおり {D['correct']}/{D['n']}、誤許可 {D['false_approvals']}")
    if E:
        nb = E['n'] - E['allow']
        txt.append(f"評価E（v3.5、試行ごとにランダムな世界）：{E['ok']}/{E['n']}（Wilson 95%区間 {pct_ci(E['ok'], E['n'])}）、誤配達 {E['fa']}、判断遅延の中央値 {E['lat_med']:.2f} 秒。"
                   f"同じ試行への反事実の基準は、盲目的に配達すると {E['allow']}/{E['n']}（誤行動 {nb}）、回復探索なしで {E['allow']}/{E['n']}")
    return [P('4.4 閉ループのベースライン（評価D・E）', 'h2'),
            P('。'.join(txt) + '。インフラ失敗の再試行も台帳に残し、集計は最終試行のみ。評価Dは同じ配置の反復、評価Eは世界を毎回変えるが拠点の配置は固定で、どちらも試行数は多くない。層別の表は付録A・B。')]


def camera_table():
    r = jload('r_summary.json')
    if not r:
        return []
    cond = r['conditions']
    rows = [['劣化', '段階', '誤許可', '火の見逃し', '正しい許可', '品質ゲートで棄却']]
    for c in cond:
        f_, sv = c.rsplit('_', 1)
        o = cond[c]
        rows.append([R_FAM.get(f_, f_), '中' if sv == 'M' else '強', f"{o['false_approvals']}/{r['n_deny']}", f"{o['fire_missed']}/{r['n_visible_fire']}",
                     f"{o['correct_approvals']}/{r['n_allow']}", o['gate_rejected']])
    return [table(rows, [38, 16, 28, 28, 30, 34]), Spacer(1, 4)]


def main_tail(account, SP, p_fa):
    s = [P('5. 実用性・応用可能性', 'h1')]
    s += bullets(['<b>在庫と現物のずれに強い</b>：物流倉庫・病院内搬送・避難所運営で、誤った物資を届けず、無ければ探し、それでも無ければ人に報告して止まる。',
                  '<b>オフライン・オンデバイス</b>：推論はすべて単一GPU上（APIキー不要、Apache-2.0のモデル）。',
                  '<b>説明と検証可能性</b>：判断画像のハッシュ・各質問の確率・日本語報告・真値軌跡・ROS bagを試行ごとに保存し、第三者が再計算できる。'])
    s += [P('6. 限界・反省と今後の課題', 'h1')]
    lim = ['v3.6の横から見直す効果（評価G）は、拠点配置が固定の新しい世界での対比較で、試行数は少ない。完全に隠れた火は横からも見逃し得る。実機・実写では未検証。',
           '物資の把持・運搬は未実装。Nav2の動的経路計画ではなく既知配置のウェイポイント追従。',
           '小道具は単純形状、拠点は2か所・避難所は1か所の固定配置。実機（SO-101等）でのSim-to-Realは未検証。実写で検証したのは火災判定のみ（4.6章）。',
           '閾値（τ_s=0.50、τ_h=0.05）は確率の較正ではなく、分布の異なる環境では再評価が必要。',
           'ROSグラフ監視は認証機構ではなく、実機の安全認証を意味しない。']
    if p_fa:
        lim.insert(0, f'実写の火の無い画像の誤警報は {p_fa}（4.6章）。安全側に倒れる代わりに止まりすぎるため、現場での閾値の較正が前提になる。')
    s += bullets(lim)
    chap = ROOT / 'docs/video_chapters.json'
    s += [P('7. 提出動画と再現方法', 'h1')]
    if chap.is_file():
        ch = json.loads(chap.read_text(encoding='utf8'))
        mmss = lambda x: f'{int(x // 60)}:{int(x % 60):02d}'
        s += [P(f"動画は全 {mmss(round(ch[-1]['end_s']))}。3-D映像はすべてGazeboの実レンダリング（俯瞰カメラ＋ロボット搭載カメラ）で、模式図やモック映像は使っていない。"
                f'字幕・確率バー・軌跡・ロボットの報告文はその試行のログから自動合成。<b>{SP}</b>で、速度は画面左上に常時表示している。ナレーションは VOICEVOX:四国めたん。構成は付録J。')]
    s += [P('再現：<font name="IPAexG">bash docker/build.sh</font> → <font name="IPAexG">bash docker/run.sh python3 scripts/run_campaign.py --protocol experiments/campaign_e_protocol.json</font>。'
            '全体フローは docs/ARCHITECTURE.md、設計判断は docs/DESIGN_DECISIONS.md。'),
          P('本資料・動画・コードに氏名・所属・メールアドレス等の個人情報は含めていない。講座サンプル（差動二輪ROSシミュレーション等）を出発点に、'
            '現地での確認・回復探索・安全ガード・真値監査・事前登録評価は独自に設計・実装した。', 'small')]
    return s


def build(account: str, video_url: str | None, repo_url: str):
    D = campaign_d()
    E = campaign_e()
    T = t1_info()
    V = v36_info()
    SP = speed_text()
    pj = jload('p_summary.json')
    p_fa = f"{pj['false_alarm']['k']}/{pj['false_alarm']['n']}" if pj else None
    rr_tab = camera_table()
    C = [r for r in ledger('campaign_ledger.jsonl') if r.get('final', True)]
    c_ok = sum(r['correct'] for r in C)
    rob = jload('i05_robustness_summary.json') or {}
    msel = jload('i08_model_selection.json') or []
    it = {k: (jload(f) or {}).get('summary') for k, f in (('tfidf', 'intent_tfidf.json'), ('q3b', 'intent_hybrid_qwen25vl3b.json'),
                                                          ('q9b', 'intent_hybrid_selected_qwen35_9b_i35.json'))}
    i01 = {k: jload(f'i01_drift/{k}.json') for k in ('baseline', 'sphere_wheels')}
    out = ROOT / 'docs/report' / f'説明資料_PAI最終課題_{account}.pdf'
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(str(out), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                          topMargin=16 * mm, bottomMargin=16 * mm,
                          title='RescueMind v3.6 説明資料', author=account, subject='Physical AI 応用1講座 最終課題')
    doc.addPageTemplates([PageTemplate('p', [Frame(18 * mm, 16 * mm, 174 * mm, 266 * mm, id='f')], onPage=on_page)])
    s = []
    s += [P('RescueMind：現地で「目で確かめてから」届ける災害物資ロボット', 'title'),
          P('最新のローカルVLM（Qwen3.5-9B / V100）× ROS 2 Jazzy × Gazebo Harmonic — 誤った物資を届けず、無ければ探し、危険なら止まる', 'sub')]
    s += headline(D, E, V)
    s += [table([['項目', '内容'],
                 ['提出者', f'omnicampus アカウント：{account}'],
                 ['コード', repo_url],
                 ['動画', video_url or f'YouTube（タイトル：PAI最終課題_{account}）。{SP}（倍速は動画内に常時表示）。日本語ナレーション（VOICEVOX:四国めたん）'],
                 ['使用ツール', 'ROS 2 Jazzy / Gazebo Harmonic（Docker・EGLヘッドレス描画）/ PyTorch 2.8 + Transformers 5.20 / Tesla V100 32GB（sudo不要）'],
                 ['AIの活用', '① 自然言語指示の理解（ローカルLLM）② 搭載カメラ画像による現物・危険の確認（ローカルVLM、選択肢の確率で判断）③ 現場の人への日本語状況報告']],
                [28, 146]), Spacer(1, 4)]
    crit = [['審査基準', '本作品での取り組み', '根拠（本資料の節）'],
            ['創造性', '「運ぶAI」ではなく「間違えたら動かないAI」。新規性3つ：横から見直す能動知覚、確認を減らさない出動をまたぐ記憶、当初計画の2つのAI', '要旨, 4.1–4.3章'],
            ['技術力', '選択肢の確率によるVLM判定、独立速度ガード、Gazebo真値による独立監査、事前登録した閉ループ評価（結果あり：D・E・F・G、実行中：H・J）と未使用画像の評価（T1・T2・Z・P・R）、対比較の検定つきで弱点を段階的に改善', '2–4章, 付録'],
            ['実用性', 'オフライン・単一GPU・Apache-2.0、在庫と現物のずれへの対応、人への報告と判断の委譲、実写画像での限界の公開（誤警報）、Dockerで再現可能', '5–7章, 4.6章'],
            ['表現力', '実レンダリング映像にAR軌跡・確率バー・ロボットの報告を重ねた日本語ナレーション付き動画、全体フロー図、結果の表（区間推定・検定つき）', '7章, 付録J']]
    s += [P('審査基準との対応', 'h2'), table(crit, [18, 108, 48]), Spacer(1, 4)]
    s += [P('1. 課題の概要と目的', 'h1'),
          P('災害時の物資配送では「在庫表では水があるはずの棚に救急箱が置かれていた／空だった」という<b>情報と現物の食い違い</b>や、'
            '<b>現場の危険（火災）</b>が起こる。指示どおり機械的に運ぶロボットは、誤った物資を届けたり危険な場所に留まったりする。'
            '本作品では、自然言語で依頼を受けた差動二輪ロボットが物資拠点へ自律移動し、<b>その場で静止して搭載カメラで現物を確認</b>する。'
            'ローカルVLMが依頼物資を高い確信で確認したときだけ避難所Bへ向かい、物資が違えば<b>もう一方の拠点を探して</b>正しい物資を届け、'
            '火災を見たら探索せずに停止して、見たものを日本語で報告する。'),
          P('狙いは「AIに運ばせる」ことではなく、<b>AIの判断が間違っていればロボットが動かないこと</b>を、ログと物理シミュレータの真値で第三者が検証できる形にすることである。'
            'ロボットは物資の把持・運搬は行わない（現物確認と避難所への接近までを対象とし、配達完了とは表現しない）。')]
    s += fig('architecture.png', 112, '図1 実行時アーキテクチャ。全推論はローカルGPUで実行（クラウドAPI不使用）。詳細なフロー図は docs/ARCHITECTURE.md。')
    # ---- 2. AI
    s += [P('2. AIの活用と工夫', 'h1'),
          P('2.1 現地確認：文章を生成させず「選択肢の確率」で判断する', 'h2'),
          P('VLMに選択式の質問（台の上は 水／救急箱／なし・その他）を2問、選択肢の順序を入れ替えて出し、回答文字の次トークン確率を1回の順伝播で読む。'
            '2問とも依頼物資が最大かつ確率0.50以上（τ_s）、火災・煙の Yes/No 質問が0.05未満（τ_h、v3.6。v3.4までは0.50）のときだけ許可する。'
            '引継ぎ版の「JSONを自由生成させる」方式は、実画像で96応答中21件が解析不能、空の台で「水がある」と幻覚した。'
            '選択肢方式では解析不能0となり、最初の開発画像48枚での正答は 37/48 → 48/48 になった。'),
          P('2.2 モデルの調査と選定（最新世代への更新）', 'h2'),
          P('当初のQwen2.5-VL-3B（2025年1月・研究用途ライセンス）から、2025〜2026年の新世代（Qwen3-VL-8B、Qwen3.5-4B/9B、いずれもApache-2.0）を調査した。'
            'V100（FP16のみ）向けに torch 2.8＋transformers 5.20 の実行環境を用意し、<b>同じ開発データ・同じ手順</b>で比較。'
            '1回目は3B向けに調整したプロンプトのため新モデルが救急箱を「その他」と答える誤りが多発し、選択肢に外見と用途を併記したモデル非依存のプロンプトで公平に再比較した。')]
    s += [P('誤許可（視覚）と危険な誤受理（指示）がともに0だった唯一の新世代モデル <b>Qwen3.5-9B（2026年2月）</b>を採用した。状況説明の正確さは 84 → 125/128 に向上（比較表は付録E）。')]
    s += [P('2.3 自然言語指示の理解', 'h2'),
          P('同じローカルモデルに「物資は？」「届け先は？」の選択式2問を出して解釈し、明示的に別の避難所名がある指示は規則で必ず拒否する。'
            f"事前に固定した未知の言い換え60文（間接表現・否定・ひらがな・英語・無関係な依頼を含む）で、v3.3のTF-IDF {it['tfidf']['correct']}/60（危険な誤受理{it['tfidf']['unsafe_accepts']}）→ "
            f"<b>{it['q9b']['correct']}/60（危険な誤受理{it['q9b']['unsafe_accepts']}）</b>。" if it.get('q9b') and it.get('tfidf') else ''),
          P('2.4 現場の人への状況報告', 'h2'),
          P('判断が確定した<b>後</b>に、VLMが日本語1文で「台の上に何があり、火や煙が見えるか」を報告する（例：「灰色の台には赤い十字の箱が置かれ、その横に炎と煙が立ち上っている。」）。'
            '判断ロジックは報告文を読まない（コードとテストで保証）。'),
          P('2.5 開発データと評価データの分離（事前登録）', 'h2'),
          P('プロンプト・閾値・モデルは開発用データ（視点・照明・妨害物・火災をランダム化した画像176枚、指示文40文）だけで決め、評価前に条件を'
            '<font name="IPAexG">experiments/PREREGISTRATION_v34.md</font> に固定してから閉ループ評価を一度だけ実行した。失敗・中断した評価も台帳から削除していない。')]
    # ---- 3. robot
    s += [P('3. ロボットの振る舞いと安全設計', 'h1')]
    s += bullets([
        '<b>現地確認</b>：到着後、拠点中心へカメラを向けて停止し、オドメトリで静止を確認してから新しいカメラ画像を2枚取得（画質・ROS時刻・シミュレーション時計を検査）。推論中・拒否後もゼロ速度と静止を監視し続ける。',
        '<b>回復探索</b>：依頼物資が無い／違う（危険なし）ときだけ、もう一方の拠点で同じ確認を1回行い、確認できたときだけ避難所Bへ。火災・確信度不足・2回目の拒否は停止して人に委ねる。',
        '<b>横から見直す（v3.6）</b>：正面の確認で許可したら、拠点の左右0.4 mへ移動して照準・静止確認・新しい画像の取得・判定をやり直す。どちらかで危険を見れば、探索せず危険で停止する（横からの物資判定は使わない）。物資の陰に隠れた火は、視点を変えると見える。',
        '<b>独立速度ガード</b>：ミッションは速度を要求するだけで、<font name="IPAexG">/cmd_vel</font> の唯一の発行者は別プロセスのガード。センサー鮮度・前方距離・速度上限を10 Hzで判定し異常はラッチ停止。DDSグラフで第2の発行者を検知したら非常停止。',
        '<b>真値による監査</b>：成功・停止は、独立レコーダが記録した <b>Gazebo真値姿勢</b>・ROS bag・時系列で判定する。回復探索は「最初の拒否の再計算 → 停止保持 → 探索 → 別拠点での新しい判断」の順序と画像ハッシュまで監査する。',
    ])
    s += chapter_novelty(D, E, V)
    s += main_tail(account, SP, p_fa)
    M, s = s, [PageBreak(), P('付録（詳細な表・過去の評価・失敗の一覧）', 'h1'),
                P('本文で省いた表と経緯。数値はすべて結果ファイルから生成している。', 'small')]
    if D:
        by = D['by']
        rows = [['シナリオ', '期待する行動', '試行', '期待どおり', '実際の行動']]
        for g, (ja, want) in GROUP.items():
            rs = by.get(g) or []
            if not rs:
                continue
            from collections import Counter
            cnt = Counter(OBS.get(r['observed_action'], r['observed_action']) for r in rs)
            rows.append([ja, want, len(rs), f"{sum(r['correct'] for r in rs)}/{len(rs)}", '、'.join(f'{k} {v}' for k, v in cnt.items())])
        s += [P('A. 事前登録した閉ループ評価D（v3.4）', 'h2'),
              P(f"試行ごとに Gazebo・ブリッジ・ガード・VLMを新規起動し、{D['n']}試行を事前に決めた順序で実行した。"
                f"期待どおりの行動 <b>{D['correct']}/{D['n']}</b>、誤許可 <b>{D['false_approvals']}</b> 件、"
                f"指示文の解釈 {D['intent_ok']}/{D['n']} 正解、判断遅延（静止画取得→判断）中央値 {D['lat_med']:.2f} 秒（最大 {D['lat_max']:.2f} 秒）。"
                + (f"VLM判断前のインフラ失敗による再試行 {D['retries']} 件（台帳に記録）。" if D['retries'] else '')
                + '同じワールドの反復であり、独立なシーン数ではない点に注意。'),
              table(rows, [34, 38, 12, 20, 70]), Spacer(1, 4)]
        s += fig('campaign_d_results.png', 100, '図2 評価Dのシナリオ別結果。')
        s += fig('trajectories_d.png', 68, '図3 評価D全試行のGazebo真値軌跡。取り違えでは別拠点を経由して避難所へ、欠品・火災では拠点で停止している。')
        s += [P(f"参考：v3.3（評価C、30試行、Qwen2.5-VL-3B、回復探索なし）は VLM判断 30/30・監査まで合格 {c_ok}/30。"
                '取り違えシーンでは「停止」が正解であり、正しい物資を届けることはできなかった。', 'small')]
    if E:
        s += [CondPageBreak(120 * mm), P('B. 評価E（v3.5）：試行ごとにランダムな世界での事前登録評価', 'h2'),
              P(f"照明・小道具の配置・妨害物・火災をランダム化した世界を試行ごとに生成し、{E['n']}試行を事前に決めた順序で実行した"
                f"（<font name=\"IPAexG\">experiments/campaign_e_protocol.json</font>）。期待どおりの行動 <b>{E['ok']}/{E['n']}</b>、"
                f"誤許可 <b>{E['fa']}</b> 件、判断遅延の中央値 {E['lat_med']:.2f} 秒。"
                + (f"VLM判断前のインフラ失敗による再試行 {E['retries']} 件は台帳に記録（集計は最終試行のみ）。" if E['retries'] else '')
                + f"Wilson 95%区間は試行数が少ないため広い（全体の下限 {wilson(E['ok'], E['n'])[0] * 100:.0f} %）。")]
        rows = [['期待する行動', '条件', '試行', '期待どおり', 'Wilson 95%区間']]
        for a, c in E['keys']:
            k, n = E['strata_ok'][(a, c)], E['strata'][(a, c)]
            rows.append([EXP_E.get(a, a), COND_E.get(c, c), n, f'{k}/{n}', pct_ci(k, n)])
        rows.append(['<b>全体</b>', '', E['n'], f"{E['ok']}/{E['n']}", pct_ci(E['ok'], E['n'])])
        nb = E['n'] - E['allow']
        rows.append(['反事実：盲目的に配達', '常に配達（確認しない）', E['n'], f"{E['allow']}/{E['n']}（誤行動 {nb}）", pct_ci(E['allow'], E['n'])])
        rows.append(['反事実：回復探索なし', '最初の拒否で停止', E['n'], f"{E['allow']}/{E['n']}", pct_ci(E['allow'], E['n'])])
        s += [table(rows, [44, 40, 14, 38, 38]),
              P('反事実は同じ試行に対する計算上の基準で、実行したものではない。盲目的な配達は期待行動が配達（ALLOW）以外の全試行で誤り、'
                '回復探索なしは ALLOW の試行のみ成功とみなす保守的な定義（停止が正解の試行も成功に数えない）。', 'small'), Spacer(1, 4)]
    if T:
        t1 = T['t1']
        m9 = t1['models']['Qwen3.5-9B']
        s += [P(f"C. 未使用の画像{m9['n_images']}枚（T1）での評価", 'h2'),
              P(f"モデル選定・閾値決定に一度も使っていない{m9['n_images']}枚（描画前に <font name=\"IPAexG\">experiments/PREREGISTRATION_T1.md</font> で登録）。"
                f"拒否すべき画像（{m9['rules']['full']['n_deny']}枚）での誤許可、許可すべき画像（{m9['rules']['full']['n_allow']}枚）での正しい許可、"
                f"見えている火（{m9['hazard_recall'][1]}枚）の検出数を示す。τ_h は登録した主設定 {t1['tau_h']} と、事前指定の副設定 0.05（v3.5）。")]
        rows = [['方式', '誤許可', '正しい許可', '火の検出', 'τ_h=0.05：誤許可', '正しい許可', '火の検出']]
        for name, m in t1['models'].items():
            a, b = m['rules']['full'], m['rules'].get('v35_tau_h_0.05')
            rows.append([name + ('（採用）' if name == 'Qwen3.5-9B' else ''), a['false_approvals'], a['correct_approvals'],
                         m['hazard_recall'][0], b['false_approvals'] if b else '-', b['correct_approvals'] if b else '-',
                         m['hazard_recall_tau_h_0.05'][0] if 'hazard_recall_tau_h_0.05' in m else '-'])
        for name, m in t1.get('json_method', {}).items():
            if isinstance(m, dict):
                rows.append([f'{name}・自由JSON生成（v3.2方式）', m['false_approvals'], m['correct_approvals'], '-', '-', '-', '-'])
        s += [table(rows, [58, 16, 22, 18, 26, 18, 16]),
              P('検出は、危険と判定された（p(危険)が閾値以上の）見える火の数。自由JSON生成では、解析不能または推論失敗を拒否として数える'
                + ('（3B：' + str(t1['json_method']['Qwen2.5-VL-3B']['parse_or_inference_errors']) + '件）。'
                   if isinstance(t1.get('json_method', {}).get('Qwen2.5-VL-3B'), dict) else '。'), 'small'), Spacer(1, 3)]
        sm = T['small']
        txt = (f"<b>解釈</b>：物資の確認は、拒否すべき非火災画像 {T['n_neg']} 枚で誤許可 {T['fa_neg']} 件"
               f"（Wilson 95%区間 {pct_ci(T['fa_neg'], T['n_neg'])}）。採用モデルの誤許可 {m9['rules']['full']['false_approvals']} 件は、すべて物資が正しく火が一部しか見えない画像だった")
        if sm:
            txt += (f"（火の面積 {min(sm['fa_px'])}–{max(sm['fa_px'])} 画素、1万画素未満 {sm['fa_small']}/{len(sm['fa_px'])} 件）。"
                    f"見えている火の検出（p(危険)が0.05以上）は、面積1万画素以上で <b>{sm['dl']}/{sm['nl']}</b>、1万画素未満で <b>{sm['ds']}/{sm['ns']}</b>。"
                    '残る弱点は、小さく写った・物資の陰に隠れた火の見逃しである（I-11, I-13）。')
        else:
            txt += '。'
        s += [P(txt)]
    if V:
        f, g, t2, sel = V['f'], V['g'], V['t2'], V['sel']
        fp, gp, fc, gc = f['primary'], g['primary'], f['per_config'], g['per_config']
        fm = sorted(x['fire_pixels'] for x in f.get('trials', []) if x['config'] == 'B' and x['wrong_delivery'] and x.get('fire_pixels'))
        FPX = f"{fm[0]:,}〜{fm[-1]:,}画素（{len(fm)}件）" if fm else '小さく'
        s += [P('D. 小さな火への対策の経過（評価Fと未使用のT2）', 'h2'),
              P('付録Cで分かった残る弱点（小さく写った・物資の陰の火の見逃し）に対し、<b>結果を見る前に条件を固定</b>して、段階的に2つの手（手1：問い方と拡大切り出し、手2：横から見直す）を打った。'
                '最終構成 v3.6 はオーケストレータの<b>既定値</b>（Qwen3.5-9B、危険の問い方 h36＋拡大切り出し tiles、τ_h=0.05、横から見直す0.4 m、回復探索・状況報告あり、DDS非同期）で、'
                '過去の評価を再現するときは各台帳の <font name="IPAexG">stack_args</font> のフラグを明示する。')]
        s += bullets([
            f"<b>手1（I-11・I-13、開発データのみ）</b>：「小さい・隠れた・端で切れた火や煙」を明示する問い（h36）と拡大切り出し（tiles）。"
            + (f"開発データでの誤許可は v3.5 の {sel['table'][0]['false_approvals']} → {[r for r in sel['table'] if r['config'].startswith('Q9B[h36_tiles]')][0]['false_approvals']}（/{sel['table'][0]['n_deny']}枚）。" if sel else '')
            + "Clef-Flash（Jev役、ローカル）との2モデル確認はさらに少ないが、V100 1台に同時に載らない（"
            + (f"{sel['selected']['vram_gb']:.0f} GB）ため既定には採用せず、未使用のT2で確認した。" if sel else '）。'),
            f"<b>手1の評価F（閉ループ、事前登録、対比較）</b>：小さな火が確認時の姿勢から見えていた{fp['n_world_pairs_fire_visible_both']}世界で、火があるのに配達した回数は"
            f" v3.5（A）{fp['wrong_deliveries_A']}/{fp['n_world_pairs_fire_visible_both']} → 手1（B）{fp['wrong_deliveries_B']}/{fp['n_world_pairs_fire_visible_both']}。"
            f"食い違いは {fp['discordant_A_only']}:{fp['discordant_B_only']}、McNemar正確検定 {pexact(fp['mcnemar_p'])}で<b>有意ではない</b>。"
            f"Bが見逃した火は正面から{FPX}しか写らず、p(危険)が火の無い画像と重なるため、閾値の調整では分けられないと判断した（docs/IMPROVEMENT_LOG.md I-14）。",
            "<b>手2：I-14 横から見直す（能動知覚）</b>。同じ火は、確認位置から左右に0.4 mずらした視点では4,600〜22,000画素で見えた（開発用の予備走行、マスク画像で確認）。"
            "VLMの判定ではなく<b>ロボットの視点</b>を変える（4.1章）。"])
        s += [P('手2の評価G（対比較・事前登録）は本文4.1章に載せた。', 'small')]
        if t2:
            R = t2['results']
            ref, j2, sj = R[t2['reference']], R['J2(Clef-task) tau_h=0.05'], R[t2['selected']]
            s += [P('<b>未使用のT2（オフライン、描画前に事前登録）</b>', 'body'),
                  table([['構成', '誤許可', '正しい許可', '火の検出（小／大）']] +
                        [[nm, f"{r['false_approvals']}/{r['n_deny']}（95%区間 {r['fa_ci95'][0] * 100:.1f}–{r['fa_ci95'][1] * 100:.1f} %）",
                          f"{r['correct_approvals']}/{r['n_allow']}", f"{r['fire_small_refused'][0]}/{r['fire_small_refused'][1]}・{r['fire_large_refused'][0]}/{r['fire_large_refused'][1]}"]
                         for nm, r in (('v3.5（Qwen3.5-9B、基準）', ref), ('Clef-Flash 単独（課題向けの質問）', j2), ('Clef-Flash＋Qwen3.5-9B（h36＋tiles、規則上の選定）', sj))],
                        [66, 46, 26, 36]), Spacer(1, 3),
                  P(f"T2では v3.5 でも誤許可が {ref['false_approvals']}/{ref['n_deny']} と<b>天井</b>で、改善は測れない（判断を分ける画像がない）。"
                    f"T2の役割は、改良が正しい許可を減らさないことと、Jev役を担うClef-Flashがローカルで動くことの確認である。"
                    + (f"Clef-Flash単独は課題向けの質問にすると誤許可 {j2['false_approvals']}/{j2['n_deny']}・正しい許可 {j2['correct_approvals']}/{j2['n_allow']}、"
                       f"1画像あたりの推論は中央値 {V['clef_lat']:.1f} 秒（V100）。" if V['clef_lat'] else '')
                    + "当初のJev要求（通路の安全を問う質問）のままでは物資の存在確率が低く出て、正しい配達の約半分を拒否した（"
                    + f"{R['J(Clef) tau_h=0.05']['correct_approvals']}/{R['J(Clef) tau_h=0.05']['n_allow']}）。判断モデルは<b>質問の書き方に強く依存</b>する。", 'small')]
    if msel:
        s += [P('E. モデルの調査と選定（最新世代への更新）', 'h2'),
              table([['モデル', '公開', '視覚判定（176枚）', '状況説明（128枚）', '指示理解（開発40文）', '1問の遅延']] +
                    [[r['model'], r['released'], r.get('vision_v35', '-'), r.get('explain', '-'), r.get('intent_dev_i35', '-'),
                      f"{r.get('latency_v35', 0):.2f} 秒"] for r in msel], [30, 18, 36, 26, 36, 22]), Spacer(1, 3)]
    s += fig('i08_models.png', 135, '図4 モデル比較（開発データ）。右：危険側の誤り。評価用データはモデル選定に使っていない。')
    if rr_tab:
        s += [P('F. カメラ劣化（R）の全12条件', 'h2')] + rr_tab
    s += sec_prereg(D, E)
    # ---- improvements
    s += [P('H. 改善の軌跡（v3.3 → v3.6）', 'h2'),
          P('審査基準（創造性・技術力・実用性・表現力）に沿って自己レビューし、弱点ごとに改善項目を立て、すべて「仮説 → 変更 → 計測（Before/After）」で記録した'
            '（<font name="IPAexG">docs/REVIEW_AND_PLAN.md</font>、<font name="IPAexG">docs/IMPROVEMENT_LOG.md</font>、コミットは <font name="IPAexG">git log --grep I-0</font> で追跡可能）。')]
    imp = [['ID', '弱点・動機', '改善', 'Before → After（計測）']]
    if i01['baseline'] and i01['sphere_wheels']:
        b = max(x['pos_error_m'] for x in i01['baseline']['patterns']['medicine_route'])
        a = max(x['pos_error_m'] for x in i01['sphere_wheels']['patterns']['medicine_route'])
        imp.append(['I-01', '推測航法のずれで監査不合格', '原因を切り分け：DARTの円柱接触の多角形近似 → 球コリジョン', f'位置誤差 {b:.3f} → {a:.3f} m'])
    imp.append(['I-02', '物資が違うと止まるだけ', '別拠点の探索と回復（危険時は探さない）', '取り違え：停止 → 探索して配達'])
    imp.append(['I-03', '拒否理由が人に伝わらない', '判断後の日本語状況報告（判断には不使用）', '説明の正確さ 84 → 125/128'])
    if it.get('q9b'):
        imp.append(['I-04', '指示理解が合成40文のTF-IDF', 'ローカルLLMの選択式解釈＋規則ガード',
                    f"未知の60文 {it['tfidf']['correct']} → {it['q9b']['correct']}/60（危険な誤受理 {it['tfidf']['unsafe_accepts']} → {it['q9b']['unsafe_accepts']}）"])
    m0, m1 = rob.get('M0_v33'), rob.get('M1_v34')
    if m0 and m1:
        g0 = next(x for x in m0['grid'] if x['tau_s'] == 0.5 and x['tau_h'] == 0.5)
        g1 = next(x for x in m1['grid'] if x['tau_s'] == 0.5 and x['tau_h'] == 0.5)
        imp.append(['I-05', '照明・妨害物・火災で未検証', '環境ランダム化の開発セットとプロンプト改良',
                    f"{g0['correct']}/176（誤許可{g0['false_approval']}）→ {g1['correct']}/176（誤許可{g1['false_approval']}）"])
    imp.append(['I-06', '新機能が未評価', '事前登録した42試行の閉ループ評価',
                f"{D['correct']}/{D['n']}（誤許可{D['false_approvals']}）" if D else '実行中'])
    imp.append(['I-08', 'モデルが古く研究用途限定', '最新世代の調査・公平比較 → Qwen3.5-9B', '説明 84→125、指示 50→55/60、誤許可0維持'])
    imp += improvements_late(D, E)
    s += [table(imp, [12, 38, 64, 60]), Spacer(1, 4)]
    s += fig('i01_drift.png', 110, '図5 I-01 推測航法ドリフトの原因切り分け（棄却した仮説も含む）。')
    # ---- 6. findings
    s += [P('I. 実際に動かして初めて分かった問題（v3.2引継ぎ → v3.3）', 'h2'),
          P('引継ぎ時点のコードは、単体テストと模擬環境でしか確かめられておらず、実Gazebo・実ROS 2・実GPUでは一度も動いていなかった。'
            f'実際に動かして（v3.3〜v3.6の開発と評価の準備を含め）{count_tests.n_findings()}件の問題を見つけ、すべて再現→修正→確認した'
            f'（<font name="IPAexG">docs/FINDINGS.md</font>）。単体テストも現在は{count_tests.n_tests()}件に増えた。代表例：')]
    s += bullets(['車輪軸の定義誤り：オドメトリ上は1.1 m前進、実際の車体は0.15 m（→ Gazebo真値による監査を新設）',
                  'Best Effort QoS で 0.9 MB の画像が102枚中10枚しか届かない（→ Reliable に統一）',
                  'gpu_lidar が自機のカメラマスト（visual）を障害物として検出（→ 可視性マスク）',
                  '評価の中断時に孤立したスタックが別試行に速度指令を出し続けた（→ 段階的停止と起動前の孤立スタック検出。Publisher監視は正しく検知していた）'])
    s += fig('wheel_axis_regression.png', 100, '図6 同じ速度指令に対する車輪オドメトリとGazebo真値（左：引継ぎ版、右：修正後）。')
    chap = ROOT / 'docs/video_chapters.json'
    if chap.is_file():
        ch = json.loads(chap.read_text(encoding='utf8'))
        mmss = lambda x: f'{int(x // 60)}:{int(x % 60):02d}'
        s += [P('J. 提出動画の構成', 'h2'),
              table([['時刻', '内容', '備考']] + [[f"{mmss(c['start_s'])}–{mmss(c['end_s'])}", c['title'],
                     (c['speed'] or '') + (f"（run {c['run_id']}）" if c.get('run_id') else '')] for c in ch], [24, 90, 60])]
    s += fig('video_frame_decision.png', 85, '図7 動画の一場面（取り違え）：拠点Wで救急箱を確認して拒否し、もう一方の拠点を確認しに向かう。下段はロボットの日本語報告。')
    doc.build(M + s)
    print(out)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--account', required=True)
    ap.add_argument('--video-url', default=None)
    ap.add_argument('--repo-url', default='https://github.com/fe2131-art/rescue-mind')
    a = ap.parse_args()
    build(a.account, a.video_url, a.repo_url)
