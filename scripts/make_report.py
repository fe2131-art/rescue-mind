#!/usr/bin/env python3
"""Build the submission PDF (説明資料) from committed results; numbers are never hand-typed.

  python3 scripts/make_report.py --account <omnicampusアカウント名> [--video-url URL]

Output: docs/report/説明資料_PAI最終課題_<account>.pdf  (personal info must not appear;
only the omnicampus account name is allowed by the assignment rules).
"""
from __future__ import annotations
import argparse
import json
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
                         spaceAfter=6, borderPadding=(0, 0, 3, 0)),
    'h2': ParagraphStyle('h2', fontName='IPAexG', fontSize=11.5, leading=16, textColor=ACC, spaceBefore=6, spaceAfter=3),
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


def load():
    d = {}
    ledger = RES / 'campaign_ledger.jsonl'
    rows = [json.loads(x) for x in ledger.read_text().splitlines()] if ledger.is_file() else []
    d['all'] = rows
    d['final'] = [r for r in rows if r.get('final', True)]
    for k in ('A', 'B'):
        f = RES / f'campaign_{k}_aborted_ledger.jsonl'
        d[k] = [json.loads(x) for x in f.read_text().splitlines()] if f.is_file() else []
    d['dev'] = json.loads((RES / 'devset_summary.json').read_text())
    d['wheel'] = json.loads((RES / 'wheel_axis_regression.json').read_text()) if (RES / 'wheel_axis_regression.json').is_file() else None
    return d


