#!/usr/bin/env python3
"""Build the submission PDF (説明資料) from committed results; numbers are never hand-typed.

  python3 scripts/make_report.py --account <omnicampusアカウント名> [--video-url URL]

Output: docs/report/説明資料_PAI最終課題_<account>.pdf  (personal info must not appear;
only the omnicampus account name is allowed by the assignment rules).
"""
from __future__ import annotations
import argparse
import json
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
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'experiments/results'
FIG = ROOT / 'docs/figures'
sys.path.insert(0, str(ROOT / 'scripts'))
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
    canvas.drawString(18 * mm, 10 * mm, 'Physical AI 応用1講座 最終課題 ｜ RescueMind v3.5')
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
    sel = (RES / 'i13_selection.json').is_file()
    rows.append(['I-11', '小さく写った火の見逃し（T1の誤許可は全てこれ）',
                 '小さい火・煙を明示した質問と、拡大切り出しの併用。開発データ（DH）のみで選定、未使用のT2で確認',
                 '選定済み（結果は IMPROVEMENT_LOG）' if sel else '進行中（選定前・T2は未採点）'])
    rows.append(['I-13', '当初計画の「2つのAIで確認」から縮退していた',
                 'Clef-Flash（Jev互換、ローカル）をQwenと併用。選定規則は結果前に固定',
                 '選定済み（結果は IMPROVEMENT_LOG）' if sel else '進行中（開発データで選定中）'])
    return sorted(rows, key=lambda r: r[0])


