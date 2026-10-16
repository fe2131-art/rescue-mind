#!/usr/bin/env python3
"""Generate a truthful unsubmitted Japanese 3-page course report."""
from pathlib import Path
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
R=Path(__file__).resolve().parents[1]
D=json.loads((R/'verification/v19/v19_TEST_REPORT.json').read_text())
OUT=R/'docs/RescueMind_v19_REPORT_DRAFT_NOT_SUBMISSION.pdf'
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
W,H=A4;c=canvas.Canvas(str(OUT),pagesize=A4,pageCompression=1)
c.setTitle('RescueMind v1.9 Physical AI 最終課題説明資料（未提出）')
c.setAuthor('RescueMind / no personal author information')
FONT='HeiseiKakuGo-W5'; NAVY=(.065,.16,.24); ACCENT=(.025,.37,.58)
def txt(x,y,s,n=9.2,color=NAVY):
 c.setFillColorRGB(*color);c.setFont(FONT,n);c.drawString(x,y,s)
def header(t,pg):
 c.setFillColorRGB(*NAVY);c.rect(0,H-108,W,108,fill=1,stroke=0)
 txt(42,H-39,'RESCUEMIND  /  PHYSICAL AI 2026',13,(1,1,1))
 txt(42,H-74,t,16,(1,1,1))
 txt(40,32,'v1.9 / 2026-10-16 / ドラフト・未提出・実Gazebo未検証',8.5)
 txt(W-74,32,f'{pg} / 3',9)
def section(y,head,items):
 txt(42,y,head,12,ACCENT);y-=28
 for item in items:
  txt(46,y,'・'+item,9.25);y-=22
 return y-22
def note(y,title,rows):
 c.setFillColorRGB(.92,.96,.985);c.roundRect(39,y, W-78,89,9,fill=1,stroke=0)
 txt(54,y+64,title,11.5,ACCENT)
 for i,line in enumerate(rows):txt(54,y+44-i*21,line,9.0)
header('目的・提案システム・独自性',1)
y=H-145
y=section(y,'講座課題文からの必須条件',[
 'AI×ロボティクス。創造性・技術力・実用性・表現力を評価。',
 '60〜180秒のロボット実行動画、PDF、public GitHubが必要。',
 '2026年11月2日（月）10:00 JST締切。個人情報・秘密情報を除外。'])
y=section(y,'RescueMind：現地VLM判断で走行の可否を分岐',[
 '日本語の救援依頼を解析し、差動二輪ロボットが物資拠点へ接近。',
 '現地のROSカメラをJev 1.14.0（必須）とQwen3.8で検証。',
 '一致かつ安全条件を満たせば避難所Bへ移動。異常時は停止。'])
y=section(y,'作品の正確な実装範囲',[
 '把持・積載・実物運搬は未実装。目的は拠点確認と避難所接近。',
 '独自Gazeboワールドの直接走行。Nav2再計画ではない。',
 'Jev画像／Boxは実験的機能であり安全性能の保証はない。'])
note(98,'研究上の問い',[ '現地でのAI許可が「次の区間の移動」に反映されたか？',
 'モデル単独と二重判定の誤許可・誤拒否を実画像で比較する。'])
c.showPage()
header('v1.9の技術的な改善・オフライン検証',2)
y=H-145
y=section(y,'行動とAI許可の因果関係を厳密に監査',[
 '①ミッション時刻をホストUnix時刻へ固定して記録。',
 '②独立ROS観測と許可時刻を照合し、許可前の移動を拒否。',
 '③許可前の拠点停車と、許可後の避難所到着を要求。',
 '④任意でrosbag2を保存し、保存トピックとファイルを検査。'])
y=section(y,'実行できた検証と、主張できる範囲',[
 f'Python単体テスト：{D["python_unittest_passed"]}件、すべて通過。',
 '人工的な認可／移動時系列：10条件、期待結果と一致。',
 '理想運動学による閉ループ：6条件、期待結果と一致。',
 'センサー・速度・AI判定の人工故障試験も再実行。'])
img=R/'verification/v19/v19_synthetic_causal_timeline.png'
if img.exists():c.drawImage(str(img),47,98,width=W-94,height=215,preserveAspectRatio=True,anchor='c')
txt(45,82,'図：許可前の移動を拒否する人工時系列。実Gazebo映像ではない。',8.0)
c.showPage()
header('優秀賞向けの評価設計・未完了の実証',3)
y=H-145
y=section(y,'4つの加点要素に対応する「実データ」',[
 '創造性：物資が一致／不一致の場合で次の行動が変わる動画。',
 '技術力：ROSとJev/Qwenの判断ログ、許可時刻と独立軌跡。',
 '実用性：誤許可・誤拒否、保留、推論時間を実画像で検証。',
 '表現力：2分の実Gazebo映像、軌跡、比較値を一体で説明。'])
y=section(y,'推奨進行日程（達成保証ではない）',[
 '10/20まで：Ubuntu PCでGazebo／ROS車輪走行を検証。',
 '10/23まで：現地Jev・Qwen実API認識を実行。',
 '10/29まで：実画像比較、正常／不一致動画、実ログ。',
 '10/31まで：PDF・公開GitHub・YouTubeと提出確認。'])
y=section(y,'重大な未検証・注意事項',[
 '実際のGazebo物理走行・Jev/Qwen実API：未検証。',
 '60〜180秒の実ロボット動画：未完成。人工結果は代替不可。',
 'rosbag・独立ROSトピックも物理環境の真正性を保証しない。'])
note(94,'外部一次資料（完全なURLは同梱文書）',[
 'TypeSafe Jev 1.14／Alibaba Cloud Qwen3.8 Model Studio',
 'Gazebo Harmonic ROS2 bridge／ROS 2 rosbag2公式仕様'])
c.save();print(OUT)
