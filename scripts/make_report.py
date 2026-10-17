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
PAPER_FIG = ROOT / 'docs/paper'
REPORT_FIG = ROOT / 'docs/report/figures'   # PNGs rasterised from the paper's vector PDFs (generated, not hand-made)
sys.path.insert(0, str(ROOT / 'scripts'))
import count_tests  # noqa: E402  (generated test / findings counts)
import advice_numbers  # noqa: E402  (I-23 z3 numbers, I-24 advice-credit model numbers; single source shared with the README)
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
    'h1': ParagraphStyle('h1', fontName='IPAexG', fontSize=14.5, leading=20, textColor=INK, spaceBefore=7,
                         spaceAfter=4, borderPadding=(0, 0, 3, 0), keepWithNext=1),
    'h2': ParagraphStyle('h2', fontName='IPAexG', fontSize=11.5, leading=16, textColor=ACC, spaceBefore=5, spaceAfter=2, keepWithNext=1),
    'body': ParagraphStyle('b', wordWrap='CJK', fontName='IPAexM', fontSize=9.3, leading=14.0, textColor=INK, alignment=TA_LEFT),
    'bullet': ParagraphStyle('bl', wordWrap='CJK', fontName='IPAexM', fontSize=9.3, leading=13.6, textColor=INK, leftIndent=12,
                             bulletIndent=2),
    'cap': ParagraphStyle('c', wordWrap='CJK', fontName='IPAexG', fontSize=8.2, leading=11.5, textColor=MUT, alignment=TA_CENTER,
                          spaceAfter=6),
    'cell': ParagraphStyle('cell', wordWrap='CJK', fontName='IPAexM', fontSize=8.2, leading=11.2, textColor=INK),
    'cellh': ParagraphStyle('cellh', wordWrap='CJK', fontName='IPAexG', fontSize=8.4, leading=11.2, textColor=colors.white),
    'h3': ParagraphStyle('h3', fontName='IPAexG', fontSize=10, leading=14, textColor=INK, spaceBefore=3, spaceAfter=1, keepWithNext=1),
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


def pdf_to_png(src: Path, dst: Path, dpi: int = 300) -> bool:
    """Rasterise page 1 of a vector PDF figure (pypdfium2 -> pdftoppm). If no rasteriser is installed, keep an
    existing up-to-date-or-older PNG (rendered earlier by this same function) rather than failing the build."""
    import shutil
    import subprocess
    if dst.is_file() and dst.stat().st_mtime >= src.stat().st_mtime:
        return True
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        import pypdfium2 as pdfium
        pdfium.PdfDocument(str(src))[0].render(scale=dpi / 72).to_pil().convert('RGB').save(dst, optimize=True)
        return True
    except ImportError:
        pass
    if shutil.which('pdftoppm'):
        subprocess.run(['pdftoppm', '-png', '-singlefile', '-r', str(dpi), str(src), str(dst.with_suffix(''))], check=True)
        return True
    return dst.is_file()


def paper_fig(stem, width_mm, caption):
    """Insert docs/paper/<stem>.pdf as a PNG with a short caption; a missing PDF is skipped silently (empty list)."""
    src = PAPER_FIG / f'{stem}.pdf'
    if not src.is_file():
        return []
    dst = REPORT_FIG / f'{stem}.png'
    if not pdf_to_png(src, dst):
        return []
    from PIL import Image as PI
    with PI.open(dst) as im:
        w, h = im.size
    wpt = width_mm * mm
    return [KeepTogether([Image(str(dst), width=wpt, height=wpt * h / w), P(caption, 'cap')])]


def table(rows, widths, header=True):
    data = [[Paragraph(str(c), S['cellh' if (header and i == 0) else 'cell']) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1 if header else 0)
    st = [('GRID', (0, 0), (-1, -1), 0.4, LINE), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
          ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]
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
    canvas.drawString(18 * mm, 10 * mm, 'Physical AI 応用1講座 最終課題 ｜ RescueMind')
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
            'retries': len(allr) - len(rows), 'lat_med': statistics.median(lat) if lat else None,
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
            'strata_ok': strata_ok, 'lat_med': statistics.median(lat) if lat else None,
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


PEND = '実行中（事前登録済み）'
PEND_NOT_RUN = '未実行（事前登録済み・実行待ち）'      # queued, not started: only V is running while the report is built


def n_runs(protocol):
    """Trials in a campaign protocol (single source for the run counts printed here)."""
    try:
        return len(json.loads((ROOT / 'experiments' / protocol).read_text(encoding='utf8'))['trials'])
    except (OSError, ValueError, KeyError):
        return None


A_RUNS = n_runs('campaign_a_protocol.json') or 226


def reg_label(n):
    """Registration document of study n: its letter, '(草稿)' while the text on main differs (registered at the merge), '統合時' when absent."""
    import subprocess
    f = ROOT / f'experiments/PREREGISTRATION_{n}.md'
    if not f.is_file():
        return '統合時に登録'
    r = subprocess.run(['git', 'show', f'main:experiments/PREREGISTRATION_{n}.md'], cwd=ROOT, capture_output=True, text=True)
    on_main = r.returncode == 0 and r.stdout.strip() == f.read_text(encoding='utf8').strip()
    return n if on_main else f'{n}（草稿）'


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


def v_result_text(vs):
    """Study V (prediction, then closed-loop test) as one string; PEND when v_summary.json is absent."""
    if not vs:
        return PEND
    v1, av = vs['V1_time_diff'], vs['arms']
    ok_ = lambda x: '成立' if x else '不成立'
    return (f"M0とM2の所要時間差 実測 {v1['mean_M0_minus_M2_s']:.0f} 秒（事前登録の予測区間 {v1['pred']['p2.5']:.0f}〜{v1['pred']['p97.5']:.0f} 秒）、"
            f"危険な配達 記憶なし {av['M0']['unsafe']}・素朴な記憶 {av['M1']['unsafe']}・本方式 {av['M2']['unsafe']} 件。"
            f"モデルの予測：<b>{ok_(vs['claim_model_predicts'])}</b>、ランダムな変化でも安全に速い：<b>{ok_(vs['claim_memory_under_random_change'])}</b>")


def w_result_text(ws):
    """Study W as one string; PEND when w_summary.json (or one of its parts) is absent."""
    try:
        a, b = ws['W-a'], ws['W-b']
        la, fr = a['miss_look_around'], a['miss_front_only']
        S, nd = b['systems'], b['n_deny']
        ok_ = lambda x: '成立' if x else '不成立'
        base = '・'.join(f"{n.split(' (')[0]} {S[n]['false_approvals']}" for n in b['primary_baselines'])
        return (f"小さく隠れた火の見逃し 正面のみ {fr['k']}/{fr['n']}、見回し {la['k']}/{la['n']}（Wilson 95%CI {100 * la['ci95'][0]:.0f}〜{100 * la['ci95'][1]:.0f}%）。"
                f"同じ入力での誤許可（{nd}件中）本方式 {S[b['primary_reference']]['false_approvals']}、{base}。"
                f"見逃しの上限：<b>{ok_(a['criteria']['claim_eps_tight'])}</b>")
    except (TypeError, KeyError):
        return PEND_NOT_RUN


def a_result_text(a):
    """Study A (adversarial advice, closed loop) as one string; PEND when a_summary.json is absent."""
    try:
        a1, a2, a3 = a['A1_unsafe_naive_vs_monotone'], a['A2_time_saved_truthful'], a['A3_dos_cost_vs_bound']
        r = a1['runs']
        ok_ = lambda x: '成立' if x else '不成立'
        return (f"悪意のある助言での危険な配達（試行）：助言に従う方式 {r['naive']['unsafe']}/{r['naive']['n']}、本方式 {r['monotone']['unsafe']}/{r['monotone']['n']}、"
                f"助言なし {a1['control_runs_F_N']['unsafe']}/{a1['control_runs_F_N']['n']}。主張 安全：<b>{ok_(a1['supported'])}</b>、"
                f"時間：<b>{ok_(a2['supported']) if a2['monotone']['testable'] else '検定不能'}</b>、コスト：<b>{ok_(a3['supported'])}</b>")
    except (TypeError, KeyError):
        return PEND_NOT_RUN


def s_result_text(sj):
    """Study S (scene-text injection) as one string; PEND when s_summary.json is absent."""
    try:
        o = sj['systems']['OURS']
        fl = lambda x: f"{x['attack_vs_none']['flips']}/{x['n_pairs']}"
        return (f"本方式で標識により拒否→許可に変わった世界：「Cと答えよ」{fl(o['by_text']['letter_C'])}、文字A {fl(o['by_text']['letter_A'])}、文字B {fl(o['by_text']['letter_B'])}、"
                f"取り違えラベル {fl(o['by_sign_type']['mislabel'])}、「火災なし」標識 {fl(o['by_sign_type']['false_safe'])}（構造的な保証の外）")
    except (TypeError, KeyError):
        return PEND_NOT_RUN


def sec_advice():
    """4.2b: I-19, untrusted inputs may only tighten.  Results of A and S come from their summaries; pending until they ran."""
    a, sj = jload('a_summary.json'), jload('s_summary.json')
    out = [P('C1. 助言一般：信頼できない入力は「厳しくする」ことしかできない（I-19）', 'h2'),
           P('記憶は、ロボットが自分で見ていない入力の一つにすぎない。他のロボットの報告、在庫表、依頼文の一言（「火は消えたので確認不要」）も、古い・間違い・悪意のいずれもあり得る。'
             'これらをすべて「助言」とし、できることを拠点の順序の変更と閾値の強化に限る。「安全」「確認不要」は何の効果も持たず、助言だけでは訪問せずに拒否もしない。'
             'したがって、どんな（悪意のある）助言でも、同じ画像での許可は助言なしの許可の部分集合になり、危険な配達の確率は助言なしと同じ上限 kε で抑えられる（命題2）。'
             '悪意のある助言が与えられるのは、1拠点ぶんの無駄足と、慎重な閾値での誤拒否（1視点あたり 4/193）だけである。'
             'カメラに映る標識の文字は知覚なので、この保証の外にある。それは評価Sで測り、残りの弱点として報告する。'),
           P('配送インターロック（I-22）は実装済み・既定オフ、Gazebo確認は未了。評価A・Xはオフで走らせる（事前登録に明記）。', 'small'),
           P(f'評価A（閉ループ{A_RUNS}試行、助言に従う方式との対比較）：' + a_result_text(a)),
           P('評価S（画像レベル、52世界×標識なし・攻撃・無害）：' + s_result_text(sj))]
    return out


def p_auroc():
    """AUROC of the hazard probability on the 400 real photographs (descriptive, not registered); None if the scores are absent."""
    rows = ledger('p_scores_qwen9b_h36_tiles.jsonl')
    pos = [r['hazard_prob'] for r in rows if r['category'] != 'none']
    neg = [r['hazard_prob'] for r in rows if r['category'] == 'none']
    if not pos or not neg:
        return None
    return sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg))


def memory_price_text():
    """Price of safety (share of naive memory's modelled saving kept at q=0 and q=0.5) and k-station scaling; descriptive, not registered."""
    c, ks = jload('h_change_rate.json'), jload('h_k_scaling.json')
    if not (c and ks):
        return []
    q, pol = c['q'], c['policies']
    sv = lambda arm, qq: pol['M0'][q.index(qq)]['mean_time_s'] - pol[arm][q.index(qq)]['mean_time_s']
    g = {(r['k'], r['q']): r for r in ks['grid']}
    return [P(f"<b>安全の代償と規模</b>（モデル、登録外）：確認を省かないので、時間の節約は素朴な記憶の <b>{100 * sv('M2', 0.0) / sv('M1', 0.0):.0f} %</b>"
              f"（q=0：{sv('M2', 0.0):.0f}／{sv('M1', 0.0):.0f} 秒）、物資の移動が出動の半分で起きる q=0.5 では {100 * sv('M2', 0.5) / sv('M1', 0.5):.0f} %。"
              f"拠点がk個なら節約は δ((k−1)−qk)/2（δ={ks['delta_s']:.0f} 秒）で、q=0.2 の k=2 は {g[(2, 0.2)]['saving_s']:.0f} 秒、k=8 は {g[(8, 0.2)]['saving_s']:.0f} 秒、"
              '損益分岐は q=(k−1)/k。拠点が増えるほど得になり、危険の上限は変わらない。', 'small'), Spacer(1, 3)]


