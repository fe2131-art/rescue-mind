"""Generate an explicitly non-submittable Japanese report draft from VERIFIED offline results.
No user name, real-Gazebo success, real model accuracy or video claim is inserted.
"""
from __future__ import annotations
from pathlib import Path
import json
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/'outputs/release/v09_verification_summary.json').read_text())
FAULT=json.loads((ROOT/'outputs/release/v09_fault_matrix.json').read_text())
PDF=ROOT/'docs/RescueMind_v09_report_DRAFT_not_for_submission.pdf'
PDF.parent.mkdir(parents=True,exist_ok=True)
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
BASE='HeiseiKakuGo-W5'
ink=colors.HexColor('#16293A');accent=colors.HexColor('#1D5667')
style=ParagraphStyle('jp',fontName=BASE,fontSize=9.2,leading=16,textColor=ink,spaceAfter=8,wordWrap='CJK')
small=ParagraphStyle('small',parent=style,fontSize=7.7,leading=12)
heading=ParagraphStyle('heading',parent=style,fontSize=14,leading=22,spaceBefore=6,spaceAfter=11,textColor=accent)
title=ParagraphStyle('title',parent=style,fontSize=20,leading=27,textColor=ink,spaceAfter=12)
subtitle=ParagraphStyle('subtitle',parent=style,fontSize=11,leading=18,textColor=accent)
label=ParagraphStyle('label',parent=small,fontSize=8)

def P(s,styl=style):return Paragraph(s,styl)
def bullet(s):return P('・'+s)
def table(rows, widths, fs=8.0):
    t=Table([[P(str(c),small) for c in row] for row in rows],colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E9F2F4')),
      ('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),
      ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
      ('LINEBELOW',(0,0),(-1,0),.7,accent),('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#CFD8DA'))]))
    return t

def footer(canvas,doc):
    canvas.saveState();canvas.setFont(BASE,7)
    canvas.setFillColor(colors.HexColor('#5E6B74'))
    canvas.drawString(17*mm,12*mm,'RescueMind v0.9  |  未提出ドラフト / 未検証事項あり')
    canvas.drawRightString(193*mm,12*mm,f'{doc.page}')
    canvas.restoreState()

doc=SimpleDocTemplate(str(PDF),pagesize=A4,rightMargin=17*mm,leftMargin=17*mm,topMargin=18*mm,bottomMargin=20*mm)
w=176*mm
story=[]
# page 1
story += [P('Physical AI 応用1 最終課題',subtitle), P('RescueMind v0.9',title),
          P('Jev必須の二重視覚判断で、現地確認から避難所接近までを制御する研究用ロボット'),
          P('<b>目的</b>　災害対応を想定し、自然言語の救援要請を受けた差動二輪ロボットが物資拠点へ向かう。到着後にロボットのカメラ画像をJev 1.14.0とQwen3.8-Omni-Flashに入力し、正しい物資について合意した場合だけ避難所Bまで接近する。'),
          P('課題と評価基準の対応',heading),
          table([['公式の加点項目','本作品の工夫と、提出までに必要な証拠'],
                ['創造性','現地画像に基づき「次区間へ進む／停止」を分岐。実行動画に両例を収める。'],
                ['技術力','Jevの型付き判断、Qwenの画像理解、ROS 2カメラ・差動二輪・LiDAR監視を統合。'],
                ['実用性','誤物資、危険の疑い、API失敗、近接障害物、車輪停滞で停止。誤拒否とのトレードオフを実測する。'],
                ['表現力','自然言語→物資拠点→現地判定→避難所接近と、失敗例を2分で示す。']], [32*mm,w-32*mm]),
          Spacer(1,8*mm),P('作品の正しい表現',heading),
          bullet('実装済みのタスクは<b>物資拠点の視覚確認と避難所への接近</b>。物資の把持・積載・物理的運搬は未実装。'),
          bullet('独自Gazeboワールドのウェイポイント走行はNav2でなく直接駆動。動的な迂回経路再計画は未実装。'),
          bullet('実API・実Gazeboの成功を示す動画と計測結果は、現時点の配布ZIPには含まれない。'),
          PageBreak()]
