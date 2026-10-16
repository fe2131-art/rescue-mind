"""Render transparent 3-page report draft: no fabricated ROS/API results."""
from pathlib import Path
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.units import mm

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'docs/RescueMind_説明資料_ドラフト_未提出.pdf'
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
font='HeiseiKakuGo-W5'
NAVY=colors.HexColor('#16334F'); TEAL=colors.HexColor('#177B7E')
styles={
 'title':ParagraphStyle('title6',fontName=font,fontSize=20,leading=31,textColor=NAVY,spaceAfter=13),
 'h':ParagraphStyle('head6',fontName=font,fontSize=12,leading=18,textColor=TEAL,spaceBefore=12,spaceAfter=6),
 'body':ParagraphStyle('body6',fontName=font,fontSize=9,leading=15,spaceAfter=7),
 'sub':ParagraphStyle('sub6',fontName=font,fontSize=8,leading=13,spaceAfter=6,textColor=colors.HexColor('#596673')),
}
P=lambda t,k='body':Paragraph(t,styles[k])
def table(rows,widths):
 t=Table([[P(str(c),'sub') for c in row] for row in rows],colWidths=widths,repeatRows=1)
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#EAF4F3')),('LINEBELOW',(0,0),(-1,0),1,TEAL),
                        ('LINEBELOW',(0,1),(-1,-1),.2,colors.HexColor('#CCD6DC')),
                        ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
                        ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
 return t
story=[P('RescueMind v0.7','title'),P('Jevを必須とした救援物資拠点のAI認識と安全な接近経路の研究（研究用ドラフト・未提出）','sub'),
 P('1. 目的と課題設定','h'),
 P('災害時に自然言語の救援指示を読み取り、シミュレーション環境の物資拠点を確認し、避難所へ移動する。ロボットが環境の観測から走行開始の可否を判断する仕組みを構築する。現バージョンでは物体把持・物資の実積載は含まず、拠点への接近と目的地到達を対象とする。'),
 P('2. 提案方式と創造性','h'),
 table([['コンポーネント','役割と選定理由'],
        ['Jev 1.14.0（必須）','画像から型付きChoice/Noul/Boxを推論。物体不在ではBoxを無効化する。'],
        ['Qwen3.8-Omni-Flash','別モデルによる画像意味判断（API経路を分離）。'],
        ['Decision Fusion','両者の意見が一致し、危険の疑いが低い場合に限り出発を許可。'],
        ['ROS 2/Gazebo / Nav2','車輪制御・LiDAR監視・経路目標。直接駆動とNav2を別の実験経路として区別。']],
        [47*mm,127*mm]),
 P('3. 技術的工夫','h'),
 P('JevのBoxだけでは物体の存在を保証できないためNoulの存在確認を必須化。さらに現地で取得した画像でもQwenと照合し、不一致なら避難所への移動を拒否する。センサ監視が失敗した場合も移動しない。クラウドAIの長い待ち時間中はゼロ速度指令を繰り返し送る。'),
 P('4. v0.7の新規実装','h'),
 P('独自Gazebo環境での物資拠点到着後、カメラの新規画像を保存し、Jev＋Qwenの現地再判定によって避難所への次の移動を許可・拒否するチェックポイントを追加。推論中もROSをspinして停止指令とセンサ監視を継続する。'),
 PageBreak(),P('5. 実装・検証の記録','title'),
 P('実測済みなのはソフトウェア/理想運動学モデルの範囲であり、以下の結果をGazeboでの走行成功とは解釈しない。','sub'),
 table([['評価項目','今回確認した事実','必要な次の実証'],
        ['Pythonコード','チェックポイント判断・模擬ROS・モックAPIの自動テストを実行','実ROS上での現地画像取得とゲート実証'],
        ['数学モデル','水/医療の2ルートで運動学の追従を完走','Gazeboで車輪走行を観察'],
        ['静的障害物','ステーション矩形に対する離隔の近似確認','Gazeboコリジョン/実LiDAR'],
        ['Jev+Qwen推論','API契約と失敗時拒否の単体テスト','実画像/実APIで正解ラベル付き検証'],
        ['統計解析','Wilson区間とMcNemar正確検定の数値計算','実ケースの異常/正常のペア比較']],
       [38*mm,66*mm,70*mm]),
 P('運動モデルの再現結果','h')]
img=ROOT/'outputs/release/v06_waypoint_regression.png'
if img.exists():
 story.extend([Image(str(img),width=162*mm,height=119*mm),
               P('図：純Python数理シミュレーション。軌跡が描画されていてもGazebo実行結果ではない。','sub')])
story.extend([P('定量比較の設計','h'),
 P('Jevのみ、Qwenのみ、両者合意方式を同一の実画像条件で比較する。誤許可率と許可率（coverage）、誤拒否、実APIの応答時間を評価する。再現性を高めるため評価画像のハッシュ・ケースID・モデル名を保存し、未知画像を分離する。'),
 PageBreak(),P('6. 現状の限界・提出計画','title'),
 P('検証していない点','h'),
 P('このドラフトには、実Jev/Qwenの精度、Gazebo実走、Nav2による動的障害物回避、実世界の救助能力についての実測値はない。画像判断は物理障害物の三次元位置推定ではない。物理積載装置は未実装。安全認証装置でもない。'),
 P('優秀賞の評価観点への対応','h'),
 table([['観点','証拠の見せ方'],
        ['創造性','出発前と物資拠点到着後の二段階AI照合を可視化。'],
        ['技術力','画像→AI判断→動作命令→LiDAR/odom→到着イベントを端から端まで実証。'],
        ['実用性','危険な誤許可だけでなく、不必要な拒否による救援遅延も評価。'],
        ['表現力','約2分のロボット実写（Gazebo画面）+ 状態表示 + 実測値で説明。']],
       [39*mm,135*mm]),
 P('提出前チェック（2026年11月2日 10:00 JST締切）','h'),
 P('1〜3分のロボット実行MP4、PDF形式の説明資料、コード公開GitHub URLを準備する。YouTube動画のURLもOmniCampusで提出する。PDF名は「説明資料_PAI最終課題_omnicampusアカウント名.pdf」。動画タイトルは「PAI最終課題_omnicampusアカウント名」。個人情報、APIキー、所属を含めない。YouTubeは限定公開以上。'),
 P('再現・一次資料','h'),
 P('実装・操作手順：README.md / docs/V07_RUNBOOK.md。公式資料と制約：docs/RESEARCH_SOURCES_V07.md。検証ログ：outputs/release/。'),
 Spacer(1,8*mm),P('本PDFは成果完成版ではありません。実モデルとGazebo走行の検証を行い、実測値と動画のスクリーンショットを追記したうえで提出してください。','sub')])
def footer(c,doc):
 c.saveState();c.setFont(font,7);c.setFillColor(colors.HexColor('#667889'))
 c.drawString(18*mm,11*mm,'RescueMind v0.7 | 調査・実装ドラフト / 未提出')
 c.drawRightString(193*mm,11*mm,str(doc.page));c.restoreState()
SimpleDocTemplate(str(DEST),pagesize=(210*mm,297*mm),leftMargin=18*mm,rightMargin=18*mm,topMargin=17*mm,bottomMargin=19*mm,title='RescueMind v0.7 ドラフト（未提出）').build(story,onFirstPage=footer,onLaterPages=footer)
print(DEST)