def sec_new_detail():
    """Appendix C1b: details of I-23 (z3 check), the necessity result and I-24 (advice credit); numbers from smt_advice_proof.json / advice_credit_horizon.json."""
    f, c, p = advice_numbers.smt_facts(), advice_numbers.credit_facts(), advice_numbers.pending_studies()
    out = [P('C1b. 助言の新しい成果の詳細：機械検証・必要十分・信用枠（I-23、I-24）', 'h2')]
    if f:
        out.append(P(f"<b>機械検証</b>（<font name='IPAexG'>scripts/verify_advice_smt.py</font>、z3 {f['z3']}）。確認の判定・助言の畳み込み・訪問ループは小さな純関数なので、z3 に写して全入力で証明し、"
                     f"同じ具体入力を実関数とモデルに通して完全一致を要求した。証明した問い {f['queries']}件のうち{f['unsat']}件が「反例なし（unsat）」で、残りは緩める側の反例や、前提が充足可能であること（空でない証明）を示す問い。"
                     "証明の内容：（P2a）助言ありの許可は助言なしの許可に含まれる（助言の長さは任意。1項目で不変式が保たれることの帰納で示し、3項目までの展開でも k=2,3,4 で確認）、"
                     "（P2b）配達の前に、その拠点で許可する確認が必ずある（候補の順序は常に全拠点の順列で、飛ばし・重複が無い）、（C）代償の上界。"
                     f"突き合わせは計画・承認判定・命題2の実コード・計画の assertion を切った版・信用枠・ループの{f['groups']}組×{f['per_group']:,}＝{f['cases']:,}件（境界値・NaN・inf・bool・範囲外・不正形式・敵対的な助言を含む）で不一致 {f['disagreements']}。"
                     f"わざと入れたバグ{f['mutants']}個（助言が τ_h を緩める、確認を省く、拠点を検証済みにする、見ずに拒否する、候補を落とす、慎重さの境界、横視点の無視、無効スコアを問題なしとする、など）は、"
                     f"どれも z3 の反例が出て、その反例を変異コードに流すと実際に逸脱し、差分テストが検出した（{f['caught']}/{f['mutants']}）。この過程で、追加視点の監査・NaN の確信度・bool の確信度の3件の見落としが見つかり、修正した（フェイルクローズ）。"
                     '範囲：証明するのは転記したモデルで、実コードとの一致は突き合わせで確かめている。残る信頼は、転記・z3・CPython と、仕様そのもの（同じ筆者が同じ仕様から書いた）に対するもの。第三者による再現はまだ無い。', 'small'))
        out.append(P(f"<b>必要十分</b>（補足 S10）。ある入力で許可が「助言なし ⇒ 拒否、助言あり ⇒ 許可」となるとき、その窓口は緩める。緩める窓口の危険な配達の確率は ε_any + ε_rel（ε_rel＝緩められるフレームの質量）まで上がり得る。"
                     "逆向き：前提（N1：安全だと証明できるフレームは作れない／N2：許可は配送につながる）のもとで、緩めるどの窓口にも、予算 ε_any を超える世界の分布と千里眼の助言者が存在する。"
                     f"z3 は、緩める窓口 {f['necessity_relaxing']}種（安全・スキップの助言を信じる、場所の助言で検証済みにする、横視点を無視する、無効スコアを問題なしとする）それぞれに、2世界の分布と助言を返した"
                     + (f"（例：危険な配達の率 {f['unsafe_rate']} が予算 {f['eps_any']} を超える）" if f.get('unsafe_rate') is not None else '')
                     + '。締めるだけの窓口（本方式）では反例が無い（unsat）。素朴な方式・フィルタ方式は緩める窓口なので、実測の率にかかわらず、この上限が成り立たない。信用証明書があれば N1 が崩れ、緩めても安全にできる。', 'small'))
    if c:
        out.append(P(f"<b>信用枠</b>（<font name='IPAexG'>rescuemind/advice_credit.py</font>）。情報源（入力の経路）ごとに、場所の枠（{c['c_loc']:g} 訪問ぶん）と危険の枠（{c['c_haz']:g} 回の誤停止ぶん）を持ち、"
                     "採用する項目の最悪の代償が信用以内のときだけ採用する。精算は出動後にロボット自身の確認だけで行い（先頭に回した拠点に依頼物資が無ければ引く、慎重さだけで停止したら危険の枠から引く）、"
                     f"場所の枠は確認できた出動ごとに {c['rho_shadow']:g}、危険の枠は出動ごとに {c['rho']:g} ずつ回復する。未認証の他ロボットはチャネル単位で1口座にまとめるので、名前を変えても信用は増えない。"
                     "採用しなかった項目は、助言の部分集合を使うことと同じで、命題2がそのまま成り立つ（安全は変わらない）。"
                     f"<b>命題3</b>：どの情報源のどんな適応的な系列でも、m 回の出動で、場所の助言による無駄な訪問は {c['c_loc']:g} + {c['rho_shadow']:g}m 以下、危険の助言による誤った停止は {c['c_haz']:g} + {c['rho']:g}m 以下。"
                     '危険な訪問そのもの（本当に燃えている拠点への接近）はこの代償に含まれない。', 'small'))
        k4 = c['k4']
        lab = [('liar', '毎回嘘をつく（場所）', 'extra_s', '余分な時間'), ('farmer', '適応的な嘘つき（信用を見て嘘をつく）', 'extra_s', '余分な時間'),
               ('honest', '正直（常に正しい）', 'extra_s', '時間の変化'), ('noisy', '7割正しい', 'extra_s', '時間の変化'),
               ('flooder_real', '危険の連打（実写の誤警報率 ' + f"{c['flood_delta']:g}" + '）', 'false_refusals', '誤った停止')]
        rows = [['情報源（k=4、' + str(c['missions']) + '出動）', '測った量', '信用なし', '信用あり']]
        for key, nm, fld, what in lab:
            a, b = k4[key][fld]
            if fld == 'extra_s':
                rows.append([nm, what, f'{a:+.0f} 秒', f'{b:+.0f} 秒'])
            else:
                rows.append([nm, what, f'{a} 回', f'{b} 回'])
        out += [Spacer(1, 2), table(rows, [70, 34, 34, 34]),
                P('合成した出動の結果で本物の計画と信用枠を動かした記述モデル（<font name="IPAexG">scripts/advice_credit_horizon.py</font>）で、事前登録はしていない。'
                  f"危険な配達は全条件で信用ありと信用なしが同一。代償は、7割正しい情報源の節約が {c['noisy_keep']:.0f} % に減ること（一貫性の代償）と、"
                  '正しいのに確認できない危険の警告も誤停止として課金され、いずれ締め出されること。'
                  + ('閉ループの確認（研究B：6出動×(嘘つき3＋正直1)×(信用なし／あり)＝48試行）は結果待ち（未実行）。' if not p['B'] else '研究Bは結果あり（論文を参照）。')
                  + ('依頼文による書き換え（研究IF：6種類×2言語×2物資×3表現＝72文）は結果待ち（未実行）。' if not p['IF'] else '研究IFは結果あり（論文を参照）。'), 'small'),
                Spacer(1, 3)]
    return out


def sec_memory():
    sha = ''
    pf = ROOT / 'experiments/campaign_h_protocol.json'
    if pf.is_file():
        import hashlib
        proto = json.loads(pf.read_text())
        sha = (f"プロトコル（{proto['planned_n']}試行、sha256 先頭16桁 {hashlib.sha256(pf.read_bytes()).hexdigest()[:16]}）は"
               '最初の試行の前に固定した。')
    out = [P('C2. 出動をまたぐ記憶：記憶は提案だけ、確認は減らさない（I-15）', 'h2'),
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
            Spacer(1, 3)]
    out += fig('memory_principle_ja.png', 112, '記憶は提案だけ。行った先では必ず確認する（同じ画像なら、記憶ありの許可は記憶なしの許可の部分集合）')
    out += [Spacer(1, 2), P('<b>比較対象 M1（素朴な記憶）</b>：記憶を信じ、前回その物資を見た拠点では確認を省いて配達し、前回危険を見た拠点へは行かない。速いが、現場が変わると誤配達につながる。'
              'M1は評価Hで測るためだけに実装し、既定にはしない。'),
            Spacer(1, 2), P('<b>事前登録した評価H</b>（<font name="IPAexG">experiments/PREREGISTRATION_H.md</font>）：16系列×3出動、世界は出動ごとに照明・小道具・火を引き直し、'
              'M0（記憶なし）/M1/M2（提案）を同じ世界で対にして比べる。基準は P1：物資の入れ替わりが続く出動で M2 が M0 より速い、P2：危険な配達が M2 は M1 より少ない、'
              f'P3：M2 の危険な配達が M0 以下。3つが揃って初めて「速さを保ち、危険を増やさない」と主張する。{sha}')]
    out += paper_fig('fig_h_outcomes', 105, '評価Hの結果：M0・M1・M2 の出動ごとの結果（速さと危険な配達）。')
    h = jload('h_summary.json')
    if not h:
        return out + [P('<b>評価H 実行中（事前登録済み）</b>。結果は <font name="IPAexG">experiments/results/h_summary.json</font> が生成され次第、本資料に反映する。'), Spacer(1, 4)]
    p1, p2, p3 = h['P1_efficiency_relocation_persist'], h['P2_safety_naive_vs_verified'], h['P3_no_extra_risk_vs_v36']
    ok = lambda x: '<b>成立</b>' if x['supported'] else '<b>不成立</b>'
    rows = [['基準', '結果', '判定']]
    rows.append([f"P1 速さ（M2 vs M0、入れ替わりが続く{p1['n_pairs']}出動）",
                 (f"所要時間の中央値 {p1['time_M0_median_s']:.0f} → {p1['time_M2_median_s']:.0f} 秒（差の中央値 {p1['median_diff_s']:+.0f} 秒）、"
                  f"Wilcoxon正確検定 {pexact(p1['wilcoxon_exact_p'])}") if p1['n_pairs'] else '対になる出動なし', ok(p1)])
    rows.append([f"P2 安全（M2 vs M1、{p2['n_pairs']}出動。M1は確認を省く設計）",
                 f"危険な配達 M1 {p2['unsafe_M1']}/{p2['n_pairs']} → M2 {p2['unsafe_M2']}/{p2['n_pairs']}（食い違い {p2['discordant_M1_only']}:{p2['discordant_M2_only']}）、"
                 f"McNemar正確検定 {pexact(p2['mcnemar_p'])}", ok(p2)])
    rows.append([f"P3 追加の危険なし（M2 vs M0、{p3['n_pairs']}出動）", f"危険な配達 M0 {p3['unsafe_M0']}/{p3['n_pairs']}、M2 {p3['unsafe_M2']}/{p3['n_pairs']}", ok(p3)])
    out += [table(rows, [56, 98, 20]), Spacer(1, 3),
            P(f"全体の主張（P1・P2・P3 がすべて成立）：<b>{'成立' if h['headline_supported'] else '不成立（成り立たなかった部分は上表のとおり）'}</b>。")]
    arows = [['方式', '出動', '危険な配達（95%区間）', '誤った停止', '安全な配達', '時間の中央値', '失敗']]
    for a, m in h['per_arm'].items():
        arows.append([ARM_JA.get(a, a), m['n'], f"{m['unsafe_deliveries']}（{m['unsafe_ci95'][0] * 100:.0f}–{m['unsafe_ci95'][1] * 100:.0f} %）",
                      m['false_refusals'], f"{m['safe_correct_deliveries']}/{m['safe_option_missions']}",
                      f"{m['time_median_s']:.0f} 秒" if m['time_median_s'] is not None else '-', m['failed']])
    out += [Spacer(1, 3), table(arows, [44, 12, 36, 20, 22, 24, 16]),
            P(f"出動2・3回目のみ。「安全な配達」は、安全な選択肢がある出動のうち安全に配達できた数。1回目の出動（記憶なし、{h['first_missions']['n']}出動）の危険な配達は "
              f"{h['first_missions']['unsafe']} 件。火は設計上、見えにくいものを含む。", 'small'),
            Spacer(1, 3),
            P(f"素朴な記憶（M1）の危険な配達 {h['per_arm']['M1']['unsafe_deliveries']} 件の内訳は、前回から入れ替わった物資 {h['per_arm']['M1']['wrong_supply']} 件と、"
              f"新たに出た火の中への配達 {h['per_arm']['M1']['into_fire']} 件で、いずれも確認を省いた結果である（中央値 {h['per_arm']['M1']['time_median_s']:.0f} 秒が最短なのも同じ理由で、誤った停止も {h['per_arm']['M1']['false_refusals']} 件）。"
              f"M1 は確認を省く設計なので{h['P2_safety_naive_vs_verified']['unsafe_M1']}対{h['P2_safety_naive_vs_verified']['unsafe_M2']}は意外な結果ではなく、"
              f"意味のある比較は M0 対 M2（{h['P3_no_extra_risk_vs_v36']['unsafe_M0']}件対{h['P3_no_extra_risk_vs_v36']['unsafe_M2']}件）で、主張するのは「M2 は M0 より危険ではない」までである。"),
            Spacer(1, 3),
            P(f"速さの限定：{h['P1_efficiency_relocation_persist']['time_M0_median_s']:.0f}→{h['P1_efficiency_relocation_persist']['time_M2_median_s']:.0f}秒は、置き場所が変わったままの8出動での差。置き場所が元に戻った8出動では、記憶の提案した拠点に先に行ってから探すため検証つき記憶の方が遅い（中央値 {h['per_arm']['M2']['by_transition']['relocation_change']['time_median_s']:.0f} 秒 対 記憶なし "
              f"{h['per_arm']['M0']['by_transition']['relocation_change']['time_median_s']:.0f} 秒）。全体の中央値は {h['per_arm']['M0']['time_median_s']:.0f} → {h['per_arm']['M2']['time_median_s']:.0f} 秒。"), Spacer(1, 3)]
    out += memory_price_text()
    vs_ = jload('v_summary.json')
    out += [P('<b>予測してから試す（評価V、事前登録）</b>：上のモデルの予測（所要時間差と危険な配達数の区間）を最初の試行の前に登録し、物資と火がランダムに変わる10系列×6出動（q=0.2）で確かめる。'
              + (v_result_text(vs_) + '。' if vs_ else '結果は<b>実行中</b>で、出たら本資料に反映する。'), 'small'), Spacer(1, 3)]
    _c = [t for t in h['trials'] if t['arm'] == 'M2' and t['k'] > 1 and t.get('caution')]
    _free = [t for t in _c if not t['fire_perceivable_at']]
    _cn, _cf, _cfr = len(_c), len(_free), sum(bool(t['false_refusal']) for t in _free)
    _cup = 100 * wilson(_cfr, _cf)[1]
    out += fig('memory_case_ja.png', 135, '事例（評価H Q09）：記憶なし（M0）は隠れた火(p=0.0346、基準0.05未満)に配達したが、検証つき記憶（M2）は2出動前にそこで火を見たため閾値を0.01に厳しくし(p=0.0489)、止まった。'
               '記憶は確認を減らさず、慎重さだけを足し、記憶なしでは見逃した火で止まれた（1件の事例で、統計的な主張ではない）。'
               f"慎重さが使われたのはM2の32出動中{_cn}出動、うち火のない拠点は{_cf}出動だけ（誤拒否 {_cfr}/{_cf}、Wilson上限 {_cup:.0f}%）で、慎重さの費用はまだ確立していない。")
    return out