# page 2
story += [P('システムとv0.9改善点',heading),
          table([['入力','処理','出力/判断'],
                 ['日本語の指示','TF-IDF分類＋曖昧指示ガード','水/医薬の物資拠点へ向かう'],
                 ['ロボットROSカメラ','Jev 1.14.0 + Qwen3.8','物資ラベルと現地危険表示を評価'],
                 ['2モデルの応答','安全ゲートで一致・存在・危険を照合','次区間を許可 or その場で停止'],
                 ['オドメトリ/LiDAR','位置追従、近接・停滞・途絶監視','車輪コマンドまたは停止']], [38*mm,63*mm,75*mm]),
          Spacer(1,6*mm),P('今回の監査→修正→再検証',heading),
          bullet('前版では、物資ラベルが正しければ同じ画像で明示的な危険があっても続行可能だった。v0.9はJev hazard、両モデルscene=hazard、不完全な観測で拒否。'),
          bullet('移動停滞を新たに検知するProgressWatchを追加し、前進コマンド中に位置が変わらなければ停止要求を出す。'),
          bullet('ROSライブ起動時のカメラ受信確認、実験ログのJev/Qwen両モデル識別・判断再計算・イベント時刻順序の監査を追加。'),
          P('オフライン実行検証（2026-10-16）',heading),
          table([['検証項目','結果','限界'],
                 ['単体・モック結合テスト',f"{DATA['test_count']}件、全件成功",'実ROS/Gazeboの成功ではない'],
                 ['合成JSON故障条件',f"{FAULT['cases']}通り：許可{FAULT['allowed']}、拒否{FAULT['rejected']}",'実VLMの精度ではない'],
                 ['SDFトピックと静的幾何','静的検査 PASS','車輪接地・衝突は未実証'],
                 ['配布検証','ZIP CRC / SHA-256 / 展開後再試験','物理系を保証しない']], [49*mm,56*mm,71*mm]),
          PageBreak()]
# page 3
story += [P('比較実験と最終提出計画',heading),
          P('実測予定の比較：Jev単独 / Qwen単独 / Jev＋Qwenの合意を同じ未使用のカメラ画像セットで比較する。正解ラベルを先に人手で固定し、誤許可率、適切な許可率、API遅延、ロボット到達率を測る。統計的不確実性にはWilson区間とMcNemar正確検定を用いる。現時点では実画像データ未収集のため、この結果を掲載しない。'),
          P('提出動画（120秒想定）',heading),
          table([['時間','映像で示す事実'],
                 ['0:00–0:34','救援要請、ロボット出発、実Gazeboの移動'],
                 ['0:34–1:18','現地ROS画像、JevとQwenの判定、避難所へ続行'],
                 ['1:18–1:38','意図的な誤物資または危険シーンへの拒否'],
                 ['1:38–2:00','両モデルの比較実測、実装の制約と改善点']], [38*mm,w-38*mm]),
          Spacer(1,6*mm),P('残る必須実証',heading),
          bullet('Ubuntu PCでROS 2 Jazzy + Gazebo Harmonicの物理走行、ROSカメラ撮影、Jev/Qwen実API呼び出しを実行する。'),
          bullet('成功シナリオと停止シナリオの生映像・JSON・カメラ画像SHA-256を照合する。'),
          bullet('動画1〜3分、公開GitHub URL、講座指定名PDFを整備し、OmniCampusとYouTubeの両方に提出する。'),
          P('根拠資料',heading),
          P('課題原文：Physical AI応用1講座 最終課題（10/8版）。技術：Jev 1.14（TypeSafe公式）、Qwen3.8-Omni-Flash（Alibaba Cloud公式）、Gazebo Harmonic ROS 2連携、Nav2 Jazzy Getting Started。詳細なリンク・確認範囲はZIP内 docs/V09_RESEARCH_AND_VERIFICATION.md を参照。',small),
          Spacer(1,6*mm),
          P('<b>このPDFは未提出ドラフト。</b> 11月2日10:00 JST締切。実際に確認できた画像・数値に差し替え、OmniCampusアカウント名をファイル名に反映してから提出する。',small)]
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(PDF)
