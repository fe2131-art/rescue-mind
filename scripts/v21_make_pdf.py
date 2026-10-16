#!/usr/bin/env python3
"""Non-submission PDF: claims correspond to offline verification only."""
from pathlib import Path
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
R=Path(__file__).resolve().parents[1]
D=json.loads((R/'verification/v21/V21_VERIFICATION.json').read_text())
OUT=R/'docs/RescueMind_v21_REPORT_DRAFT_NOT_SUBMISSION.pdf'
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
W,H=A4;c=canvas.Canvas(str(OUT),pagesize=A4,pageCompression=1)
c.setTitle('RescueMind v2.1 Physical AI 応用1 説明資料（未提出）')
c.setAuthor('RescueMind - anonymous draft')
FONT='HeiseiKakuGo-W5';DARK=(.08,.18,.28);BLUE=(.03,.36,.54)
def text(x,y,s,size=9.2,color=DARK):
 c.setFillColorRGB(*color);c.setFont(FONT,size);c.drawString(x,y,s)
def header(title,page):
 c.setFillColorRGB(*DARK);c.rect(0,H-108,W,108,fill=1,stroke=0)
 text(38,H-39,'RESCUEMIND  /  PHYSICAL AI 2026',13,(1,1,1))
 text(38,H-75,title,15,(1,1,1))
 text(38,30,'v2.1 | 2026-10-16 | 未提出・実Gazebo・実AI推論は未検証',8)
 text(W-74,30,f'{page} / 3',8)
def section(y,title,items):
 text(42,y,title,11.3,BLUE);y-=29
 for item in items:
  text(48,y,'・'+item,9); y-=24
 return y-18

def box(y,title,items):
 c.setFillColorRGB(.92,.96,.98);c.roundRect(40,y,W-80,99,8,fill=1,stroke=0)
 text(54,y+74,title,10.4,BLUE)
 for k,s in enumerate(items):text(54,y+49-k*22,s,8.6)

header('研究目的・課題への適合',1)
y=H-155
y=section(y,'課題の評価基準と提出条件',[ '創造性、技術力、実用性、表現力を総合的にアピール。', '提出必須：実ロボット動画60～180秒、PDF資料、GitHub public URL。', 'YouTube URLもOmniCampusに提出。締切：11月2日10:00。'])
y=section(y,'RescueMindの役割とAIの行動への関与',[ '自然言語指示で物資拠点へ移動し、ROSカメラの新画像を取得。', 'Jev 1.14.0必須＋Qwen3.8の一致によって次の走行を許可。', '誤物資・危険・判断不一致時は避難所へ進まず停止。'])
y=section(y,'実装範囲',[ '車輪ロボットの接近・停止（把持・積載・運搬は未実装）。', '独立速度ガード、ROS移動記録、時刻・因果順序監査。', 'Nav2による動的経路再計画や安全認証は未実証。'])
box(111,'研究として示す差別化',['AIによる「現地での次区間許可」と車輪の実行を結び付ける。', '物資の違いによって続行／停止が変わる実動画が目標。'])
c.showPage()
header('v2.1の改善・オフライン検証',2)
y=H-155
y=section(y,'v2.0で見つかった弱点',[ 'ROSセンサーの受信検査だけではGazebo側のトピック存在が未確認。', 'SDFとブリッジの型・方向の不整合は実行時に切り分けづらい。'])
y=section(y,'v2.1に実装した修正',[ 'SDF・ブリッジYAMLのワールド名・トピック型・方向を照合。', 'Gazebo Transportの /clock・/camera・/scan・/odomを走行前検査。', '検査に失敗した場合はROSミッションを開始しない。'])
y=section(y,'実際に行った検証（シミュレータの実測ではない）',[ f'Python自動テスト：{D["unit_tests_passed"]}件すべて成功。', '欠損トピック、コマンドエラー、SDF破損、型不一致を模擬検査。', '実Gazebo Transport未導入：本物のトピック・動作は未検証。', '起動計画とJev必須のライブ経路が保たれることを検査。'])
box(106,'検証の限界',['Gazebo側にトピック名があるだけでは画像・駆動の成功は保証しない。', '実走行・API応答・実画像分類率は今回測定していない。'])
c.showPage()
header('受賞へ向けた検証計画・提出ゲート',3)
y=H-155
y=section(y,'4評価項目と実証すべき証拠',[ '創造性：物資が異なるとロボットの行動が変わる実映像。', '技術力：ROS・Gazebo・Jev/Qwen・安全ガードの連続動作。', '実用性：誤許可率、誤拒否率、保留率、判断遅延を比較。', '表現力：2分程度の動画でAI判断と走行を同時に説明。'])
y=section(y,'実際のUbuntu上で必ず実施する順序',[ '1. Gazebo起動 → Gazebo Transport・ROS時計・センサー確認。', '2. 非AI走行 → 独立ROS軌跡・ROS bagの実収録。', '3. Jev＋Qwen実画像推論 → 正常・拒否の2条件を撮影。', '4. ラベル付き実画像の比較試験 → 結果をPDFに記載。'])
y=section(y,'提出物の最終検査',[ '実Gazebo動画：MP4 60～180秒。倍速の場合は明記。', 'PDFのファイル名、GitHub public、YouTube公開条件を再確認。', '個人情報、メール、APIキー、所属などは含めない。'])
box(100,'2026年11月2日（月）10:00 JST 締切',['コードとPDFドラフトは準備中。実機相当のGazebo映像は未完成。', '完成の自己申告ではなく、実行映像とログを提出する。'])
c.save()
print(OUT)