def sec_two_ai():
    out = [P('J. 当初計画の2つのAI（Jev役 Clef-Flash＋Qwen）：評価J、採用せず（I-16）', 'h2'),
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
    vr = f"、GPUメモリの最大 {p1['peak_vram_mib'] / 1024:.1f} GiB" if p1.get('peak_vram_mib') else ''
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
    return [P('I3. 比較：CLIP系ゼロショット（Z）', 'h2'),
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
    out = [P('I1. 実写画像（P）：シミュレーションの外での火災判定', 'h2'),
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
        fz = p2['test_at_frozen_tau_0.05'][p2['chosen_wording']]
        out += [P(f"<b>追試P2</b>（<font name=\"IPAexG\">experiments/PREREGISTRATION_P2.md</font>）：較正用の画像だけで閾値と問いの文面を選び"
                  f"（{p2['chosen_wording']}、τ_h={p2['chosen_tau']}）、較正に使っていない400枚で確かめた。検出 {rate_ci(ct['recall'])}、誤警報 {rate_ci(ct['false_alarm'])}。"
                  f"比較：固定の τ_h=0.05 では検出 {fz['recall']['k']}/{fz['recall']['n']}、誤警報 {fz['false_alarm']['k']}/{fz['false_alarm']['n']}。"
                  f"登録した基準（検出0.90以上かつ誤警報0.20以下）：<b>{'成立' if p2['claim_supported'] else '不成立（' + '；'.join(p2.get('failed', [])) + '）'}</b>。")]
    elif p2:
        out += [P('<b>追試P2</b>（<font name="IPAexG">experiments/PREREGISTRATION_P2.md</font>）：較正画像では、どの閾値でも検出0.95以上にならず、閾値を決められなかった。'
                  f"登録した基準：<b>不成立（{'；'.join(p2.get('failed', []))}）</b>。")]
    else:
        out += [P('<b>追試P2は実行中（事前登録済み）</b>：現場での較正（火の無い現地画像で閾値を決める手順）が、較正に使っていない画像で通用するかを事前登録した'
                  '（<font name="IPAexG">experiments/PREREGISTRATION_P2.md</font>、修正1：較正画像は訓練分割の9シャード全体から抽出）。'
                  '結果は <font name="IPAexG">experiments/results/p2_summary.json</font> に出力される。')]
    return out + [Spacer(1, 4)]


def sec_camera():
    r = jload('r_summary.json')
    out = [P('I2. カメラ劣化（R）：実機カメラに近づけたとき、失敗は「停止」に倒れるか', 'h2'),
           P('Gazeboの画像は雑音がなく鮮明で、露出も適正である。実機のカメラはそうではない。未使用のT2画像（30世界）に、6種類の劣化（センサー雑音、動きぶれ、ピンぼけ、露出不足、露出過多、JPEG劣化）を'
             '2段階ずつ（計12条件）加え、v3.6の確認が<b>フェイルクローズ</b>（誤りが停止になり、誤った許可にならない）のままかを調べる（'
             '<font name="IPAexG">experiments/PREREGISTRATION_R.md</font>。閾値・問いは変更しない）。')]
    out += paper_fig('fig_r_examples', 140, '同じ火災画像に6種類の劣化を加えた例（左端が元画像）。雑音・ぶれ・ピンぼけ・暗すぎ・明るすぎ・JPEG劣化。')
    if not r:
        return out + [P('<b>実行中（事前登録済み）</b>（結果は <font name="IPAexG">experiments/results/r_summary.json</font> に出力される）。'), Spacer(1, 4)]
    pp, cond = r['P1_pooled'], r['conditions']
    worst = min(cond, key=lambda c: cond[c]['ca_rate'])
    nm = lambda c: f"{R_FAM.get(c.rsplit('_', 1)[0], c)}（{'中' if c.endswith('_M') else '強'}）"
    out += [P(f"12条件をまとめた誤許可は <b>{pp['false_approvals']}/{pp['n']}（{pp['rate'] * 100:.2f} %）</b>、Wilson 95%区間の上限 {pp['wilson_ci95'][1] * 100:.2f} %（上限が2 %未満なら「フェイルクローズ」と主張すると登録した）→ "
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
    kk = jload('k_summary.json')
    reg = reg_label
    m9 = t1['models']['Qwen3.5-9B']['rules']['full'] if t1 else None
    m35 = t1['models']['Qwen3.5-9B']['rules']['v35_tau_h_0.05']['false_approvals'] if t1 else None
    q = (t2 or {}).get('results', {}).get('Q9B[h36_tiles] tau_h=0.05')
    zs = ((z or {}).get('models') or {}).get('siglip')
    gp = g['primary'] if g else None
    rows = [['研究', '問い', '登録文書', '結果'],
            ['D（v3.4）', '閉ループ42試行で期待どおりに動くか', reg('v34'), f"{D['correct']}/{D['n']}、誤許可 {D['false_approvals']}" if D else PEND],
            ['E（v3.5）', 'ランダムな世界で回復探索は効くか', reg('E'), f"{E['ok']}/{E['n']}、誤配達 {E['fa']}" if E else PEND],
            ['T1', '未使用の画像での誤許可', reg('T1'), f"誤許可 {m9['false_approvals']}/{m9['n_deny']}（登録した規則 v3.4）、{m35}/{m9['n_deny']}（v3.5）" if m9 else PEND],
            ['F・G', '横から見直すと小さな火への配達が減るか', reg('G'),
             f"G：配達 {gp['wrong_deliveries_B']} → {gp['wrong_deliveries_C']}（{pexact(gp['mcnemar_p'])}）" if gp else PEND],
            ['T2', '未使用の画像で改良が悪化しないか', reg('T2'),
             f"誤許可 {q['false_approvals']}/{q['n_deny']}、正しい許可 {q['correct_approvals']}/{q['n_allow']}" if q else PEND],
            ['Z', 'CLIP系ゼロショットでも足りるか', reg('Z'),
             f"T1誤許可（v3.5の規則）：本システム {zs['t1']['ours']['FA']}、SigLIP {zs['t1']['baseline']['FA']}" if zs else PEND],
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
             f"危険な配達 A {j['P2_no_extra_unsafe']['unsafe_A']}、J {j['P2_no_extra_unsafe']['unsafe_J']}" if j else PEND],
            ['V', 'モデルの予測は閉ループで当たるか（ランダムな変化）', reg('V'), v_result_text(jload('v_summary.json'))],
            ['W', '隠れた火の画像の検出、先行手法との比較', reg('W'), w_result_text(jload('w_summary.json'))],
            ['A', '信頼できない助言は確認を緩められるか（閉ループ）', reg('A'), a_result_text(jload('a_summary.json'))],
            ['S', '画像内の標識の文字で誤許可を起こせるか', reg('S'), s_result_text(jload('s_summary.json'))],
            ['L', '未知の配置24通りでも期待どおり動くか', reg('L'),
             (lambda pl: f"期待どおり {pl['expected_behaviour']}、危険な配達 {pl['unsafe_deliveries']}、主張 {'成立' if pl['claim_supported'] else '不成立'}")(jload('l_summary.json')['primary'])
             if jload('l_summary.json') else PEND],
            ['XD・X', '倉庫（4拠点）の画像と閉ループでも成り立つか', 'XD・X（草稿）', PEND_NOT_RUN],
            ['Q', '実物の写真（Commons 405枚）で物資の確認は通用するか', reg('Q'), PEND_NOT_RUN],
            ['B', '助言の信用枠は、毎回嘘をつく情報源の代償を閉ループで抑えるか（機構の確認）', reg('B'), PEND if jload('b_summary.json') else PEND_NOT_RUN],
            ['IF', '依頼文で、頼まれた物資をすり替えられるか（査読 R6 の P7）', reg('IF'), PEND if jload('if_summary.json') else PEND_NOT_RUN],
            ['K', '保証付きの閾値は既定の閾値より良いか', reg('K'),
             (f"T2の見逃し：既定 {kk['frozen']['heldout_miss']['k']}/{kk['frozen']['heldout_miss']['n']}、保証付き(α=0.05) "
              f"{kk['alphas']['0.05']['K_PAC']['heldout_miss']['k']}/{kk['frozen']['heldout_miss']['n']}、誤警報 "
              f"{kk['alphas']['0.05']['K_PAC']['heldout_false_alarm']['k']}/{kk['n_free']}") if kk else PEND]]
    return [KeepTogether([P('K. 事前登録した研究の一覧', 'h2'),
            P(advice_numbers.study_phrase() + 'を、結果を見る前に条件・基準・解析を <font name="IPAexG">experiments/PREREGISTRATION_<記号>.md</font> に固定して進めた（初期の評価Cは別に数える）。'
              '失敗した試行も台帳に残している。'
              + (' 「草稿」の研究（' + '・'.join(x for x in ('A', 'S', 'X', 'XD', 'Q', 'B', 'IF') if reg_label(x) != x) + '）は、統合ブランチを main に統合するときに登録され、それまで試行は一つも走らせない'
                 '（結果のある研究と同列の時系列監査はまだできない）。'
                 if any(reg_label(x) != x for x in ('A', 'S', 'X', 'XD', 'Q', 'B', 'IF')) else '')),
            table(rows, [20, 66, 24, 64])]), Spacer(1, 4)]


def sec_conformal():
    """4.8 study K (conformal threshold): alpha / tau / miss / false alarms, all read from k_summary.json."""
    k = jload('k_summary.json')
    if not k:
        return []
    fz = k['frozen']
    sf = k['small_fire_frac']
    r5, r10 = k['alphas']['0.05']['K_PAC'], k['alphas']['0.1']['K_PAC']
    cmp_ = lambda r: f"τ={r['tau']}：見逃し {r['heldout_miss']['k']}/{r['heldout_miss']['n']}・誤警報 {r['heldout_false_alarm']['k']}/{r['heldout_false_alarm']['n']}"
    return [P('I4. 閾値を保証付きで決める（K）：適合予測', 'h2'),
            P(f"火の見逃し率に統計的な上限（α）を保証するように閾値を開発データ（火 {k['n_cal']} 枚）から決める方法（適合予測）を試した"
              f"（<font name=\"IPAexG\">experiments/PREREGISTRATION_K.md</font>、保存済みスコアの再解析でGPUは使わない、δ={k['delta']}）。"
              f"未使用のT2（火 {k['n_fire']} 枚、火の無い必須許可 {k['n_free']} 枚）では、既定（τ={fz['tau']}）は見逃し {fz['heldout_miss']['k']}・誤警報 {fz['heldout_false_alarm']['k']}、"
              f"保証付き（α=0.05）{cmp_(r5)}、（α=0.10）{cmp_(r10)}で、保証付きの閾値は誤警報を増やすだけだった。"
              f"T2の火はやさしく（小さな火の割合：開発 {sf['cal'] * 100:.0f} %、T2 {sf['heldout'] * 100:.1f} %）、見逃しが既定でも0なので、"
              f"「保証が成り立った」ではなく「天井で差が出なかった」と読む。開発データでの既定の見逃しは {fz['cal_miss']['k']}/{fz['cal_miss']['n']}（{fz['cal_miss']['rate'] * 100:.1f} %）で、"
              'この見逃しの多さを指摘できる点では役に立つ。Kは、T2のスコアが既にある状態で登録した（スコアの再調整はしていない）。', 'small'),
            Spacer(1, 3)]


def sec_related():
    return [P('関連研究との違い', 'h2'),
            P('最も近い VAP-TAMP は、VLMに言い換えた yes/no を何度も尋ねて多数決し、その結果で計画を立て直す。本作品は、選択肢の次トークン確率、'
              '失敗は拒否か取り消しにしかならないAND条件、VLMが指令できない独立した速度ガード、事前登録した閉ループ監査（真値）が違う。'
              '事前知識を使う物体探索や半静的地図・長期シーングラフも過去の観測で探索を速くするが、検出を信じて確認の関門でのリスクを抑えない。'
              '本作品の記憶は、順序と慎重さを変えるだけで、確認の関門は変えない。', 'small'), Spacer(1, 3)]



def headline(D, E, V, after_fig=()):
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
        p1h, p3h = h['P1_efficiency_relocation_persist'], h['P3_no_extra_risk_vs_v36']
        pah = h['per_arm']
        rch = {a_: pah[a_]['by_transition']['relocation_change']['time_median_s'] for a_ in ('M0', 'M2')}
        h_res = (f"危険な配達：確認を省く素朴な記憶 {p2h['unsafe_M1']}/{p2h['n_pairs']} は省くことの代償を示し、実質の比較は記憶なし {p3h['unsafe_M0']}/{p3h['n_pairs']} 対 本方式 {p3h['unsafe_M2']}/{p3h['n_pairs']}（より危険ではない）。"
                 f"時間（中央値）：物資の入れ替わりが続く{p1h['n_pairs']}出動で {p1h['time_M0_median_s']:.0f} → {p1h['time_M2_median_s']:.0f} 秒、置き場所が戻る出動では {rch['M0']:.0f} → {rch['M2']:.0f} 秒と遅い（遠回りの代償）、全体 {pah['M0']['time_median_s']:.0f} → {pah['M2']['time_median_s']:.0f} 秒。"
                 f"速さ{ok_(p1h['supported'])}・安全{ok_(p2h['supported'])}・追加の危険なし{ok_(p3h['supported'])}で、全体の主張：<b>{ok_(h['headline_supported'])}</b>")
    else:
        h_res = PEND
    if j:
        pj = j['P2_no_extra_unsafe']
        j_res = (f"危険な配達 A {pj['unsafe_A']}、J {pj['unsafe_J']}、J の失敗 {j['P1_runs_on_one_v100']['failed_J']} 件。"
                 f"全体の主張：<b>{ok_(j['P1_runs_on_one_v100']['supported'] and pj['supported'])}</b>")
    else:
        j_res = PEND
    vs = jload('v_summary.json')
    v_res = v_result_text(vs)
    lsum = jload('l_summary.json')
    if lsum:
        pl = lsum['primary']
        l_res = (f"未知の配置24通りで期待どおり {pl['expected_behaviour']}、危険な配達 {pl['unsafe_deliveries']} 件。"
                 f"全体の主張：<b>{ok_(pl['claim_supported'])}</b>")
    else:
        l_res = PEND
    nf = gp['n_world_pairs_fire_perceivable'] if gp else None
    # page 1 = the graphical abstract (problem, three ideas, main results; regenerated by scripts/make_graphical_abstract.py),
    # then the submission-info table, then the plain-language glossary.  The prose summary lives in chapter 1 and 4.
    out = fig('graphical_abstract_ja.png', 174, '要約図：問題、3つの工夫、事前登録した主な結果（数値は結果ファイルから自動生成）。')
    out += list(after_fig)
    out += [Spacer(1, 3), P('<b>用語</b>：<b>誤許可</b>＝届けてはいけない場面で「届けてよい」と判断してしまうこと（ロボットを実際に動かす評価では<b>誤配達</b>。火のある拠点から届けてしまうことは<b>危険な配達</b>）。'
                            '<b>正しい許可</b>＝届けてよい場面で、正しく「よい」と判断できること。'
                            '<b>事前登録</b>＝結果を見る前に、条件と合格の基準を文書にして固定すること。'
                            '<b>閉ループ</b>＝AIの判断でロボットが実際に動くところまで含めた評価。'
                            '<b>p値</b>＝偶然でこうなる確率の目安で、0.05より小さければ偶然とは考えにくい。'
                            '<b>版名</b>＝改良段階（v3.6が提出版）。', 'small')]
    gloss, out = out, []
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
        rows.append(['<b>Z</b> CLIP系ゼロショットとの比較（T1、v3.5の規則 τ_h=0.05）',
                     f"誤許可：本システム {so['FA']}/{so['n_deny']}、SigLIP {ba['FA']}/{ba['n_deny']}、CLIP {cl['FA']}/{cl['n_deny']}",
                     f"CLIPは正しい許可 {cl['CA']}/{cl['n_allow']} で、ほぼ何も許可しない。SigLIPは誤許可が多い"])
    else:
        rows.append(['<b>Z</b> CLIP系ゼロショットとの比較', PEND, ''])
    if p:
        res = f"実写{p['n']}枚：検出 {p['recall']['k']}/{p['recall']['n']}、火の無い画像の誤警報 {p['false_alarm']['k']}/{p['false_alarm']['n']}"
        au = p_auroc()
        lim = (f'確率の順位づけは良く（AUROC {au:.2f}、登録外）、問題は閾値。' if au else '') + '安全側だが<b>止まりすぎる</b>（最大の限界）。現場ごとの較正が必要'
        if p2 and p2.get('chosen_test'):
            ct = p2['chosen_test']
            lim += f"。較正した追試P2：誤警報 {ct['false_alarm']['k']}/{ct['false_alarm']['n']}、登録した基準 {ok_(p2['claim_supported'])}"
        rows.append(['<b>P</b> 実写の火災画像', res, lim])
    else:
        rows.append(['<b>P</b> 実写の火災画像', PEND, ''])
    rows.append(['<b>H</b> 出動をまたぐ記憶', h_res, '素朴な記憶は比較用。世界の変化は台本どおり。記憶なしの1件は本方式なら止まった（1件の事例）' if h else '結果が出たら資料に反映する'])
    rows.append(['<b>V</b> ランダムな変化での予測検証', v_res, '' if vs else '事前登録済み（PREREGISTRATION_V.md）、結果はこれから'])
    ws = jload('w_summary.json')
    rows.append(['<b>W</b> 隠れた火の画像と先行手法との比較', w_result_text(ws), '' if ws else 'Vの後に登録（PREREGISTRATION_W.md）。正面のみ対 横から見直す、VAP-TAMP風・KnowNo風との比較'])
    rows.append(['<b>L</b> 未知の配置での一般化', l_res, '' if lsum else '事前登録済み（PREREGISTRATION_L.md）、結果はこれから'])
    rows.append(['<b>J</b> 2つのAIの閉ループ', j_res, '' if j else 'スモーク試験では V100 1台に載り、閉ループが完走した'])
    out += [Spacer(1, 4), table(rows, [42, 74, 58]), Spacer(1, 3),
            P('すべてシミュレーション上の評価で、実写で検証したのは火災判定（P）だけ。ロボットを動かす評価（E・G・H・J）は、実機でも実写でも未検証。'
              '各研究の条件・基準・解析は結果を見る前に <font name="IPAexG">experiments/PREREGISTRATION_*.md</font> に固定した。', 'small'),
            Spacer(1, 4)]
    return gloss, out


def judge_box(D, E, V, compact=False):
    """3-minute box on page 1: problem, what is new, three numbers in plain words (all read from result files).
    compact: three short lines under the graphical abstract (the figure already carries the numbers)."""
    if compact:
        lines = ['<b>問題</b>：在庫表と現物の食い違いや火災があると、指示どおり運ぶロボットは、誤った物資や危険な場所へ届けてしまう。',
                 '<b>解き方</b>：届ける前に拠点で止まり、ローカルのAIが<b>選択肢の確率</b>で現物と火・煙を確かめる。迷ったら止まる。'
                 '残る誤りは物資の陰の小さな火なので、<b>横へ0.4 m動いて</b>見直す。',
                 '<b>新しさ</b>：記憶・他のロボット・依頼文・在庫表は<b>「助言」</b>とし、確認の順番と慎重さを変えるだけで、確認は決して省けない。'
                 'どんな助言でも、危険な配達は確認自身の誤り以下に収まる。']
        sf, cf = advice_numbers.smt_facts(), advice_numbers.credit_facts()
        if sf:      # I-23 / I-24: what is new since the first version of this principle (numbers from the result files)
            lines.append(f"<b>新しい成果</b>：この保証を、実装そのものに対して<b>機械検証</b>した（z3 {sf['unsat']}件、突き合わせ {sf['cases']:,}件で不一致 {sf['disagreements']}、"
                         f"バグ{sf['mutants']}個を{sf['caught']}個とも検出）。「締めるだけ」は<b>必要十分</b>でもあり、"
                         + (f"<b>信用枠</b>で、毎回嘘をつく情報源の代償にも上限がつく（記述モデル：+{cf['liar_no']:.0f}秒 → +{cf['liar_yes']:.0f}秒）。" if cf else '')
                         + '閉ループの確認（研究B・IF）は' + ('結果あり。' if all(advice_numbers.pending_studies().values()) else '結果待ち。'))
        return [P(x, 'small') for x in lines] + [Spacer(1, 3)]
    h = jload('h_summary.json')
    items = ['<b>問題</b>：災害時の物資配達ロボットは、在庫表と現物の食い違い（水のはずが救急箱・空）や火災に出会う。指示どおり運ぶだけでは、誤った物資や危険な場所へ届けてしまう。',
             '<b>新しさ</b>：前回の出動の記憶は「どの拠点を先に見るか」を<b>提案するだけ</b>で、届けてよいかは必ず<b>その場のカメラ</b>で決める（記憶は提案、判断は目）。'
             '<b>三つの教訓</b>：①選択肢の確率で判断し、独立した速度ガードの後ろに置く。②残った失敗は視点の失敗で、物資の陰の小さな火は正面からは見えないが、<b>横へ動くと</b>見える。'
             '③記憶は「どこを、どれだけ慎重に」見るかを変えるが、「見るかどうか」は変えない。']
    nums = []
    if E:
        nums.append(f"<b>{E['ok']}/{E['n']}</b>：ランダムな{E['n']}世界で期待どおりに動き、誤った物資・火のある拠点への配達は {E['fa']} 件（シミュレーション上。60試行では誤配達率の95%区間の上限は6%）")
    if V:
        gp, gc = V['g']['primary'], V['g']['per_config']
        nums.append(f"<b>{gp['wrong_deliveries_B']}回 → {gp['wrong_deliveries_C']}回</b>：3視点のどれかで火が見えた{gp['n_world_pairs_fire_perceivable']}世界で、正面だけだと火のある拠点へ配達した回数 → 横から撮り直した後"
                    f"（火の無い世界での誤停止 {gc['C']['false_hazard_stops']}/{gc['C']['fire_free_trials']}。測っているのは「横から見る効果」）")
    if h:
        p1, p3 = h['P1_efficiency_relocation_persist'], h['P3_no_extra_risk_vs_v36']
        nums.append(f"<b>{p1['time_M0_median_s']:.0f}秒 → {p1['time_M2_median_s']:.0f}秒</b>：物資が移されたままの{p1['n_pairs']}出動（少数）の所要時間の中央値（記憶なし → 検証つき記憶）。"
                    f"危険な配達は {p3['unsafe_M0']}/{p3['n_pairs']} 対 {p3['unsafe_M2']}/{p3['n_pairs']}。物資が元に戻った出動では遠回りで遅くなる")
    out = [P(t, 'small') for t in items]
    if nums:
        out += [P('<b>3つの数字</b>（条件は結果を見る前に固定）', 'small')] + [P(f'{i}. {t}', 'small') for i, t in enumerate(nums, 1)]
    return out + [Spacer(1, 3)]


def sec_active(V):
    """4.1 look-around (I-14): the G table; the F / T2 detail is in the appendix."""
    if not V:
        return [P('D1. 横から見直す能動知覚', 'h2'), P(PEND)]
    f, g = V['f'], V['g']
    fp, gp, fc, gc = f['primary'], g['primary'], f['per_config'], g['per_config']
    fm = sorted(x['fire_pixels'] for x in f.get('trials', []) if x['config'] == 'B' and x['wrong_delivery'] and x.get('fire_pixels'))
    FPX = f"{fm[0]:,}〜{fm[-1]:,}画素" if fm else '小さく'
    out = [P('D1. 横から見直す能動知覚（I-14、評価F → G）', 'h2'),
           P(f"T1で残った弱点は、物資の陰に隠れた小さな火の見逃しである。問い方の改良と拡大切り出しを加えた評価F（対比較）でも、火があるのに配達した回数は"
             f" {fp['wrong_deliveries_A']}/{fp['n_world_pairs_fire_visible_both']} → {fp['wrong_deliveries_B']}/{fp['n_world_pairs_fire_visible_both']} 世界、{pexact(fp['mcnemar_p'])} で有意でなかった。"
             f"見逃した火は正面から{FPX}しか写らず、p(危険)が火の無い画像と重なるため、閾値の調整では分けられない。"
             '同じ火は左右0.4 mずらした視点では4,600〜22,000画素で見えた。そこで<b>VLMではなくロボットの視点を変える</b>：'
             '許可の直前に拠点の左右0.4 mへ移動して、照準・静止確認・撮り直し・判定をやり直し、どちらかで危険を見れば探索せずに止まる（横からの物資判定は使わない）。')]
    out += paper_fig('fig_lookaround', 88, '同じ小さな火を、正面（左）と左へ0.4 m動いた位置（右）から見た画像。正面では物資の陰で危険と判定されず（p=0.002）、横からは火が見えて止まる（p=0.82）。')
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
    out += paper_fig('fig_fire_size', 150, '左：見える火が小さいほど、VLMは危険と判定しにくい（横軸：火の画素数）。右：正面で見逃した火（青）は、横からだと大きく見える（縦軸）。')
    if V['miss']:
        m = V['miss'][0]
        out += [P(f"<b>唯一の見逃し</b>（{m['world']}）：火が正面から{m['fire_pixels_front']}画素（完全に隠れる）、横からも最大 {m['fire_pixels_best_side']:,} 画素と最小で、"
                  'p(危険)が閾値0.05に届かなかった。限界として明記する。', 'small')]
    return out + [Spacer(1, 3)]



def camera_table():
    r = jload('r_summary.json')
    if not r:
        return []
    cond = r['conditions']
    fams = []
    for c in cond:
        if c.rsplit('_', 1)[0] not in fams:
            fams.append(c.rsplit('_', 1)[0])
    rows = [['劣化', '誤許可（中／強）', '火の見逃し（中／強）', '正しい許可（中／強）', '品質ゲート棄却（中／強）']]
    for fm in fams:
        o = [cond[f'{fm}_{sv}'] for sv in ('M', 'S') if f'{fm}_{sv}' in cond]
        j2 = lambda g: '／'.join(g(x) for x in o)
        rows.append([R_FAM.get(fm, fm), j2(lambda x: f"{x['false_approvals']}/{r['n_deny']}"), j2(lambda x: f"{x['fire_missed']}/{r['n_visible_fire']}"),
                     j2(lambda x: f"{x['correct_approvals']}/{r['n_allow']}"), j2(lambda x: str(x['gate_rejected']))])
    return [table(rows, [28, 34, 38, 38, 36]), Spacer(1, 3)]



# ---------------------------------------------------------------------------------------------------------
# Main body (<= 7 pages): one story, the same chain as the paper "Advice May Only Tighten":
#   stops when unsure -> hidden fires dominate the error -> look again from the side -> untrusted inputs may only
#   reorder or tighten -> what stays outside the guarantee -> limits.  Plain Japanese, figures first; details in the appendix.
# ---------------------------------------------------------------------------------------------------------
def two_figs(items, width_mm):
    """Figures side by side, each (file name in docs/figures, caption[, width mm]); missing files are skipped silently."""
    from PIL import Image as PI
    cells, cols = [], []
    for it_ in items:
        name, cap = it_[0], it_[1]
        width_mm_i = it_[2] if len(it_) > 2 else width_mm
        path = FIG / name
        if not path.is_file():
            continue
        with PI.open(path) as im:
            w, h = im.size
        wpt = width_mm_i * mm
        cells.append([Image(str(path), width=wpt, height=wpt * h / w), P(cap, 'cap')])
        cols.append((width_mm_i + 4) * mm)
    if not cells:
        return []
    t = Table([[c[0] for c in cells], [c[1] for c in cells]], colWidths=cols)
    t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 1), ('RIGHTPADDING', (0, 0), (-1, -1), 1),
                           ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0), ('LEFTPADDING', (0, 1), (-1, 1), 6), ('RIGHTPADDING', (0, 1), (-1, 1), 6)]))
    return [KeepTogether([t])]


