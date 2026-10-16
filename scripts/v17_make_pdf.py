#!/usr/bin/env python3
"""Generate a Japanese project report DRAFT, with actual offline claims only."""
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/RescueMind_v17_REPORT_DRAFT_NOT_SUBMISSION.pdf'
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
c=canvas.Canvas(str(OUT),pagesize=A4,pageCompression=1)
W,H=A4
FONT='HeiseiKakuGo-W5'
c.setTitle('RescueMind v1.7 最終課題 説明資料ドラフト（実API・実Gazebo未検証）')
c.setAuthor('RescueMind')
def txt(x,y,s,size=10,rgb=(.12,.19,.27)):
 c.setFillColorRGB(*rgb);c.setFont(FONT,size);c.drawString(x,y,s)
def pageheader(name,n):
 c.setFillColorRGB(.06,.16,.28);c.rect(0,H-105,W,105,fill=1,stroke=0)
 txt(38,H-46,'RESCUEMIND | PHYSICAL AI APPLIED 1',12,(1,1,1))
 txt(38,H-79,name,17,(1,1,1))
 txt(38,33,'2026-10-16 | v1.7 | DRAFT - 未提出 / Gazebo実動作未検証',9)
 txt(W-76,33,f'{n} / 3',9)
def section(y,title,lines):
 txt(40,y,title,12,(.05,.29,.52));y-=25
 for line in lines:
  txt(47,y,'・'+line,9.5);y-=19
 return y-22
pageheader('背景・タスク・独自性',1)
y=H-146
y=section(y,'講座の要求（10/8版の課題原文）',[
 'AI活用必須。創造性・技術力・実用性・表現力が加点対象。',
 '提出物：60〜180秒のロボット動画、public GitHub、説明資料PDF。',
 '締切：2026年11月2日 10:00（JST）。'])
y=section(y,'RescueMindの提案',[
 '救援依頼に応じて物資拠点に向かう差動二輪ロボット。',
 '現地画像をJev 1.14.0とQwen3.8に入力し、物資の適合を確認。',
 '許可時のみ避難所Bへ接近。不一致・危険・センサー異常では停止。',
 'Jevは必須。画像Boxは存在判定との併用が必要な実験的機能。'])
y=section(y,'物理的な制約・説明上の注意',[
 '把持・積載・運搬は未実装。物資拠点確認・避難所への接近が対象。',
 '独自GazeboワールドではNav2の再計画は未実装（直接目標追従）。',
 '実API応答とGazebo物理走行の成功は、現時点では未確認。'])
c.showPage()
pageheader('v1.7の実装・再現可能な検証',2)
y=H-140
y=section(y,'新しく実装した閉ループ検証',[
 '移動制御器＋独立速度ガード＋理想運動学を連続して実行。',
 '正常・人工AI拒否・近接障害物・速度指令途絶・カメラ途絶・Odometry途絶。',
 '6条件の期待結果がすべて一致。人工AI判断であり、実VLM推論ではない。'])
y=section(y,'回帰・構成の静的検査',[
 'Python 207件の自動テストは全件成功。',
 'SDF DiffDrive・車輪ジョイントとROSブリッジの向き／型を点検。',
 'Gazebo独自ワールドと速度ガード・起動管理の接続設定を検査。'])
img=ROOT/'verification/v17/v17_scripted_closed_loop.png'
if img.exists():
 c.drawImage(str(img),55,101,width=W-110,height=268,preserveAspectRatio=True,anchor='c')
txt(54,91,'図：人工許可／人工拒否で分岐する理想走行の軌跡。実Gazebo映像ではない。',8)
c.showPage()
pageheader('優秀賞向けの実証計画と残課題',3)
y=H-145
y=section(y,'評価基準に対応させる証拠',[
 '創造性：同一条件で、現地Jev＋Qwen判断が走行を分岐する映像。',
 '技術力：ROSトピックと制御・独立ガードの実走行ログ。',
 '実用性：人手正解付き画像で誤許可・誤拒否・推論時間を実測。',
 '表現力：成功／拒否の対照例と失敗原因を2分動画に明示。'])
y=section(y,'今後の必須実証',[
 '① Ubuntu 24.04上でROS 2・Gazeboの本物の車輪運動を確認する。',
 '② 物資拠点で新規撮影したROS画像からJevとQwenを呼ぶ。',
 '③ Jev単体・Qwen単体・合意ゲートを実画像で比較。',
 '④ 実ロボットのMP4（60〜180秒）・結果表・公開GitHubを完成する。'])
y=section(y,'一次資料・制約',[
 'Gazebo／ros_gz：Gazebo公式のROS 2連携資料に基づく。',
 'Qwen3.8：Alibaba Cloud Model Studio公式の画像入力仕様に基づく。',
 'Jev：画像・Boxの一次文書は今回直接取得できず、実API検証が必要。',
 '外部情報と実証範囲：docs/V17_PRIMARY_SOURCES_AND_STRATEGY.md参照。'])
txt(47,95,'※提出前に必ず実モデル・実Gazeboの測定結果へ置き換える。',9)
c.save()
print(OUT)
