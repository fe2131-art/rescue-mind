#!/usr/bin/env python3
"""Draft report with source-grounded requirements and explicitly offline results."""
from pathlib import Path
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
ROOT=Path(__file__).resolve().parents[1]
REPORT=json.loads((ROOT/'verification/v18/v18_TEST_REPORT.json').read_text())
OUT=ROOT/'docs/RescueMind_v18_REPORT_DRAFT_NOT_SUBMISSION.pdf'
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
W,H=A4;c=canvas.Canvas(str(OUT),pagesize=A4,pageCompression=1)
c.setTitle('RescueMind v1.8 AI×ロボティクス 最終課題説明資料（ドラフト）')
c.setAuthor('RescueMind')
font='HeiseiKakuGo-W5'
def line(x,y,s,sz=10,clr=(.16,.23,.32)):
 c.setFont(font,sz);c.setFillColorRGB(*clr);c.drawString(x,y,s)
def box(x,y,w,h,rgb=(.93,.96,.98)):
 c.setFillColorRGB(*rgb);c.roundRect(x,y,w,h,8,fill=1,stroke=0)
def header(title,page):
 c.setFillColorRGB(.07,.17,.27);c.rect(0,H-102,W,102,fill=1,stroke=0)
 line(38,H-43,'RESCUEMIND  /  PHYSICAL AI 2026',13,(1,1,1))
 line(38,H-76,title,16,(1,1,1))
 line(40,31,'v1.8  •  2026-10-16  •  DRAFT／未提出・実Gazebo未検証',8.5)
 line(W-80,31,f'{page} / 3',9)
def section(y,cap,items):
 line(39,y,cap,12,(.03,.29,.55));y-=25
 for s in items:
  line(45,y,'・'+s,9.3);y-=20
 return y-18
header('課題目的・創造性・システム設計',1)
y=H-145
y=section(y,'課題文（10/8版）から確認した要件',[
 '評価：創造性・技術力・実用性・表現力。数値配点は未公表。',
 'AI活用必須。60〜180秒のロボット実行動画＋public GitHub＋PDF。',
 '締切：2026年11月2日 10:00 JST。個人情報・秘密情報の提出は禁止。'])
y=section(y,'RescueMindの独自タスク',[
 '避難所への救援指示を解析し、差動二輪ロボットが物資拠点へ接近。',
 '現地カメラ画像をJev 1.14.0（必須）とQwen3.8に入力。',
 '一致・危険なしの場合のみ避難所へ移動。不一致・異常時は停止。'])
y=section(y,'正確な実装範囲',[
 '物資の把持・積載・輸送は未実装。物資拠点確認と避難所接近の課題。',
 '独自Gazeboワールドは直接目標追従。Nav2再計画は未実装。',
 'Jevの画像／Boxは実験機能。実API推論とGazebo実走行は未実行。'])
box(39,95,W-78,83)
line(54,151,'研究課題：AI判断はロボットの行動を変えるか？',12,(.05,.24,.39))
line(54,127,'比較するのは実API推論による次区間の許可／拒否と実走行ログ。',9)
line(54,109,'人工判断による分岐テストは、VLMの性能実測とは区別する。',9)
c.showPage()
header('v1.8で実装した独立観測・検証',2)
y=H-140
y=section(y,'ロボット自身の「成功」申告に依存しない二重監査',[
 '①ミッションJSON：物資拠点→現地判定→避難所の順番を検査。',
 '②別ROSノード：/odom と /cmd_vel を同じ実行IDで独立記録。',
 '③実移動の観測：始点、訪問順序、走行距離、時刻、座標系を検査。',
 '④センサー位置飛び、速度観測欠落、時刻逆行では成功を拒否。'])
y=section(y,'実行済みオフライン検証（Gazebo成功ではない）',[
 f'Pythonテスト：{REPORT["python_tests_passed"]}件、全件成功。',
 f'独立観測の人工異常ケース：{REPORT["synthetic_motion_evidence_cases"]}件、期待結果に一致。',
 f'理想運動学の閉ループ：{REPORT["scripted_closed_loop_cases"]}件、人工AI判断で想定結果に一致。',
 'Gazebo SDF、ROSブリッジの型・方向、制御接続の静的検査が通過。'])
img=ROOT/'verification/v17/v17_scripted_closed_loop.png'
if img.exists():
 c.drawImage(str(img),47,105,width=W-94,height=218,preserveAspectRatio=True,anchor='c')
line(45,87,'図：人工判断による理想運動学の閉ループ軌跡。実Gazebo動画ではない。',8.2)
c.showPage()
header('優秀賞向けの実験と必須の未検証',3)
y=H-145
y=section(y,'評価基準との対応：審査員に見せたい証拠',[
 '創造性：同一条件の「正常物資」と「不一致物資」で進行が分岐。',
 '技術力：ROSカメラ、Jev＋Qwen、独立速度ガード、走行監査。',
 '実用性：誤許可率と誤拒否率、通信異常時停止、推論待機時間。',
 '表現力：実Gazebo映像、観測画像、判断ログ、実測比較を2分で提示。'])
y=section(y,'優先実証ステップと期限',[
 '10/20まで：Ubuntu PCで本物のGazebo走行・独立オドメトリ取得。',
 '10/23まで：現地撮影からJev／Qwen実API判定の成功ログ。',
 '10/29まで：両モデルの評価データ、誤許可／誤拒否の比較、動画。',
 '10/31まで：公開GitHub、説明資料PDF、YouTube提出前チェック。'])
y=section(y,'提出前に残っている重大な未達成事項',[
 'ROS/Gazebo物理走行・実API画像推論・実動画（60〜180秒）：未確認。',
 '人工的に生成した位置ログは実ロボットの実行証拠にはならない。',
 '実行者は映像とROSノード構成を目視照合し、個人情報を消去する。'])
box(39,94,W-78,82)
line(54,149,'使用した外部一次資料（URLは同梱の調査文書に収録）',11,(.05,.24,.39))
line(54,125,'TypeSafe公式 Jev 1.14 公告／Alibaba Cloud Qwen3.8 Model Studio',9)
line(54,108,'Gazebo公式 Harmonic＋ROS Jazzy／ros_gz公式サンプル',9)
c.save();print(OUT)