def findings_mutants():
    """(mutants of the I-19 rule, mutants of the 4-station extension) read from docs/FINDINGS.md rows 24 and 25; None if absent."""
    import re
    f = ROOT / 'docs/FINDINGS.md'
    if not f.is_file():
        return None
    rows = {}
    for ln in f.read_text(encoding='utf8').splitlines():
        m = re.match(r'\|\s*(\d+)\s*\|', ln)
        if m:
            rows[int(m.group(1))] = ln
    a = re.search(r'変異体\s*(\d+)\s*個', rows.get(24, ''))
    b = re.search(r'変異体\s*(\d+)\s*個', rows.get(25, ''))
    return (int(a.group(1)), int(b.group(1))) if a and b else None


def n_prereg():
    """Number of studies (the one definition: advice_numbers.study_counts; falls back to the registration files without C)."""
    c = advice_numbers.study_counts()
    return c['n'] if c else len(list((ROOT / 'experiments').glob('PREREGISTRATION_*.md'))) - 1


def smt_line():
    """'machine-checked on the implementation' in one clause (I-23); None when the result file is missing."""
    f = advice_numbers.smt_facts()
    if not f:
        return None
    return (f"z3 で実装そのものを検証（{f['queries']}件中{f['unsat']}件が反例なし）、モデルと実関数の突き合わせ {f['cases']:,}件で不一致 {f['disagreements']}、"
            f"わざと入れた緩めるバグ {f['mutants']}個を {f['caught']}個とも検出")


