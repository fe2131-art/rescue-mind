#!/usr/bin/env python3
"""Create a three-page Japanese PDF DRAFT from source-grounded statements."""
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/RescueMind_v16_REPORT_DRAFT_NOT_SUBMISSION.pdf'
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
W,H=A4
c=canvas.Canvas(str(OUT),pagesize=A4,pageCompression=1)
c.setTitle('RescueMind v1.6: Physical AI 最終課題説明資料（ドラフト）')
c.setAuthor('RescueMind / Anonymous')
FONT='HeiseiKakuGo-W5'
def text(x,y,s,size=10):
    c.setFont(FONT,size);c.drawString(x,y,s)
def header(title,num):
    c.setFillColorRGB(.075,.15,.24)
    c.rect(0,H-96,W,96,fill=1,stroke=0)
    c.setFillColorRGB(1,1,1)
    text(42,H-46,'RESCUEMIND  /  PHYSICAL AI FINAL PROJECT',11)
    text(42,H-74,title,18)
    c.setFillColorRGB(.15,.22,.29)
    text(42,36,'v1.6 | 2026-10-16 | 未提出・実機相当検証未完了',9)
    text(W-85,36,f'{num} / 3',9)
def block(y,heading,lines):
    c.setFillColorRGB(.10,.28,.47);text(43,y,heading,12)
    y-=26
    c.setFillColorRGB(.15,.22,.29)
    for a in lines:
        text(48,y,'・'+a,10);y-=21
    return y-18
header('課題背景と提案方式',1)
y=H-130
y=block(y,'課題（原文10/8版）',['AI×ロボティクスによる創造的なタスクを設計・実装する。','創造性・技術力・実用性・表現力が加点対象。','1〜3分のロボット実行動画、PDF、public GitHub URLが必要。'])
y=block(y,'提案：RescueMind',['救援指示から物資拠点を選び、ロボットが拠点に接近する。','現地カメラ画像をJev 1.14.0とQwen3.8で個別判断する。','両モデルが妥当性を確認した場合のみ避難所へ移動する。','不一致・センサー異常・判断不能の場合には停止する。'])
y=block(y,'実装で守る説明の正確性',['把持・物資の物理配送は未実装。成果は拠点確認と避難所接近。','Nav2の動的再計画ではなく独自差動二輪の目標追従を主に使用。','現時点でGazeboでの車輪駆動とJev/Qwen実APIは未検証。'])
c.showPage()
header('アーキテクチャと検証',2)
y=H-130
y=block(y,'構成',['Gazebo Harmonic：物資・避難所・カメラ/LiDAR付き移動ロボット。','ROS 2 Jazzy：カメラ、測距、Odometry、Twist通信。','Jev + Qwen3.8：現地の対象物・危険の二重判断。','独立速度ガード：新鮮な観測・速度指令がなければゼロ速度。'])
y=block(y,'今回v1.6の改善',['OdometryのNaN・姿勢・フレーム・timestamp異常を継続検査。','supervisorの子プロセス終了時に、成功ログの条件を再検査。','run_idを統一し、撮影画像・現地判断・到着イベントを対応付け。'])
y=block(y,'この環境で実行したオフライン検証',['Python自動テスト：198件、全件成功。','新しい人工Odometry故障注入：600ケース、全件期待値と一致。','Gazebo SDF静的構造・理想運動学・シェル構文の検証成功。','上記は認識精度やGazeboの物理走行成功率を意味しない。'])
c.showPage()
header('研究的価値・残課題・提出準備',3)
y=H-130
y=block(y,'計測予定の比較実験',['同じ画像をJev単体・Qwen単体・二重判定に入力する。','誤許可率・誤拒否率・判断時間・停止理由を保存する。','成功場面だけでなく、不一致・センサー停止の失敗例も示す。'])
y=block(y,'優秀賞の4評価基準に対する構成',['創造性：認識状況に応じてロボット行動が分岐する。','技術力：AIとセンサー監視、独立ガード、ROS制御の結合。','実用性：誤許可・不要な停止のトレードオフを実測する。','表現力：実走行とAI判断を同じ2分動画内で対応付ける。'])
y=block(y,'実環境で未完了の工程',['Ubuntu上でのGazebo実走行とROS-GZブリッジ動作確認。','Jev/Qwen実API推論、実画像の人手ラベル付き比較実験。','60〜180秒の実ロボット動画、実測値入りPDF、公開GitHub。'])
text(45,92,'※提出前に実際の測定値へ差し替え、個人情報がないことを確認する。',9)
c.save()
print(OUT)