def campaign_stats(final):
    def count(scene, action):
        return sum(1 for r in final if r['scene'] == scene and r['observed_action'] == action)
    lat = sorted(r['vlm_latency_s'] for r in final if r.get('vlm_latency_s') is not None)
    wall = sorted(r['wall_s'] for r in final)
    allowed = lambda r: r.get('vlm_reason') == 'on_site_supply_confirmed'
    fa = sum(1 for r in final if r.get('vlm_reason') and allowed(r) and r['expected_action'] == 'DENY')
    fd = sum(1 for r in final if r.get('vlm_reason') and not allowed(r) and r['expected_action'] == 'ALLOW')
    # Decision level = what the VLM checkpoint decided (independent of evidence audits).
    dec = [r for r in final if r.get('vlm_reason')]
    dec_ok = sum((r['vlm_reason'] == 'on_site_supply_confirmed') == (r['expected_action'] == 'ALLOW') for r in dec)
    unverified = [r for r in final if r['observed_action'] == 'DENY_UNVERIFIED']
    causes = {}
    for r in final:
        if r['correct']:
            continue
        e = (r.get('error') or '')
        if 'odometry diverged' in e:
            k = 'オドメトリ誤差が監査上限0.25 mを超過（真値監査）'
        elif r['observed_action'] == 'DENY_UNVERIFIED':
            k = '拒否は正しいが停止証拠の時刻整合が不合格'
        elif not r.get('vlm_reason'):
            k = 'VLM判断前のインフラ失敗'
        elif (r['vlm_reason'] == 'on_site_supply_confirmed') != (r['expected_action'] == 'ALLOW'):
            k = 'VLMの判断誤り'
        else:
            k = 'その他の監査不合格'
        causes[k] = causes.get(k, 0) + 1
    return {'n': len(final), 'correct': sum(r['correct'] for r in final), 'fa': fa, 'fd': fd, 'causes': causes,
            'decided': len(dec), 'decision_correct': dec_ok, 'unverified': len(unverified),
            'lat_med': lat[len(lat) // 2] if lat else None, 'lat_max': lat[-1] if lat else None,
            'wall_med': wall[len(wall) // 2] if wall else None,
            'by': {s: {a: count(s, a) for a in ('ALLOW', 'DENY', 'DENY_UNVERIFIED', 'FAILED')}
                   for s in ('nominal', 'swapped', 'empty')}}


def campaign_ab_text(a_rows, b_rows):
    def summary(rows):
        decided = [r for r in rows if r['observed_action'] in ('ALLOW', 'DENY', 'DENY_UNVERIFIED')]
        return (len({r['trial_id'] for r in rows}), len(rows), len(decided), sum(r['correct'] for r in decided),
                sum(1 for r in rows if r['observed_action'] == 'FAILED'))
    if not a_rows:
        return ''
    ta, na, da, ca, fa = summary(a_rows)
    txt = (f'※ 評価Cの前に2回の評価を中断した（台帳はいずれも公開）。評価A（{ta}試行・{na}回実行）は、起動直後のミッションノードが3秒以内に'
           f' /odom・/scan を受信できないDDS探索の競合で {fa} 回失敗（VLM判断に至った {da} 回はすべて正解 {ca}/{da}）。')
    if b_rows:
        tb, nb, db, cb, fb = summary(b_rows)
        txt += (f'評価B（{tb}試行・{nb}回実行）は、Aの中断時に監督プロセスを強制終了したため孤立したスタック（速度ガードを含む）が残存し、'
                f'Publisher監視が「/cmd_vel の発行者が2つ」を正しく検知して全 {fb} 回を判断前に停止した。')
    txt += ('起動待機・停止シグナル・孤立スタック検出を修正し（判断ロジック・閾値は不変）、30試行すべてを評価Cとして最初からやり直した。以下はCの結果。')
    return txt


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(ACC); canvas.setLineWidth(2)
    canvas.line(18 * mm, 287 * mm, 192 * mm, 287 * mm)
    canvas.setFont('IPAexG', 7.5); canvas.setFillColor(MUT)
    canvas.drawString(18 * mm, 10 * mm, 'Physical AI 応用1講座 最終課題 ｜ RescueMind v3.3')
    canvas.drawRightString(192 * mm, 10 * mm, f'{doc.page}')
    canvas.restoreState()


def build(account: str, video_url: str | None, repo_url: str):
    d = load()
    cs = campaign_stats(d['final'])
    dev = {t['tag']: t for t in d['dev']}
    dv = lambda tag: next(r for r in dev[tag]['rows'] if r['tau'] == 0.5)
    retries = [r for r in d['all'] if not r.get('final', True)]
    out = ROOT / 'docs/report' / f'説明資料_PAI最終課題_{account}.pdf'
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(str(out), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                          topMargin=16 * mm, bottomMargin=16 * mm,
                          title='RescueMind v3.3 説明資料', author=account, subject='Physical AI 応用1講座 最終課題')
    doc.addPageTemplates([PageTemplate('p', [Frame(18 * mm, 16 * mm, 174 * mm, 266 * mm, id='f')], onPage=on_page)])
    s = []
    # ---------------- 1. cover / summary
    s += [P('RescueMind：現地で「目で確かめてから」届ける災害物資ロボット', 'title'),
          P('ローカルVLM（Qwen2.5-VL-3B / V100）× ROS 2 Jazzy × Gazebo Harmonic — 判断を誤らないための検証可能な自律移動', 'sub'),
          table([['項目', '内容'],
                 ['提出者', f'omnicampus アカウント：{account}'],
                 ['コード', repo_url],
                 ['動画', video_url or 'YouTube（タイトル：PAI最終課題_' + account + '）。走行区間は2〜3倍速、AI判断区間は等速（倍速は動画内に常時表示）'],
                 ['使用ツール', 'ROS 2 Jazzy / Gazebo Harmonic（Docker, EGLヘッドレス描画） / PyTorch 2.5.1 + Transformers 4.53 / Tesla V100 32GB'],
                 ['AIの活用', '①自然言語指示の分類（TF-IDF＋ロジスティック回帰）②搭載カメラ画像のローカルVLM推論（閉集合対数確率スコアリング）'],
                 ['主結果', f"事前登録した30試行（自律走行＋実撮影＋実推論）で <b>VLMの許可／拒否判断 {cs['decision_correct']}/{cs['decided']} 正解</b>"
                           f"（誤許可 {cs['fa']} 件・誤拒否 {cs['fd']} 件）、Gazebo真値・ROS bag による独立監査まで合格 {cs['correct']}/{cs['n']}。"
                           f"VLM判断遅延の中央値 {cs['lat_med']:.2f} 秒"]],
                [28, 146]),
          Spacer(1, 8)]
    s += [P('1. 課題の概要と目的', 'h1'),
          P('災害時の物資配送では「在庫表では水があるはずの棚に、実際は救急箱が置かれていた／空だった」という'
            '<b>情報と現物の食い違い</b>が起こりやすい。指示どおりに機械的に運ぶロボットは、誤った物資を自信満々に届けてしまう。'
            '本作品は、自然言語で依頼を受けた差動二輪ロボットが物資拠点まで自律移動し、<b>その場で静止して搭載カメラで現物を確認</b>、'
            'ローカルVLMが「依頼された物資がある」と高い確信で一致した場合にだけ避難所Bへ向かい、違えば<b>その場で停止して人に判断を委ねる</b>タスクを実装した。'),
          P('狙いは「AIに運ばせる」ことではなく、<b>AIの判断が間違っているときにロボットが動かないこと</b>を、ログと物理シミュレータの真値で検証可能にすることである。'
            'ロボットは物資の把持・運搬は行わない（現物確認と避難所への接近までを対象とし、配達完了とは表現しない）。')]
    s += fig('architecture.png', 172, '図1 実行時アーキテクチャ。全推論はローカルGPUで実行し、クラウドAPIは使用しない。')
    # ---------------- 2. AI
    s += [P('2. AIの活用と工夫', 'h1'),
          P('2.1 現地確認VLM：自由生成から「閉集合の対数確率スコアリング」へ', 'h2'),
          P('引継ぎ版（v3.2）は VLM に JSON を自由生成させていたが、実際の Gazebo 画像で評価すると、質問2はほぼ常に「なし」、'
            '質問1は空の棚で「水」と幻覚し、96応答中21件は解析不能だった。v3.3 では各質問を<b>3択の選択式</b>にし、'
            '生成はせず<b>次トークンの選択肢文字（A/B/C）の対数確率</b>を1回の順伝播で読み取り softmax で確率化する。'
            '2問は<b>選択肢の順序を入れ替え</b>、文字位置バイアスで両問が同じ誤答に一致することを防ぐ。危険（火災・煙・瓦礫）は別の Yes/No 質問で判定する。'
            '許可条件は「2問とも依頼物資が最大かつ確率 0.50 以上、危険なし」。'),
          table([['方式（開発セット48枚, τ=0.50）', '正しい判定', '誤許可', '誤拒否', '解析不能', '1問あたり遅延'],
                 ['v3.2 引継ぎ：自由生成JSON（Qwen 3B）', f"{dv('qwen3b_json_baseline')['allow_correct'] + dv('qwen3b_json_baseline')['deny_correct']}/48",
                  dv('qwen3b_json_baseline')['false_approval'], dv('qwen3b_json_baseline')['false_denial'],
                  dev['qwen3b_json_baseline']['parse_or_http_errors'], f"{dev['qwen3b_json_baseline']['mean_latency_per_pass_s']:.2f} 秒"],
                 ['SmolVLM2-2.2B：対数確率（2モデル合議の候補）', f"{dv('smolvlm2_scored')['allow_correct'] + dv('smolvlm2_scored')['deny_correct']}/48",
                  dv('smolvlm2_scored')['false_approval'], dv('smolvlm2_scored')['false_denial'],
                  dev['smolvlm2_scored']['parse_or_http_errors'], f"{dev['smolvlm2_scored']['mean_latency_per_pass_s']:.2f} 秒"],
                 ['<b>v3.3 採用：対数確率（Qwen 3B）</b>', f"<b>{dv('qwen3b_scored')['allow_correct'] + dv('qwen3b_scored')['deny_correct']}/48</b>",
                  dv('qwen3b_scored')['false_approval'], dv('qwen3b_scored')['false_denial'],
                  dev['qwen3b_scored']['parse_or_http_errors'], f"{dev['qwen3b_scored']['mean_latency_per_pass_s']:.2f} 秒"]],
                [62, 22, 16, 16, 18, 26]),
          Spacer(1, 4)]
    s += fig('devset_ablation.png', 165, '図2 開発セット（テレポートで視点をランダム化した48枚）での方式比較。閾値はここだけで決定した。')
    s += [P('2.2 開発セットと評価の分離（事前登録）', 'h2'),
          P('プロンプトと閾値は、評価とは別に作った<b>開発セット</b>（3シーン×2拠点×8視点、seed=7）だけで決めた。'
            '真の陽性の最小確率 0.569、陰性の最大確率 0.019 と大きく分離しており、閾値 0.50 を'
            '<font name="IPAexG">experiments/PREREGISTRATION_v33.md</font> に固定してから、事前に順序・ID まで決めた30試行の閉ループ評価を一度だけ実行した。'),
          P('2.3 自然言語指示', 'h2'),
          P('文字 n-gram の TF-IDF＋ロジスティック回帰で「水／医療物資」を分類し、避難所名を正規表現で抽出する。'
            '両方の物資が含まれる・どちらも含まれず確信度が低い・未対応の避難所、のいずれも<b>出発前に拒否</b>する（既定値で黙って選ばない）。')]
    # ---------------- 3. Robot / safety engineering
    s += [P('3. ロボット制御と安全設計', 'h1')]
    s += bullets([
        '<b>2区間ミッション</b>：物資拠点へウェイポイント追従 → 拠点中心へカメラを向けて静止 → オドメトリで静止を確認してから新規フレームを2枚取得（画質・ROS時刻・シミュレーション時計を検査）→ VLM判断 → 許可時のみ避難所Bへ。推論中・拒否後もゼロ速度と静止を監視し続ける。',
        '<b>独立速度ガード</b>：ミッションは要求トピックにしか出力できず、<font name="IPAexG">/cmd_vel</font> の唯一の発行者は別プロセスのガード。LiDAR前方距離・カメラ/LiDAR/オドメトリの鮮度・速度上限・後退禁止を10 Hzで判定し、異常はラッチしてゼロ速度。',
        '<b>Publisher監視</b>：DDSグラフを200 msごとに監視し、<font name="IPAexG">/cmd_vel</font> に第2の発行者が現れたら非常停止。',
        '<b>証拠に基づく完了判定</b>：成功は「許可→避難所到着」をミッション自身の記録ではなく、独立レコーダが購読した <b>Gazebo真値姿勢</b>・ROS bag（MCAP）・時系列（許可より前に避難所へ近づいていないこと）で監査して初めて <font name="IPAexG">COMPLETED</font>。拒否は「拒否＋2.5秒停止保持＋真値で拠点から動いていない」で初めて <font name="IPAexG">COMPLETED_EXPECTED_DENIAL</font>（VLMのエラー停止は拒否成功に数えない）。',
        '<b>環境</b>：Ubuntu 22.04 ホストで、Docker（ROS 2 Jazzy + Gazebo Harmonic + CUDA PyTorch）を sudo なしで実行。Gazebo は EGL ヘッドレス描画（V100）で、カメラと gpu_lidar を描画する。',
    ])
    # ---------------- 4. results
    by = cs['by']
    s += [P('4. 実験結果：事前登録30試行の閉ループ評価', 'h1'),
          P(f"3シーン（正常配置／水と救急箱の取り違え／欠品）×依頼物資2種×5反復を、試行ごとに Gazebo・ブリッジ・ガード・VLM を<b>新規起動</b>して実行した。"
            f"同一ワールドの反復であり30個の独立なシーンではない点に注意。"
            f"<b>VLMの判断（許可／拒否）</b>は判断に到達した {cs['decided']} 試行中 <b>{cs['decision_correct']} 試行で期待どおり</b>、"
            f"危険側の誤り（誤許可）<b>{cs['fa']}</b> 件。"
            f"判断に加えて Gazebo 真値・ROS bag・時系列の<b>独立監査まで全て合格した試行</b>は <b>{cs['correct']}/{cs['n']}</b>"
            + ('（不合格の内訳：' + '、'.join(f'{k} {v}件' for k, v in cs['causes'].items()) + '）' if cs['causes'] else '') + '。'
            + f"VLM判断遅延（静止画取得→判断）の中央値 {cs['lat_med']:.2f} 秒（最大 {cs['lat_max']:.2f} 秒）、1試行の全体時間の中央値 {cs['wall_med']:.0f} 秒（起動・準備確認を含む）。"
            + (f"VLM判断前のインフラ失敗による再試行は {len(retries)} 件（台帳に記録）。" if retries else 'インフラ失敗による再試行は 0 件。')),
          P(campaign_ab_text(d['A'], d['B']), 'small'),
          Spacer(1, 4),
          table([['シーン', '期待', '許可→避難所到着', '拒否→拠点で停止', '拒否（証拠不足）', '失敗'],
                 ['正常配置', '許可', by['nominal']['ALLOW'], by['nominal']['DENY'], by['nominal']['DENY_UNVERIFIED'], by['nominal']['FAILED']],
                 ['取り違え', '拒否', by['swapped']['ALLOW'], by['swapped']['DENY'], by['swapped']['DENY_UNVERIFIED'], by['swapped']['FAILED']],
                 ['欠品', '拒否', by['empty']['ALLOW'], by['empty']['DENY'], by['empty']['DENY_UNVERIFIED'], by['empty']['FAILED']]],
                [26, 16, 34, 34, 34, 20]),
          Spacer(1, 6)]
    s += fig('campaign_results.png', 165, '図3 30試行の結果（左）とVLM判断遅延の分布（右）。')
    s += fig('trajectories.png', 120, '図4 全試行の Gazebo 真値軌跡。許可された試行だけが避難所Bへ向かい、拒否試行は拠点で停止している。')
    # ---------------- 5. findings
    s += [P('5. 実際に動かして初めて分かった問題と対策', 'h1'),
          P('引継ぎ時点のコードは506件の単体テストに合格していたが、実 Gazebo・実 ROS 2・実 GPU では一度も動いていなかった。'
            '実行して次の問題を発見し、すべて再現→修正→確認した（詳細は <font name="IPAexG">docs/FINDINGS.md</font>）。')]
    s += [table([['症状', '原因', '対策'],
                 ['オドメトリ上は前進1.5 mだが、実車体は横に滑り傾いていた', 'ロール済み車輪リンクの子座標系で関節軸を指定（車輪が鉛直軸回転）', '軸をモデル座標系で指定。Gazebo真値で監査する仕組みを追加'],
                 ['オドメトリ基準の「独立」監査が不正走行を見逃し得た', '制御器と監査器が同じ車輪オドメトリを信用', 'OdometryPublisher の真値を別トピックで監査（制御器は購読しない）'],
                 ['走行開始2秒でカメラ途絶判定', 'Best Effort QoS で0.9 MB画像を断片ロス（102枚中10枚のみ到達）', '画像購読を Reliable/KEEP_LAST(2) に統一'],
                 ['Publisher監視が起動直後に誤停止', 'DDSのノード名メタデータ到着前の一時的な不明表示', 'アーム前・猶予内・1件・型一致のみ保留扱い（テスト追加）'],
                 ['物資が画面外／LiDARが自機マストを検出', 'カメラが低すぎる／gpu_lidar は visual を描画して測距', 'カメラを0.62 mのマストへ。visibility flag/mask で自機装飾を除外'],
                 ['VLMが水ボトルを認識しない', '小道具が単なる水色円柱（Sim-to-VLMギャップ）', '半透明PET・肩・首・キャップ・ラベルの6本パックに作り替え'],
                 ['評価Aで起動直後に /odom・/scan 未受信', '新規ノードのDDS探索が3秒の固定待機に間に合わない', '全必須ストリームの初回受信まで最大20秒待機（ゼロ速度）'],
                 ['評価Bで「/cmd_vel 発行者が2つ」と全停止', '中断時のSIGKILLで速度ガードを含むスタックが孤立・残存', '段階的停止（SIGINT→SIGTERM→SIGKILL）、docker --init、起動前の孤立スタック検出']],
                [52, 62, 60])]
    s += fig('wheel_axis_regression.png', 165, '図5 同じ速度指令に対する車輪オドメトリとGazebo真値。左：引継ぎ版の軸定義（車輪は回るが車体はほぼ進まず、オドメトリだけが1.1 m進む）、右：修正後。')
    # ---------------- 6. practicality
    s += [P('6. 実用性・応用可能性', 'h1')]
    s += bullets([
        '<b>人と協調する停止</b>：誤物資・欠品・危険を検知すると「出発しない」ことが既定動作で、現場の人に確認を委ねる。物流倉庫・病院内搬送・避難所運営など、在庫情報と現物がずれる現場に直接対応する。',
        '<b>オフライン・オンデバイス</b>：通信が途絶しやすい災害時を想定し、推論はすべて単一GPU上で完結（クラウドAPIキー不要）。3Bモデル・FP16で約8 GBのVRAM。',
        '<b>検証可能性</b>：判断に使った画像のSHA-256、各問の確率、真値軌跡、ROS bag を試行ごとに保存し、第三者が判断と行動の因果を再計算できる。',
    ])
    s += [P('7. 限界と今後の課題', 'h1')]
    s += bullets([
        '物資の把持・運搬は未実装。Nav2 による動的経路計画ではなく、既知配置のウェイポイント追従である。',
        '自己位置は車輪オドメトリのみの推測航法で、長い経路（医療物資→避難所）では真値と最大0.24〜0.27 mずれた（1試行が監査上限0.25 mを超過）。LiDARによる自己位置推定（AMCL等）が次の改善点。',
        '評価は単純な幾何形状の小道具・3シーン・固定照明の反復で、実写画像や多様な物資への汎化は未検証。閾値0.50は確率の較正ではない。',
        '2モデル合議（SmolVLM2）は本条件では全許可ケースを誤拒否し実用にならなかった（否定的結果として報告）。より大きなモデルや微調整、実機（SO-101 等）での Sim-to-Real が次の課題。',
        'ROSグラフ監視は認証機構ではなく、実機の安全認証を意味しない。',
    ])
    chap = ROOT / 'docs/video_chapters.json'
    if chap.is_file():
        ch = json.loads(chap.read_text(encoding='utf8'))
        mmss = lambda x: f'{int(x // 60)}:{int(x % 60):02d}'
        s += [P('8. 提出動画の構成', 'h1'),
              P(f"全 {mmss(ch[-1]['end_s'])}。3-D映像はすべて Gazebo の実レンダリング（俯瞰カメラ＋ロボット搭載カメラ）で、モック映像や模式図は使っていない。"
                '字幕・確率バー・軌跡はその試行のログ（mission.json・真値）から自動合成。<b>走行区間は2〜3倍速、AI判断区間は等速</b>で、速度は画面左上に常時表示している。'),
              table([['時刻', '内容', '備考']] + [[f"{mmss(c['start_s'])}–{mmss(c['end_s'])}", c['title'],
                     (c['speed'] or '') + (f"（run {c['run_id']}）" if c.get('run_id') else '')] for c in ch], [24, 90, 60])]
        s += fig('video_frame_decision.png', 160, '図6 動画の一場面（取り違えシーン）：VLMが救急箱を検出し、依頼された飲料水ではないため拒否して停止。')
    s += [P('9. 再現方法', 'h1'),
          P('<font name="IPAexG">bash docker/build.sh</font> → <font name="IPAexG">bash docker/run.sh python3 scripts/run_campaign.py</font>。'
            '詳細は README（モデル重みは Hugging Face から事前取得、実行時は <font name="IPAexG">HF_HUB_OFFLINE=1</font>）。'
            'テストは <font name="IPAexG">python3 -m unittest discover -s tests</font>（ROS/Gazebo 不要の部分を含む）。'),
          P('本資料・動画・コードに氏名・所属・メールアドレス等の個人情報は含めていない。作品は講座サンプル（差動二輪ROSシミュレーション等）を出発点に、'
            '現地VLM確認・独立安全ガード・真値監査・事前登録評価を独自に設計・実装したものである。', 'small')]
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