def pend_ifb():
    p = advice_numbers.pending_studies()
    return '・'.join(f'研究{k}' + ('（結果あり）' if p[k] else '') for k in ('B', 'IF'))


def new_results_main():
    """Chapter 4: the three new results of the advice principle (I-23 machine check, necessity, I-24 credit) and the pending studies B and IF."""
    f, c, p = advice_numbers.smt_facts(), advice_numbers.credit_facts(), advice_numbers.pending_studies()
    rows = [['新しい成果', '内容と数値', '位置づけ']]
    if f:
        rows.append(['<b>① 機械検証</b>（I-23）', f"命題2を<b>実装そのものに対して</b> z3 で検証。{f['queries']}件の問いのうち{f['unsat']}件が「反例なし」（助言の長さも画像も任意）。"
                     f"モデルと実関数を同じ{f['cases']:,}件の入力で突き合わせて不一致 <b>{f['disagreements']}</b>、わざと入れた緩めるバグ{f['mutants']}個を<b>{f['caught']}個とも</b>検出。",
                     '対象は転記したモデルとコード。仕様の正しさ・乗っ取られたノードは対象外（付録C）'])
    ex = f"（z3 の反例：危険な配達の率 {f['unsafe_rate']} が予算 {f['eps_any']} を超える）" if f and f.get('unsafe_rate') is not None else ''
    rows.append(['<b>② 必要十分</b>（補足S10）', '「安全だと証明できるフレームは無い」前提のもとで、助言の窓口が<b>締めるだけであること</b>と、<b>どんな助言者に対しても誤許可の予算が守られること</b>は同値。'
                 '緩める窓口には、予算を超える世界と助言者が必ずある' + ex + '。確認を省く素朴な方式・フィルタ方式には、この上限が無い。',
                 '前提：証明書なし、許可は配送につながる'])
    if c:
        rows.append(['<b>③ 信用枠</b>（I-24、命題3）', f"情報源ごとの信用で、助言を<b>捨てるだけ</b>（安全は変わらない）。毎回嘘をつく・危険を連打する情報源の代償に、何回出動しても上限がつく：場所の無駄な訪問は {c['c_loc']:g} + {c['rho_shadow']:g}×出動数 以下、誤った停止は {c['c_haz']:g} + {c['rho']:g}×出動数 以下。"
                     f"{c['missions']}出動のモデル：嘘つきの余分な時間 <b>+{c['liar_no']:.0f} → +{c['liar_yes']:.0f} 秒</b>、実写の誤警報率での危険の連打による誤停止 <b>{c['flood_no']} → {c['flood_yes']} 回</b>、正直な情報源の{c['honest_no']:.0f}秒の短縮は変わらない。",
                     '合成した結果の記述モデル（事前登録なし、閉ループは未確認）。報告書は不採用の助言と理由を書く'])
    done_ = [k for k in ('B', 'IF') if p[k]]
    rows.append(['<b>研究B・IF</b>', '<b>B</b>：信用枠の閉ループ確認（毎回嘘をつく情報源の系列、48試行、予測は決定的）。<b>IF</b>：依頼文で依頼物資を書き換えられるか（72文）。',
                 '事前登録済み、' + ('B・IFとも結果あり' if len(done_) == 2 else '・'.join(k for k in ('B', 'IF') if not p[k]) + 'は<b>結果待ち（未実行）</b>')])
    out = [P('<b>この保証の新しい成果</b>（機械検証・必要十分・期間の上限）', 'small'), Spacer(1, 2), table(rows, [26, 112, 36])]
    if c:
        out += fig('advice_credit.png', 128, f"図 助言の信用枠の記述モデル（{c['missions']}出動）：嘘つき・危険の連打の代償は上限で止まり、正直な情報源は何も失わない。")
    return out


def story_chain(D, E, V, T):
    """The five links of the argument as one table (title row, body row); numbers come from result files, pending studies say so."""
    t1 = T['t1']['models']['Qwen3.5-9B']['rules']['full'] if T else None
    gp = V['g']['primary'] if V else None
    h = jload('h_summary.json')
    hp = h['P3_no_extra_risk_vs_v36'] if h else None
    sj = jload('s_summary.json')
    pend_va = '' if (jload('a_summary.json') and jload('v_summary.json')) else '<br/>評価V：実行中、評価A：未実行'
    g = lambda x: f"<br/><font color='#52514e'>{x}</font>"
    heads = ['① 迷ったら止まる', '② 誤りの正体', '③ 横から見直す', '④ 助言は締めるだけ', '⑤ 保証の外']
    bodies = [
        'AIが選択肢の確率で現物と火を確かめ、1つでも怪しければ拒否する。' + (g(f"ランダムな世界の評価：誤配達 {E['fa']}/{E['n']}") if E else ''),
        '残る誤りは、物資の陰に隠れた小さな火。正面からは写らない。' + (g(f"未使用の画像：誤許可 {t1['false_approvals']}/{t1['n_deny']}は全てこの型") if t1 else ''),
        '許可の前に0.4 m横へ動いて撮り直す。' + (g(f"新しい世界での比較：火の見逃し配達 {gp['wrong_deliveries_B']}→{gp['wrong_deliveries_C']}/{gp['n_world_pairs_fire_perceivable']}") if gp else ''),
        '記憶・他のロボット・依頼文・在庫表は「助言」。確認の順番と慎重さを変えるだけで、省けない。'
        + (g(f"記憶の評価：危険な配達 記憶なし{hp['unsafe_M0']}→本方式{hp['unsafe_M2']}/{hp['n_pairs']}" + pend_va) if hp else '')
        + (g(f"実装をz3で機械検証（{advice_numbers.smt_facts()['unsat']}件）。信用枠で代償に上限") if advice_numbers.smt_facts() else ''),
        '画像に写った文字と、現実・倉庫との差は保証できない。測って報告する。' + ('' if sj else g('画像内の文字・倉庫の評価：未実行')),
    ]
    sty = ParagraphStyle('chain', parent=S['cell'], fontSize=7.9, leading=11)
    hst = ParagraphStyle('chainh', parent=S['cellh'], fontSize=8.6, alignment=TA_CENTER)
    arrow = ParagraphStyle('arr', parent=S['cell'], fontName='IPAexG', fontSize=13, alignment=TA_CENTER, textColor=ACC)
    w = [31.6 * mm, 4.2 * mm] * 4 + [31.6 * mm]
    r0, r1 = [], []
    for i in range(5):
        r0.append(Paragraph(heads[i], hst)); r1.append(Paragraph(bodies[i], sty))
        if i < 4:
            r0.append(Paragraph('→', arrow)); r1.append('')
    t_ = Table([r0, r1], colWidths=w)
    dark, soft = colors.HexColor('#2d3748'), colors.HexColor('#fdf0ea')
    st = [('VALIGN', (0, 0), (-1, -1), 'TOP'), ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'), ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3),
          ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]
    for i in range(5):
        c = i * 2
        st += [('BACKGROUND', (c, 0), (c, 0), ACC if i == 3 else (MUT if i == 4 else dark)), ('BOX', (c, 0), (c, 1), 1.6 if i == 3 else 0.6, ACC if i == 3 else LINE)]
        if i in (3,):
            st.append(('BACKGROUND', (c, 1), (c, 1), soft))
        if i == 4:
            st.append(('BACKGROUND', (c, 1), (c, 1), SOFT))
    t_.setStyle(TableStyle(st))
    return [t_, Spacer(1, 2), P('橙色の枠が中心（保証の内側）、灰色の枠は保証の外側。「実行中」の研究は、結果が出てから数値を入れる。', 'cap')]