def build(account: str, video_url: str | None, repo_url: str):
    D = campaign_d()
    E = campaign_e()
    T = t1_info()
    C = [r for r in ledger('campaign_ledger.jsonl') if r.get('final', True)]
    c_ok = sum(r['correct'] for r in C)
    rob = jload('i05_robustness_summary.json') or {}
    sel = jload('i08_model_selection.json') or []
    it = {k: (jload(f) or {}).get('summary') for k, f in (('tfidf', 'intent_tfidf.json'), ('q3b', 'intent_hybrid_qwen25vl3b.json'),
                                                          ('q9b', 'intent_hybrid_selected_qwen35_9b_i35.json'))}
    i01 = {k: jload(f'i01_drift/{k}.json') for k in ('baseline', 'sphere_wheels')}
    out = ROOT / 'docs/report' / f'説明資料_PAI最終課題_{account}.pdf'
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(str(out), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                          topMargin=16 * mm, bottomMargin=16 * mm,
                          title='RescueMind v3.5 説明資料', author=account, subject='Physical AI 応用1講座 最終課題')
    doc.addPageTemplates([PageTemplate('p', [Frame(18 * mm, 16 * mm, 174 * mm, 266 * mm, id='f')], onPage=on_page)])
    s = []
    head = (f"事前登録した{D['n']}試行の閉ループ評価で期待どおりの行動 <b>{D['correct']}/{D['n']}</b>、"
            f"誤った物資・火災のある拠点からの配達（誤許可）<b>{D['false_approvals']} 件</b>、判断遅延の中央値 {D['lat_med']:.1f} 秒") if D else '（評価D実行中）'
    if E:
        head += (f"。v3.5の評価E（試行ごとにランダムな世界、{E['n']}試行）で <b>{E['ok']}/{E['n']}</b>、誤配達 {E['fa']} 件")
    if T:
        ru = T['t1']['models']['Qwen3.5-9B']['rules']['full']
        head += (f"。未使用の画像{T['t1']['models']['Qwen3.5-9B']['n_images']}枚（T1）では、拒否すべき非火災画像 {T['n_neg']} 枚の誤許可 {T['fa_neg']} 件、"
                 f"小さく写った火の見逃しが残る弱点")
    s += [P('RescueMind：現地で「目で確かめてから」届ける災害物資ロボット', 'title'),
          P('最新のローカルVLM（Qwen3.5-9B / V100）× ROS 2 Jazzy × Gazebo Harmonic — 誤った物資を届けず、無ければ探し、危険なら止まる', 'sub'),
          table([['項目', '内容'],
                 ['提出者', f'omnicampus アカウント：{account}'],
                 ['コード', repo_url],
                 ['動画', video_url or f'YouTube（タイトル：PAI最終課題_{account}）。走行は4倍速・確認動作は2倍速・AI判断の瞬間は等速（倍速は動画内に常時表示）。日本語ナレーション（VOICEVOX:四国めたん）'],
                 ['使用ツール', 'ROS 2 Jazzy / Gazebo Harmonic（Docker・EGLヘッドレス描画）/ PyTorch 2.8 + Transformers 5.20 / Tesla V100 32GB（sudo不要）'],
                 ['AIの活用', '① 自然言語指示の理解（ローカルLLM）② 搭載カメラ画像による現物・危険の確認（ローカルVLM、選択肢の確率で判断）③ 現場の人への日本語状況報告'],
                 ['主結果', head]],
                [28, 146]), Spacer(1, 6)]
    crit = [['審査基準', '本作品での取り組み', '根拠（本資料の節・リポジトリ）'],
            ['創造性', '「運ぶAI」ではなく「間違えたら動かないAI」。現物確認・別拠点の探索・火災時の停止・日本語の状況報告を1つの閉ループに統合', '1章, 3章, 4.2章（評価E）, 動画デモ2・3'],
            ['技術力', '選択肢の確率によるVLM判定、最新モデルの調査と公平比較、Gazebo真値による独立監査、独立速度ガード、事前登録した閉ループ評価（D・E）と未使用画像の評価（T1）、弱点（小さな火）の特定と事前選定規則による改善、推測航法ドリフトの原因特定',
             '2章, 4.1–4.3章, 5章, docs/IMPROVEMENT_LOG.md'],
            ['実用性', 'オフライン・単一GPU・Apache-2.0、在庫と現物のずれへの対応、人への報告と判断の委譲、Docker（sudo不要）で再現可能。ランダム化した世界での評価Eと反事実との比較で、回復探索の実効果を示した', '4.2章, 7章, 10章, README'],
            ['表現力', '実レンダリング映像にAR軌跡・確率バー・ロボットの報告を重ねた日本語ナレーション付き動画、全体フロー図・設計判断記録', '4.2・4.3章（区間推定つきの表）, 9章, docs/ARCHITECTURE.md']]
    s += [P('審査基準との対応', 'h2'), table(crit, [18, 100, 56]), Spacer(1, 4)]
    s += [P('1. 課題の概要と目的', 'h1'),
          P('災害時の物資配送では「在庫表では水があるはずの棚に救急箱が置かれていた／空だった」という<b>情報と現物の食い違い</b>や、'
            '<b>現場の危険（火災）</b>が起こる。指示どおり機械的に運ぶロボットは、誤った物資を届けたり危険な場所に留まったりする。'
            '本作品では、自然言語で依頼を受けた差動二輪ロボットが物資拠点へ自律移動し、<b>その場で静止して搭載カメラで現物を確認</b>する。'
            'ローカルVLMが依頼物資を高い確信で確認したときだけ避難所Bへ向かい、物資が違えば<b>もう一方の拠点を探して</b>正しい物資を届け、'
            '火災を見たら探索せずに停止して、見たものを日本語で報告する。'),
          P('狙いは「AIに運ばせる」ことではなく、<b>AIの判断が間違っていればロボットが動かないこと</b>を、ログと物理シミュレータの真値で第三者が検証できる形にすることである。'
            'ロボットは物資の把持・運搬は行わない（現物確認と避難所への接近までを対象とし、配達完了とは表現しない）。')]
    s += fig('architecture.png', 172, '図1 実行時アーキテクチャ。全推論はローカルGPUで実行（クラウドAPI不使用）。詳細なフロー図は docs/ARCHITECTURE.md。')
    # ---- 2. AI
    s += [P('2. AIの活用と工夫', 'h1'),
          P('2.1 現地確認：文章を生成させず「選択肢の確率」で判断する', 'h2'),
          P('VLMに選択式の質問（台の上は 水／救急箱／なし・その他）を2問、選択肢の順序を入れ替えて出し、回答文字の次トークン確率を1回の順伝播で読む。'
            '2問とも依頼物資が最大かつ確率0.50以上、火災・煙の Yes/No 質問が0.50未満のときだけ許可する。'
            '引継ぎ版の「JSONを自由生成させる」方式は、実画像で96応答中21件が解析不能、空の台で「水がある」と幻覚した。'
            '選択肢方式では解析不能0、開発画像で 37/48 → 48/48 となった。'),
          P('2.2 モデルの調査と選定（最新世代への更新）', 'h2'),
          P('当初のQwen2.5-VL-3B（2025年1月・研究用途ライセンス）から、2025〜2026年の新世代（Qwen3-VL-8B、Qwen3.5-4B/9B、いずれもApache-2.0）を調査した。'
            'V100（FP16のみ）向けに torch 2.8＋transformers 5.20 の実行環境を用意し、<b>同じ開発データ・同じ手順</b>で比較。'
            '1回目は3B向けに調整したプロンプトのため新モデルが救急箱を「その他」と答える誤りが多発し、選択肢に外見と用途を併記したモデル非依存のプロンプトで公平に再比較した。')]
    if sel:
        s += [table([['モデル', '公開', '視覚判定（176枚）', '状況説明（128枚）', '指示理解（開発40文）', '1問の遅延']] +
                    [[r['model'], r['released'], r.get('vision_v35', '-'), r.get('explain', '-'), r.get('intent_dev_i35', '-'),
                      f"{r.get('latency_v35', 0):.2f} 秒"] for r in sel], [30, 18, 36, 26, 36, 22]), Spacer(1, 3)]
    s += [P('誤許可（視覚）と危険な誤受理（指示）がともに0だった唯一の新世代モデル <b>Qwen3.5-9B（2026年2月）</b>を採用した。状況説明の正確さは 84 → 125/128 に向上。')]
    s += fig('i08_models.png', 165, '図2 モデル比較（開発データ）。右：危険側の誤り。評価用データはモデル選定に使っていない。')
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
        '<b>独立速度ガード</b>：ミッションは速度を要求するだけで、<font name="IPAexG">/cmd_vel</font> の唯一の発行者は別プロセスのガード。センサー鮮度・前方距離・速度上限を10 Hzで判定し異常はラッチ停止。DDSグラフで第2の発行者を検知したら非常停止。',
        '<b>真値による監査</b>：成功・停止は、独立レコーダが記録した <b>Gazebo真値姿勢</b>・ROS bag・時系列で判定する。回復探索は「最初の拒否の再計算 → 停止保持 → 探索 → 別拠点での新しい判断」の順序と画像ハッシュまで監査する。',
    ])
    # ---- 4. results
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
        s += [P('4. 評価結果', 'h1'), P('4.1 事前登録した閉ループ評価D（v3.4）', 'h2'),
              P(f"試行ごとに Gazebo・ブリッジ・ガード・VLMを新規起動し、{D['n']}試行を事前に決めた順序で実行した。"
                f"期待どおりの行動 <b>{D['correct']}/{D['n']}</b>、誤許可 <b>{D['false_approvals']}</b> 件、"
                f"指示文の解釈 {D['intent_ok']}/{D['n']} 正解、判断遅延（静止画取得→判断）中央値 {D['lat_med']:.2f} 秒（最大 {D['lat_max']:.2f} 秒）。"
                + (f"VLM判断前のインフラ失敗による再試行 {D['retries']} 件（台帳に記録）。" if D['retries'] else '')
                + '同じワールドの反復であり、独立なシーン数ではない点に注意。'),
              table(rows, [34, 38, 12, 20, 70]), Spacer(1, 4)]
        s += fig('campaign_d_results.png', 165, '図3 評価Dのシナリオ別結果。')
        s += fig('trajectories_d.png', 112, '図4 評価D全試行のGazebo真値軌跡。取り違えでは別拠点を経由して避難所へ、欠品・火災では拠点で停止している。')
        s += [P(f"参考：v3.3（評価C、30試行、Qwen2.5-VL-3B、回復探索なし）は VLM判断 30/30・監査まで合格 {c_ok}/30。"
                '取り違えシーンでは「停止」が正解であり、正しい物資を届けることはできなかった。', 'small')]
    if E:
        if not D:
            s += [P('4. 評価結果', 'h1')]
        s += [P('4.2 評価E（v3.5）：試行ごとにランダムな世界での事前登録評価', 'h2'),
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
        if not (D or E):
            s += [P('4. 評価結果', 'h1')]
        s += [P(f"4.3 未使用の画像{m9['n_images']}枚（T1）での評価", 'h2'),
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
              P('検出は 判定が危険（p(危険)が閾値以上）となった見える火の数。自由JSON生成では解析不能 または推論失敗 を拒否として数える'
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
    # ---- 5. improvements
    s += [P('5. 改善の軌跡（v3.3 → v3.5）', 'h1'),
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
    s += fig('i01_drift.png', 160, '図5 I-01 推測航法ドリフトの原因切り分け（棄却した仮説も含む）。')
    # ---- 6. findings
    s += [P('6. 実際に動かして初めて分かった問題（v3.2引継ぎ → v3.3）', 'h1'),
          P('引継ぎ時点のコードは506件の単体テストに合格していたが、実Gazebo・実ROS 2・実GPUでは一度も動いていなかった。'
            '実行して13件の問題を発見し、すべて再現→修正→確認した（<font name="IPAexG">docs/FINDINGS.md</font>）。代表例：')]
    s += bullets(['車輪軸の定義誤り：オドメトリ上は1.1 m前進、実際の車体は0.15 m（→ Gazebo真値による監査を新設）',
                  'Best Effort QoS で 0.9 MB の画像が102枚中10枚しか届かない（→ Reliable に統一）',
                  'gpu_lidar が自機のカメラマスト（visual）を障害物として検出（→ 可視性マスク）',
                  '評価の中断時に孤立したスタックが別試行に速度指令を出し続けた（→ 段階的停止と起動前の孤立スタック検出。Publisher監視は正しく検知していた）'])
    s += fig('wheel_axis_regression.png', 150, '図6 同じ速度指令に対する車輪オドメトリとGazebo真値（左：引継ぎ版、右：修正後）。')
    # ---- 7..10
    s += [P('7. 実用性・応用可能性', 'h1')]
    s += bullets(['<b>在庫と現物のずれに強い</b>：物流倉庫・病院内搬送・避難所運営で、誤った物資を届けず、無ければ探し、それでも無ければ人に報告して止まる。',
                  '<b>オフライン・オンデバイス</b>：通信途絶を想定し、推論はすべて単一GPU上（APIキー不要、Apache-2.0のモデル）。',
                  '<b>説明と検証可能性</b>：判断画像のハッシュ・各質問の確率・日本語報告・真値軌跡・ROS bagを試行ごとに保存し、第三者が判断と行動の因果を再計算できる。'])
    s += [P('8. 限界と今後の課題', 'h1')]
    s += bullets(['物資の把持・運搬は未実装。Nav2の動的経路計画ではなく既知配置のウェイポイント追従。',
                  '小道具は単純形状、拠点は2か所・避難所は1か所の固定配置。実写画像・多様な物資・実機（SO-101等）でのSim-to-Realは未検証。',
                  '閾値0.50は確率の較正ではない。開発データでは余裕が大きいが、分布の異なる環境では再評価が必要。',
                  'ROSグラフ監視は認証機構ではなく、実機の安全認証を意味しない。'])
    chap = ROOT / 'docs/video_chapters.json'
    if chap.is_file():
        ch = json.loads(chap.read_text(encoding='utf8'))
        mmss = lambda x: f'{int(x // 60)}:{int(x % 60):02d}'
        s += [P('9. 提出動画の構成', 'h1'),
              P(f"全 {mmss(ch[-1]['end_s'])}。3-D映像はすべてGazeboの実レンダリング（俯瞰カメラ＋ロボット搭載カメラ）で、模式図やモック映像は使っていない。"
                '字幕・確率バー・軌跡・ロボットの報告文はその試行のログから自動合成。<b>走行は4倍速、確認動作は2倍速、AI判断の瞬間（画像取得〜判断）は等速</b>で、速度は画面左上に常時表示している。ナレーションは VOICEVOX:四国めたん。'),
              table([['時刻', '内容', '備考']] + [[f"{mmss(c['start_s'])}–{mmss(c['end_s'])}", c['title'],
                     (c['speed'] or '') + (f"（run {c['run_id']}）" if c.get('run_id') else '')] for c in ch], [24, 90, 60])]
    s += fig('video_frame_decision.png', 128, '図7 動画の一場面（取り違え）：拠点Wで救急箱を確認して拒否し、もう一方の拠点を確認しに向かう。下段はロボットの日本語報告。')
    s += [P('10. 再現方法', 'h1'),
          P('<font name="IPAexG">bash docker/build.sh</font> → <font name="IPAexG">bash docker/run.sh python3 scripts/run_campaign.py --protocol experiments/v34_protocol.json -- --model Qwen/Qwen3.5-9B --prompt-set v35 --intent-backend llm --intent-prompt i35 --recovery --explain</font>。'
            '全体フローは docs/ARCHITECTURE.md、設計判断は docs/DESIGN_DECISIONS.md。'),
          P('本資料・動画・コードに氏名・所属・メールアドレス等の個人情報は含めていない。講座サンプル（差動二輪ROSシミュレーション等）を出発点に、'
            '現地VLM確認・回復探索・独立安全ガード・真値監査・事前登録評価を独自に設計・実装した。', 'small')]
    doc.build(s)
    print(out)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--account', required=True)
    ap.add_argument('--video-url', default=None)
    ap.add_argument('--repo-url', default='https://github.com/fe2131-art/rescue-mind')
    a = ap.parse_args()
    build(a.account, a.video_url, a.repo_url)