def story_criteria(E, V):
    mut = findings_mutants()
    jw = jload('j_summary.json')
    p2 = jload('p2_summary.json')
    x_tech = (f"独立に書いた参照実装と変異テストで、助言の規則のバグ5件・監査の数え間違い1件を発見して修正（変異体{mut[0]}個・{mut[1]}個はすべて検出、FINDINGS #24・#25）" if mut
              else '独立に書いた参照実装と変異テストで、助言の規則と監査のバグを発見して修正（FINDINGS #24・#25）')
    p2txt = (f"現場写真での閾値の較正（未使用の写真で検出 {p2['chosen_test']['recall']['k']}/{p2['chosen_test']['recall']['n']}、"
             f"誤警報 {p2['chosen_test']['false_alarm']['k']}/{p2['chosen_test']['false_alarm']['n']}）") if p2 and p2.get('chosen_test') else '現場写真での閾値の較正（P2）'
    rows = [['審査基準', '本作品での取り組み', '見る場所'],
            ['創造性', '<b>「助言は締めるだけ」</b>：記憶・他のロボット・依頼文・在庫表を「助言」とし、確認の順番と慎重さしか変えられない設計。どんな助言でも危険な配達は確認自身の誤り以下。'
                       'もう一つは、見逃しを<b>賢くするのでなく動いて減らす</b>「横から見直す」。'
                       '助言の窓口が締めるだけであることは、安全の予算を守るための<b>必要十分条件</b>で、素朴な方式・フィルタ方式には上限が無い。', '3・4章'],
            ['技術力', f'上の原理の<b>証明</b>（付録C）と、その<b>機械検証</b>（' + (smt_line() or 'z3') + '）、事前登録した' + advice_numbers.study_phrase() + '（失敗した主張も公開）、真値による独立監査、' + x_tech + f'。実際に動かして見つけた問題 {count_tests.n_findings()}件。', '2–4章、付録C・M'],
            ['実用性', '現場導入の手順書（半日、docs/DEPLOYMENT.md）、' + p2txt + '、運用者向けの<b>報告書の自動生成</b>（統合済み）、'
                       '実写に近い倉庫への改善（評価は実行予定）。オフライン・単一GPU。', '5章'],
            ['表現力', '日本語ナレーション付きの実レンダリング動画（倍速は画面に常時表示）、1ページ目の要約図、各アイデアに1枚の図。数値は結果ファイルから自動生成。', '1ページ目、7章']]
    return [P('審査基準との対応', 'h2'), table(rows, [18, 128, 28]), Spacer(1, 3)]


def story_gate(D, E, T, lsum):
    s = [P('2. 迷ったら止まる確認：土台', 'h1'),
         P('ロボットは依頼を受けると物資の拠点へ向かい、その場で止まってカメラで現物を確かめる。AIは文章を作らず、'
           '「台の上は 水／救急箱／なし」などの<b>選択肢の確率</b>を読む（質問は並べ替えて2回、火・煙の質問は1回）。'
           '全部がそろったときだけ避難所へ向かい、迷えば拒否する。物資が違えば別の拠点を探し、火なら探さずに止まる。'
           '動きの出力はAIではなく別プロセスの<b>速度ガード</b>だけが握り、成否はシミュレータの真値で第三者が再計算できる。')]
    s += two_figs([('architecture.png', '実行時の全体構成。推論はすべてローカルGPU（クラウドAPI不使用）。'),
                   ('hero_gazebo.png', 'Gazeboの実レンダリング（俯瞰）。ロボットが拠点の現物をカメラで確かめに行く。')], 80)
    r = []
    if E:
        nb = E['n'] - E['allow']
        r.append(f"<b>評価E</b>（毎回ランダムな世界、事前登録）：期待どおりの行動 <b>{E['ok']}/{E['n']}</b>、誤配達 <b>{E['fa']}</b>（95%区間 {pct_ci(E['ok'], E['n'])}）。"
                 f"確認せずに配達するロボットなら、同じ試行で {nb} 件を誤る。評価D（{D['n']}試行）は {D['correct']}/{D['n']}。" if D else
                 f"<b>評価E</b>：{E['ok']}/{E['n']}、誤配達 {E['fa']}。")
    if lsum:
        pl = lsum['primary']
        r.append(f"<b>評価L</b>（未知の配置24通り）：期待どおり {pl['expected_behaviour']}、危険な配達 {pl['unsafe_deliveries']} 件。")
    else:
        r.append('<b>評価L</b>（未知の配置24通り）：' + PEND_NOT_RUN + '。')
    it = (jload('intent_hybrid_selected_qwen35_9b_i35.json') or {}).get('summary')
    ai = ['<b>AIの使いどころ</b>：①依頼文の理解（ローカルLLM'
          + (f'、未知の言い換え60文で {it["correct"]}/60、危険な誤受理 {it["unsafe_accepts"]}' if it else '') + '）'
          '②カメラ画像での現物・火の確認（ローカルVLM Qwen3.5-9B）③判断の後に、見たものを日本語1文で現場の人へ報告。']
    return s + bullets(r + ai) + [Spacer(1, 3)]


def story_look(V, T, ws):
    s = [P('3. 残る誤りは「隠れた火」：賢くせず、横から見直す', 'h1')]
    if T:
        m9 = T['t1']['models']['Qwen3.5-9B']['rules']['full']
        s.append(P(f"未使用の画像{T['t1']['models']['Qwen3.5-9B']['n_images']}枚（T1）で、拒否すべき火のない画像 {T['n_neg']} 枚の誤許可は {T['fa_neg']} 件だった。"
                   f"誤許可は {m9['false_approvals']}/{m9['n_deny']} 件あり、すべて「物資が正しく、火が物資の陰で一部しか見えない」画像だった"
                   f"（事前登録の基準は「95%区間の上限が2%未満」で、上限は {wilson(m9['false_approvals'], m9['n_deny'])[1] * 100:.1f} %、<b>{'成立' if wilson(m9['false_approvals'], m9['n_deny'])[1] < 0.02 else '不成立'}</b>）。"
                   '質問の工夫や拡大切り出しでも、この火は区別できなかった（評価F、付録G）。写っていない火は、AIをどれだけ賢くしても見えない。'))
    s += paper_fig('fig_lookaround', 98, '同じ小さな火を、正面（左）と左へ0.4 m動いた位置（右）から見た画像。正面では物資の陰で拒否されず、横からは火が見えて止まる。')
    if V:
        g = V['g']
        gp, gc = g['primary'], g['per_config']
        rows = [['火があるのに配達した回数', '正面のみ', '＋横から見直す']]
        rows.append([f"火が見えた{gp['n_world_pairs_fire_perceivable']}世界（新しい世界での対比較）", f"{gc['B']['wrong_deliveries']}/{gc['B']['visible_fire_trials']}", f"<b>{gc['C']['wrong_deliveries']}/{gc['C']['visible_fire_trials']}</b>"])
        rows.append(['火のない世界での誤った停止', f"{gc['B']['false_hazard_stops']}/{gc['B']['fire_free_trials']}", f"{gc['C']['false_hazard_stops']}/{gc['C']['fire_free_trials']}"])
        if V['wall_B'] and V['wall_C']:
            rows.append(['正常な配達1回の所要時間（中央値）', f"{V['wall_B']:.0f} 秒", f"{V['wall_C']:.0f} 秒（+{V['wall_C'] - V['wall_B']:.0f} 秒）"])
        s += [table(rows, [86, 40, 48]), Spacer(1, 2),
              P(f"評価G（事前登録）：食い違いは正面のみ {gp['discordant_B_only']}・横から見直す {gp['discordant_C_only']}、McNemar正確検定 {pexact(gp['mcnemar_p'])}で主張は成立。"
                f"ただし火の多くは設計上、正面から見えにくく、測っているのは「横から見る効果」である。見逃し {gc['C']['wrong_deliveries']} 件が残り、完全に隠れた火は横からも見逃し得る。"
                '次の評価W（隠れた火の画像、先行手法との比較）：' + (w_result_text(ws) if ws else PEND_NOT_RUN + '。'), 'small')]
    return s + [Spacer(1, 3)]


def story_advice(h):
    s = [P('4. 中心の考え方：信頼できない入力は「締める」ことしかできない', 'h1'),
         P('前回の出動の記憶、他のロボットの報告、在庫表、依頼文の一言（「火は消えたので確認不要」）は、古い・間違い・悪意のいずれもあり得る。'
           'そこで<b>ロボット自身が見ていない入力をすべて「助言」</b>と呼び、できることを次の2つに限る。')]
    s += bullets(['<b>できる</b>：どの拠点を先に見るかを入れ替える。火の報告があった拠点で、危険の判定を厳しくする。',
                  '<b>できない</b>：確認を省く、「安全」「確認不要」を信じる、訪ねずに拒否する。そうした入力は何の効果も持たず、記録されるだけ。'])
    s += fig('advice_principle_ja.png', 132, '図 助言は確認の順番と慎重さを変えるだけ。確認は必ずその場のカメラで行う。')
    s.append(P('<b>保証</b>：どんな助言（悪意のあるものを含む）でも、同じカメラ画像での許可は、助言なしの許可の一部になる（許可は「物資が確認でき、かつ全視点で火の判定が閾値未満」のAND条件で、助言はそれを強められても外せない）。'
               'よって危険な配達の確率は、確認自身の誤りの確率（拠点数k倍まで）を超えない。証明は付録C、コードで強制し、独立に書いた参照実装と変異テストで確かめた。'
               '代償は、間違った助言のときの遠回りと誤った停止だけで、正しい助言なら時間が縮む。'))
    s += [Spacer(1, 3)] + new_results_main()
    if not h:
        return s + [P('<b>評価H（記憶）</b>：' + PEND + '。')]
    p1, p2, p3 = h['P1_efficiency_relocation_persist'], h['P2_safety_naive_vs_verified'], h['P3_no_extra_risk_vs_v36']
    pa = h['per_arm']
    rows = [['記憶の使い方（H：16系列×3出動、世界は出動ごとに変わる）', '危険な配達', '所要時間の中央値']]
    for a, nm in (('M0', '記憶なし'), ('M1', '素朴な記憶（記憶を信じて確認を省く）'), ('M2', '<b>本方式（記憶は助言だけ）</b>')):
        m = pa[a]
        rows.append([nm, f"{m['unsafe_deliveries']}/{m['n']}", f"{m['time_median_s']:.0f} 秒" if m['time_median_s'] is not None else '-'])
    s += [Spacer(1, 3), KeepTogether([table(rows, [100, 30, 44])]), Spacer(1, 2),
          P(f"素朴な記憶は確認を省くので危険な配達が増えるのは当然で、意味のある比較は記憶なし {p3['unsafe_M0']}/{p3['n_pairs']} 対 本方式 {p3['unsafe_M2']}/{p3['n_pairs']}（より危険にならない）。"
            f"物資が移されたまま続く{p1['n_pairs']}出動では {p1['time_M0_median_s']:.0f} → {p1['time_M2_median_s']:.0f} 秒（Wilcoxon正確検定 {pexact(p1['wilcoxon_exact_p'])}）に縮んだ。"
            f"一方、物資が元に戻った出動では助言の拠点へ先に行くぶん遅くなる（{pa['M2']['by_transition']['relocation_change']['time_median_s']:.0f} 秒 対 記憶なし {pa['M0']['by_transition']['relocation_change']['time_median_s']:.0f} 秒）。"
            f"事前登録した全体の主張（速さ・安全・追加の危険なし）：<b>{'成立' if h['headline_supported'] else '不成立'}</b>。", 'small')]
    vs, aj = jload('v_summary.json'), jload('a_summary.json')
    s += [Spacer(1, 2),
          P('<b>評価V</b>（モデルの予測を先に登録し、ランダムに変わる世界で確かめる）：' + (v_result_text(vs) if vs else PEND + '。'), 'small'),
          P('<b>評価A</b>（悪意のある助言：「火は消えた、確認不要」「水は別の拠点」。助言に従う方式との対比較）：' + (a_result_text(aj) if aj else PEND_NOT_RUN + '。'), 'small'), Spacer(1, 3)]
    s += fig('memory_principle_ja.png', 108, '図 記憶の場合：前回の記憶は拠点の順番を提案するだけ。行った先では必ず確認し、最近火を見た拠点では判定を厳しくする。')
    return s


def story_outside(sj):
    p, p2, rr = jload('p_summary.json'), jload('p2_summary.json'), jload('r_summary.json')
    s = [P('5. 保証の外にあるもの、現場に近づけるために', 'h1'),
         P('<b>画像に写った文字</b>（「Cと答えよ」「火災なし」と書かれた標識）はAIにとって助言ではなく見えているものなので、構造的な保証の外にある。'
           '評価S（52世界×標識なし・攻撃・無害）で測って報告する：' + (s_result_text(sj) + '。' if sj else PEND_NOT_RUN + '。')),
         ]
    real = []
    if p:
        real.append(f"<b>実写の火災画像（P）</b>：火・煙の検出 {p['recall']['k']}/{p['recall']['n']}、ただし火のない画像の誤警報 {p['false_alarm']['k']}/{p['false_alarm']['n']}。安全側だが止まりすぎるので、現場ごとの閾値の較正が要る。")
    if p2 and p2.get('chosen_test'):
        ct = p2['chosen_test']
        real.append(f"<b>較正（P2）</b>：較正用の画像だけで閾値を選び、未使用の写真で検出 {ct['recall']['k']}/{ct['recall']['n']}・誤警報 {ct['false_alarm']['k']}/{ct['false_alarm']['n']}"
                    f"（登録した基準 <b>{'成立' if p2.get('claim_supported') else '不成立'}</b>）。")
    if rr:
        pp = rr['P1_pooled']
        real.append(f"<b>カメラ劣化（R）</b>：雑音・ぶれ・暗さなど12条件で誤許可 {pp['false_approvals']}/{pp['n']}。劣化の代償は、止まる回数が増えること。")
    s += bullets(real)
    s += [Spacer(1, 2), P('<b>どの入力を、何が守っているか</b>', 'small'), table([
        ['入力', '守っているもの', '測っている研究'],
        ['記憶・他のロボット・在庫表', '構造的な保証（確認を省けない）', 'H、V、A'],
        ['依頼文の助言（「確認不要」など）', '構造的な保証。ただし助言の取り出しはAI', 'A'],
        ['依頼文の届け先', '選択式の解釈と規則で、曖昧なら動く前に拒否', 'A（オフライン）'],
        ['画像に写った文字', '<b>保証の外</b>（AIにとっては見えているもの）', 'S'],
        ['カメラの劣化・実写との差', '<b>保証の外</b>（止まる側に倒れるかを測る）', 'R、P、P2、倉庫X']],
        [58, 86, 30]), Spacer(1, 3)]
    s += two_figs([('depot_preview_sheet.jpg', 'シミュレーション環境の改善（評価は実行予定）：実写に近い倉庫（棚・ごみ箱・夕方の暗さ・煙）。4拠点、障害物あり。', 62),
                   ('operator_report_hidden_fire.png', '出動の記録から自動生成する現場報告書（写真・判断の理由・次にしてほしいこと）。例：物資の陰の火で停止。', 104)], 84)
    s.append(P('<b>導入の手順書</b>（docs/DEPLOYMENT.md）：差動二輪とGPU1台だけで、拠点座標の登録、現場写真約400枚での閾値の較正（30〜60分）、'
               '物資の見た目の確認、3場面×3回の試運転と監査、という半日の手順にまとめた。ネットワークは不要。'))
    return s + [Spacer(1, 3)]


STUDY_FILES = [('D', 'campaign_D_ledger.jsonl'), ('E', 'campaign_E_ledger.jsonl'), ('T1', 't1_summary.json'), ('T2', 't2_summary.json'), ('F', 'f_summary.json'), ('G', 'g_summary.json'), ('H', 'h_summary.json'),
               ('J', 'j_summary.json'), ('K', 'k_summary.json'), ('P', 'p_summary.json'), ('P2', 'p2_summary.json'), ('R', 'r_summary.json'),
               ('Z', 'z_summary.json'), ('L', 'l_summary.json'), ('V', 'v_summary.json'), ('W', 'w_summary.json'), ('A', 'a_summary.json'),
               ('S', 's_summary.json'), ('X', 'x_summary.json'), ('XD', 'xd_summary.json'), ('Q', 'q_summary.json'),
               ('IF', 'if_summary.json'), ('B', 'b_summary.json')]


def story_limits(D, E, V, SP):
    j, t1 = jload('j_summary.json'), jload('t1_summary.json')
    gp = V['g'] if V else None
    fp = V['f']['primary'] if V else None
    s = [P('6. うまくいかなかったこと・限界', 'h1')]
    done = [k for k, f in STUDY_FILES if (RES / f).is_file()]
    todo = [k for k, f in STUDY_FILES if not (RES / f).is_file()]
    running = [k for k in todo if k == 'V']
    queued = [k for k in todo if k not in running]
    s.append(P('<b>研究の状況</b>（事前登録した研究。結果ファイルがあるものだけ数値を載せている）：<b>結果あり</b> ' + '・'.join(done)
               + ('、<b>実行中</b> ' + '・'.join(running) if running else '') + '、<b>未実行（実行待ち）</b> ' + ('・'.join(queued) or 'なし')
               + '。', 'small'))
    items = []
    if t1:
        m = t1['models']['Qwen3.5-9B']['rules']['full']
        items.append(f"T1の基準（誤許可の95%区間の上限が2%未満）は{'成立' if wilson(m['false_approvals'], m['n_deny'])[1] < 0.02 else '不成立'}（{m['false_approvals']}/{m['n_deny']}、上限 {wilson(m['false_approvals'], m['n_deny'])[1] * 100:.1f} %）。評価Fの問い方の改良も有意でなく（{pexact(fp['mcnemar_p'])}）、この2つが「横から見直す」に進むきっかけになった。" if fp else
                     f"T1の基準（誤許可の95%区間の上限が2%未満）は{'成立' if wilson(m['false_approvals'], m['n_deny'])[1] < 0.02 else '不成立'}（{m['false_approvals']}/{m['n_deny']}）。")
    if j:
        items.append(f"<b>2つのAIで確認する案（J）は採用しなかった</b>：危険な配達は1つのAI {j['P2_no_extra_unsafe']['unsafe_A']}、2つ {j['P2_no_extra_unsafe']['unsafe_J']}で、登録した基準（追加の危険なし）は"
                     f"{'成立' if j['P2_no_extra_unsafe']['supported'] else '不成立'}。2つのAIは同じ系統で独立ではない。")
    items += ['保証は<b>相対的</b>：助言は確認自身の誤りを超えて危険を増やさないが、その誤りは0ではない。助言で先に向かわされた拠点が本当に燃えているときの接近は、保証の範囲外。',
              '<b>すべてシミュレーション</b>（実機なし）。物資の把持・運搬は未実装。実写で検証したのは火災判定（P）だけで、閾値は現場ごとに較正が要る。',
              '信用枠（I-24）の数値は<b>合成した結果の記述モデル</b>で、閉ループの確認（研究B）は' + ('結果あり。' if advice_numbers.pending_studies()['B'] else '結果待ち。')
              + '機械検証（I-23）は転記したモデルとコードが対象で、同じ筆者による転記と z3・CPython を信頼している。第三者による再現はまだ無い。',
              '閉ループの評価は8〜16組と少なく、記憶の評価Hは世界の変化が台本どおり（ランダムな変化は評価Vで確かめる）。']
    s += bullets(items)
    s += [P('7. 動画と再現', 'h1')]
    chap = ROOT / 'docs/video_chapters.json'
    if chap.is_file():
        ch = json.loads(chap.read_text(encoding='utf8'))
        mmss = lambda x: f'{int(x // 60)}:{int(x % 60):02d}'
        s += [P(f"動画は全 {mmss(round(ch[-1]['end_s']))}。映像はすべてGazeboの実レンダリング（模式図・モックなし）で、字幕・確率バー・軌跡・ロボットの報告文はその試行のログから自動合成。"
                f"<b>{SP}</b>で、速度は画面左上に常時表示している（構成は付録N）。")]
    s += fig('video_frame_decision.png', 74, '動画の一場面（物資の取り違え）：拠点Wで救急箱を確認して拒否し、もう一方の拠点を確認しに向かう。下段はロボットの日本語報告。')
    s += [P('再現：<font name="IPAexG">bash docker/build.sh</font> → <font name="IPAexG">bash docker/run.sh python3 scripts/run_campaign.py --protocol experiments/campaign_e_protocol.json</font>。'
            '設計判断は docs/DESIGN_DECISIONS.md。本資料・動画・コードに氏名・所属・メールアドレス等の個人情報は含めていない。', 'small')]
    return s


def glossary():
    return [P('用語集（本文で使わなかった記号・略号）', 'h2'),
            P('<b>誤許可</b>＝届けてはいけない場面で「届けてよい」と判断すること（ロボットを動かす評価では誤配達、火のある拠点から届けるのは危険な配達）。'
              '<b>正しい許可</b>＝届けてよい場面で、よいと判断できること。<b>事前登録</b>＝結果を見る前に、条件と合格の基準を文書にして固定すること。'
              '<b>閉ループ</b>＝AIの判断でロボットが実際に動くところまで含めた評価。<b>p値</b>＝偶然でこうなる確率の目安（0.05未満なら偶然とは考えにくい）。'
              '<b>Wilson区間</b>＝割合の95%の不確かさの幅。<b>McNemar検定</b>＝同じ世界を2方式で比べるときの検定。'
              '<b>ε（イプシロン）</b>＝確認自身の誤りの確率（本文の「確認自身の誤り」）。<b>τ_s・τ_h</b>＝物資・火の判定の閾値（既定 0.50・0.05、記憶で警戒した拠点は τ_h=0.01）。'
              '<b>v3.x</b>＝改良段階の版名（v3.6が提出版、横から見直しを含む）。<b>M0・M1・M2</b>＝記憶なし・素朴な記憶・本方式（記憶は助言だけ）。'
              '<b>h36・tiles</b>＝小さな火を明示した火の質問と拡大切り出し。<b>I-xx・D・E・F・G…</b>＝改善項目と事前登録した研究の記号（一覧は付録A・K）。', 'small'),
            Spacer(1, 4)]


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
                          title='RescueMind 説明資料', author=account, subject='Physical AI 応用1講座 最終課題')
    doc.addPageTemplates([PageTemplate('p', [Frame(18 * mm, 16 * mm, 174 * mm, 266 * mm, id='f')], onPage=on_page)])
    s = []
    s += [P('RescueMind：現地で「目で確かめてから」届ける災害物資ロボット', 'title'),
          P('最新のローカルVLM（Qwen3.5-9B / V100）× ROS 2 Jazzy × Gazebo Harmonic — 誤った物資を届けず、無ければ探し、危険なら止まる', 'sub')]
    info = [table([['項目', '内容'],
                 ['提出者', f'omnicampus アカウント：{account}'],
                 ['コード', repo_url],
                 ['動画', video_url or f'YouTube（タイトル：PAI最終課題_{account}）。{SP}（倍速は動画内に常時表示）。日本語ナレーション（VOICEVOX:四国めたん）'],
                 ['使用ツール', 'ROS 2 Jazzy / Gazebo Harmonic（Docker・EGLヘッドレス描画）/ PyTorch 2.8 + Transformers 5.20 / Tesla V100 32GB（sudo不要）'],
                 ['AIの活用', '① 自然言語指示の理解（ローカルLLM）② 搭載カメラ画像による現物・危険の確認（ローカルVLM、選択肢の確率で判断）③ 現場の人への日本語状況報告']],
                [28, 146]), Spacer(1, 4)]
    gloss, tab_main = headline(D, E, V, [])
    lsum, h, sj, ws = jload('l_summary.json'), jload('h_summary.json'), jload('s_summary.json'), jload('w_summary.json')
    # page 1 for a judge with five minutes: the figure first, then three short lines, then the submission table
    s += gloss[:1] + judge_box(D, E, V, compact=True) + info
    # pages 2-7: one story (the paper's chain), figures first; everything else is in the appendix
    s += [PageBreak(), P('ひとつの話：確認は「迷ったら止まる」、助言は「締めるだけ」', 'h1')] + story_chain(D, E, V, T) + [Spacer(1, 4)]
    s += story_criteria(E, V)
    s += [P('1. 課題と狙い', 'h1'),
          P('災害時の物資配送では、在庫表では水のはずの棚に救急箱が置かれていた・空だった、という<b>情報と現物の食い違い</b>や、<b>現場の火災</b>が起こる。'
            '指示どおり運ぶだけのロボットは、誤った物資や危険な場所へ届けてしまう。'
            '狙いは「AIに運ばせる」ことではなく、<b>AIの判断が間違っていればロボットが動かない</b>ことを、ログと物理シミュレータの真値で第三者が検証できる形にすること。'
            '物資の把持・運搬は行わない（現物確認と避難所への接近までを対象とする）。')]
    s += story_gate(D, E, T, lsum)
    s += story_look(V, T, ws)
    s += story_advice(h)
    s += story_outside(sj)
    s += story_limits(D, E, V, SP)
    M = s
    s = [PageBreak(), P('付録（詳細・証明・過去の評価・失敗の一覧）', 'h1'),
         P('本文で省いた記号の説明、表、証明、経緯。数値はすべて結果ファイルから生成している。'
           'すべてシミュレーション上の評価で、実写で検証したのは火災判定（P）だけであり、ロボットを動かす評価（E・G・H・A・V）は実機でも実写でも未検証。', 'small'),
         P('A. 用語集と、事前登録した主な結果', 'h2')] + glossary() + tab_main
    s += [P('B. ロボットの仕組みとAIの活用', 'h2')]
    # ---- 2. AI
    s += [P('B1. AIの活用と工夫', 'h3'),
          P('B1.1 現地確認：文章を生成させず「選択肢の確率」で判断する', 'h3'),
          P('VLMに選択式の質問（台の上は 水／救急箱／なし・その他）を2問、選択肢の順序を入れ替えて出し、回答文字の次トークン確率を1回の順伝播で読む。'
            '2問とも依頼物資が最大かつ確率0.50以上（τ_s）、火災・煙の Yes/No 質問が0.05未満（τ_h、v3.6。v3.4までは0.50）のときだけ許可する。'
            '引継ぎ版の「JSONを自由生成させる」方式は、実画像で96応答中21件が解析不能、空の台で「水がある」と幻覚した。'
            '選択肢方式では解析不能0となり、最初の開発画像48枚での正答は 37/48 → 48/48 になった。'),
          P('B1.2 モデルの調査と選定（最新世代への更新）', 'h3'),
          P('当初のQwen2.5-VL-3B（研究用途ライセンス）から、2025〜2026年の新世代（Qwen3-VL-8B、Qwen3.5-4B/9B、いずれもApache-2.0）を、V100（FP16のみ）上で'
            '<b>同じ開発データ・同じ手順</b>で公平に比較した（モデル非依存のプロンプト。比較表は付録H）。誤許可（視覚）と危険な誤受理（指示）がともに0だった唯一の新世代モデル'
            ' <b>Qwen3.5-9B（2026年2月）</b>を採用し、状況説明の正確さは 84 → 125/128 に向上した。')]
    s += [P('B1.3 自然言語指示の理解', 'h3'),
          P('同じローカルモデルに「物資は？」「届け先は？」の選択式2問を出して解釈し、明示的に別の避難所名がある指示は規則で必ず拒否する。'
            f"事前に固定した未知の言い換え60文（間接表現・否定・ひらがな・英語・無関係な依頼を含む）で、v3.3のTF-IDF {it['tfidf']['correct']}/60（危険な誤受理{it['tfidf']['unsafe_accepts']}）→ "
            f"<b>{it['q9b']['correct']}/60（危険な誤受理{it['q9b']['unsafe_accepts']}）</b>。" if it.get('q9b') and it.get('tfidf') else ''),
          P('B1.4 現場の人への状況報告', 'h3'),
          P('判断が確定した<b>後</b>に、VLMが日本語1文で「台の上に何があり、火や煙が見えるか」を報告する（例：「灰色の台には赤い十字の箱が置かれ、その横に炎と煙が立ち上っている。」）。'
            '判断ロジックは報告文を読まない（コードとテストで保証）。'),
          P('B1.5 開発データと評価データの分離（事前登録）', 'h3'),
          P('プロンプト・閾値・モデルは開発用データ（視点・照明・妨害物・火災をランダム化した画像176枚、指示文40文）だけで決め、評価前に条件を'
            '<font name="IPAexG">experiments/PREREGISTRATION_v34.md</font> に固定してから閉ループ評価を一度だけ実行した。失敗・中断した評価も台帳から削除していない。')]
    # ---- 3. robot
    s += [P('B2. ロボットの振る舞いと安全設計', 'h3')]
    s += bullets([
        '<b>現地確認</b>：到着後、拠点中心へカメラを向けて停止し、オドメトリで静止を確認してから新しいカメラ画像を2枚取得（画質・ROS時刻・シミュレーション時計を検査）。推論中・拒否後もゼロ速度と静止を監視し続ける。',
        '<b>回復探索</b>：依頼物資が無い／違う（危険なし）ときだけ、もう一方の拠点で同じ確認を1回行い、確認できたときだけ避難所Bへ。火災・確信度不足・2回目の拒否は停止して人に委ねる。',
        '<b>横から見直す（v3.6）</b>：正面の確認で許可したら、拠点の左右0.4 mへ移動して照準・静止確認・新しい画像の取得・判定をやり直す。どちらかで危険を見れば、探索せず危険で停止する（横からの物資判定は使わない）。物資の陰に隠れた火は、視点を変えると見える。',
        '<b>独立速度ガード</b>：ミッションは速度を要求するだけで、<font name="IPAexG">/cmd_vel</font> の唯一の発行者は別プロセスのガード。センサー鮮度・前方距離・速度上限を10 Hzで判定し異常はラッチ停止。DDSグラフで第2の発行者を検知したら非常停止。',
        '<b>真値による監査</b>：成功・停止は、独立レコーダが記録した <b>Gazebo真値姿勢</b>・ROS bag・時系列で判定する。回復探索は「最初の拒否の再計算 → 停止保持 → 探索 → 別拠点での新しい判断」の順序と画像ハッシュまで監査する。',
    ])
    s += [P('C. 助言の原理・証明・記憶（I-15、I-19）', 'h2'),
          P('<b>命題（助言は確認自身の誤りの範囲に収まる）</b>：拠点がk個のとき、どんな助言aでも、助言ありの許可は同じ画像での助言なしの許可に含まれる。'
            '（証明の骨子）許可は「物資の条件（閾値τ_sが大きいほど厳しい）」と「各視点の火の条件 p_h&lt;τ_h（τ_hが小さいほど厳しい）」の積で、助言の規則は τ_s を下げず τ_h を上げず、視点を減らさない。'
            'したがって助言ありの許可は助言なしの許可の部分集合になる。配達は許可の後にだけ起き、危険な配達は「ある拠点が拒否すべき状態なのに確認が許可した」ことを意味する。'
            'この事象は訪問の順番によらない（静的な世界では拠点ごとの画像は順番に依存しない）ので、順番を助言で選ばれても確率はその拠点の誤り確率ε_sで、和集合上界で拠点について足せばk倍までに収まる。'
            '範囲：保証は「相対的」で、確認自身のεは0ではない。助言が選ぶ「先に行く拠点」はさらされ方（本当に燃えている拠点への接近）を変え、配達の保証の外にある。'
            '<b>実装の確認</b>：規則はコード（advice.plan）で強制し、監査は保存した出力から再計算する。同じコードだけでは同じ見落としをするので、仕様から独立に書いた参照実装との差分テスト、'
            '変異テスト、助言ファイルへのファズも行った（付録M）。', 'small'), Spacer(1, 3)]
    s += sec_advice()
    s += sec_new_detail()
    s += sec_memory()
    s += [P('D. 横から見直す・小さな火への対策', 'h2')]
    s += sec_active(V)
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
        s += [P('E1. 事前登録した閉ループ評価D（v3.4）', 'h2'),
              P(f"試行ごとに Gazebo・ブリッジ・ガード・VLMを新規起動し、{D['n']}試行を事前に決めた順序で実行した。"
                f"期待どおりの行動 <b>{D['correct']}/{D['n']}</b>、誤許可 <b>{D['false_approvals']}</b> 件、"
                f"指示文の解釈 {D['intent_ok']}/{D['n']} 正解、判断遅延（静止画取得→判断）中央値 {D['lat_med']:.2f} 秒（最大 {D['lat_max']:.2f} 秒）。"
                + (f"VLM判断前のインフラ失敗による再試行 {D['retries']} 件（台帳に記録）。" if D['retries'] else '')
                + '同じワールドの反復であり、独立なシーン数ではない点に注意。'),
              table(rows, [34, 38, 12, 20, 70]), Spacer(1, 4)]
        s += [P(f"参考：v3.3（評価C、30試行、Qwen2.5-VL-3B、回復探索なし）は VLM判断 30/30・監査まで合格 {c_ok}/30。"
                '取り違えシーンでは「停止」が正解であり、正しい物資を届けることはできなかった。', 'small')]
    if E:
        s += [P('E2. 評価E（v3.5）：試行ごとにランダムな世界での事前登録評価', 'h2'),
              P(f"照明・小道具の配置・妨害物・火災をランダム化した世界を試行ごとに生成し、{E['n']}試行を事前に決めた順序で実行した"
                f"（<font name=\"IPAexG\">experiments/campaign_e_protocol.json</font>）。期待どおりの行動 <b>{E['ok']}/{E['n']}</b>、"
                f"誤許可 <b>{E['fa']}</b> 件、判断遅延の中央値 {E['lat_med']:.2f} 秒。"
                + (f"VLM判断前のインフラ失敗による再試行 {E['retries']} 件は台帳に記録（集計は最終試行のみ）。" if E['retries'] else '')
                + f"Wilson 95%区間は試行数が少ないため広い（全体の下限 {wilson(E['ok'], E['n'])[0] * 100:.0f} %）。")]
        rows = [['期待する行動', '条件ごとの 期待どおり／試行', '計', 'Wilson 95%区間']]
        for a in dict.fromkeys(a_ for a_, _ in E['keys']):
            ks = [c for a_, c in E['keys'] if a_ == a]
            k, n = sum(E['strata_ok'][(a, c)] for c in ks), sum(E['strata'][(a, c)] for c in ks)
            rows.append([EXP_E.get(a, a), '、'.join(f"{COND_E.get(c, c)} {E['strata_ok'][(a, c)]}/{E['strata'][(a, c)]}" for c in ks),
                         f'{k}/{n}', pct_ci(k, n)])
        rows.append(['<b>全体</b>', '', f"{E['ok']}/{E['n']}", pct_ci(E['ok'], E['n'])])
        nb = E['n'] - E['allow']
        rows.append(['反事実：盲目的に配達', '常に配達（確認しない）。誤行動 ' + str(nb), f"{E['allow']}/{E['n']}", pct_ci(E['allow'], E['n'])])
        rows.append(['反事実：回復探索なし', '最初の拒否で停止', f"{E['allow']}/{E['n']}", pct_ci(E['allow'], E['n'])])
        s += [table(rows, [38, 90, 18, 28]),
              P('反事実は同じ試行に対する計算上の基準で、実行したものではない。盲目的な配達は期待行動が配達（ALLOW）以外の全試行で誤り、'
                '回復探索なしは ALLOW の試行のみ成功とみなす保守的な定義（停止が正解の試行も成功に数えない）。', 'small'), Spacer(1, 4)]
    if T:
        t1 = T['t1']
        m9 = t1['models']['Qwen3.5-9B']
        s += [P(f"F. 未使用の画像{m9['n_images']}枚（T1）での評価", 'h2'),
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
        s += [P('G. 小さな火への対策の経過（評価Fと未使用のT2）', 'h2'),
              P('付録Fで分かった残る弱点（小さく写った・物資の陰の火の見逃し）に対し、<b>結果を見る前に条件を固定</b>して、段階的に2つの手（手1：問い方と拡大切り出し、手2：横から見直す）を打った。'
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
            "VLMの判定ではなく<b>ロボットの視点</b>を変える（付録D1）。"])
        s += [P('手2の評価G（対比較・事前登録）は本文3章に載せた。', 'small')]
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
        s += [P('H. モデルの調査と選定（最新世代への更新）', 'h2'),
              table([['モデル', '公開', '視覚判定（176枚）', '状況説明（128枚）', '指示理解（開発40文）', '1問の遅延']] +
                    [[r['model'], r['released'], r.get('vision_v35', '-'), r.get('explain', '-'), r.get('intent_dev_i35', '-'),
                      f"{r.get('latency_v35', 0):.2f} 秒"] for r in msel], [30, 18, 36, 26, 36, 22]), Spacer(1, 3)]
    s += sec_real()
    s += sec_camera()
    if rr_tab:
        s += [P('I2（表）. カメラ劣化（R）の全12条件', 'h2')] + rr_tab
    s += sec_clip()
    s += sec_conformal()
    s += sec_two_ai()
    s += sec_prereg(D, E)
    # ---- improvements
    s += [P('L. 改善の軌跡（v3.3 → v3.6）', 'h2'),
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
    # ---- 6. findings
    s += [P('M. 実際に動かして初めて分かった問題・独立検証（v3.2引継ぎ → v3.3）', 'h2'),
          P('引継ぎ時点のコードは、単体テストと模擬環境でしか確かめられておらず、実Gazebo・実ROS 2・実GPUでは一度も動いていなかった。'
            f'実際に動かして（v3.3〜v3.6の開発と評価の準備を含め）{count_tests.n_findings()}件の問題を見つけ、すべて再現→修正→確認した'
            f'（<font name="IPAexG">docs/FINDINGS.md</font>）。テスト関数も現在は{count_tests.n_tests()}件に増えた。代表例：')]
    s += bullets(['車輪軸の定義誤り：オドメトリ上は1.1 m前進、実際の車体は0.15 m（→ Gazebo真値による監査を新設）',
                  'Best Effort QoS で 0.9 MB の画像が102枚中10枚しか届かない（→ Reliable に統一）',
                  'gpu_lidar が自機のカメラマスト（visual）を障害物として検出（→ 可視性マスク）',
                  '評価の中断時に孤立したスタックが別試行に速度指令を出し続けた（→ 段階的停止と起動前の孤立スタック検出。Publisher監視は正しく検知していた）'])
    mu = findings_mutants()
    s += [P('独立検証：助言の規則（I-19）を仕様から独立に書き直した参照実装と、変異テスト・ファズで突き合わせて、実装のバグ5件を見つけて修正した'
            '（確認の不変条件の検査が慎重さの削除やNaNを見逃す、など。FINDINGS #24）。4拠点版の監査では、追加視点を「位置」でなく「枚数」で数える誤りも見つけた（#25）。'
            + (f'修正後は変異体 {mu[0]} 個・{mu[1]} 個がすべて検出される。' if mu else '')
            + '単体テストは実装と同じ考え方で書くため同じ見落としをする。安全に関わる規則は、別に書いた実装と変異テストで確かめる必要がある。', 'small')]
    chap = ROOT / 'docs/video_chapters.json'
    if chap.is_file():
        ch = json.loads(chap.read_text(encoding='utf8'))
        mmss = lambda x: f'{int(x // 60)}:{int(x % 60):02d}'
        s += [P('N. 提出動画の構成', 'h2'),
              table([['時刻', '内容', '備考']] + [[f"{mmss(c['start_s'])}–{mmss(c['end_s'])}", c['title'],
                     (c['speed'] or '') + (f"（run {c['run_id']}）" if c.get('run_id') else '')] for c in ch], [24, 90, 60])]
    s += fig('video_frame_decision.png', 75, '図2 動画の一場面（取り違え）：拠点Wで救急箱を確認して拒否し、もう一方の拠点を確認しに向かう。下段はロボットの日本語報告。')
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
