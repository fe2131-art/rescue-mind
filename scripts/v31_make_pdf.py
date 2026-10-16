#!/usr/bin/env python3
"""Generate the 3-page award report DRAFT; not a submission or live result."""
from pathlib import Path
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
R=Path(__file__).resolve().parents[1]
V=json.loads((R/'verification/v31/verification.json').read_text())
OUT=R/'docs/RescueMind_v31_REPORT_DRAFT_NOT_SUBMISSION.pdf'
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
W,H=A4;c=canvas.Canvas(str(OUT),pagesize=A4,pageCompression=1)
c.setTitle('RescueMind v3.1 Physical AI final award report DRAFT')
D=(.09,.17,.26);B=(.09,.31,.43);G=(.32,.40,.44);P=(.93,.965,.975);WHITE=(1,1,1)
def text(x,y,s,size=9,color=D):
 c.setFillColorRGB(*color);c.setFont('HeiseiKakuGo-W5',size);c.drawString(x,y,str(s))
def header(title,desc,page):
 c.setFillColorRGB(*D);c.rect(0,H-113,W,113,fill=1,stroke=0)
 text(35,H-42,'RESCUEMIND  /  PHYSICAL AI 2026',14,WHITE)
 text(35,H-78,title,12.4,WHITE)
 text(35,H-134,desc,8.5,B)
 c.setStrokeColorRGB(.78,.84,.87);c.line(35,42,W-35,42)
 text(35,25,'v3.1  |  2026-10-16  |  未提出：実Gazebo・実API未検証',7.3,G)
 text(W-69,25,f'{page} / 3',8,G)
def bullets(y,title,lines):
 text(38,y,title,10.6,B);y-=23
 for t in lines:
  text(45,y,'・'+t,8.25);y-=22
 return y-15
def box(y,title,lines):
 h=41+23*len(lines)
 c.setFillColorRGB(*P);c.roundRect(35,y-h,W-70,h,7,fill=1,stroke=0)
 text(46,y-27,title,10,B)
 for j,t in enumerate(lines):text(46,y-53-23*j,t,8.15)
 return y-h-24
header('AI×ロボティクスによる創造的タスク','自然言語 → 物資拠点 → 現地AI判定 → 接近／拒否・停止',1)
y=H-170
y=bullets(y,'課題文の目的・評価基準・提出条件',[ 'AI使用必須。創造性・技術力・実用性・表現力が加点要素。', '動画60〜180秒、実装コード、説明PDF、public GitHub／YouTube URL。', '提出締切 2026年11月2日（月）AM10:00。'])
y=box(y,'RescueMind：取り組んだタスク',[ 'ROS2 Jazzy＋Gazebo Harmonicの差動二輪ロボットが棚へ向かう。', 'カメラ方向制御、静止検証、画像2枚の時刻／画質検査。', 'Jev 1.14.0必須＋Qwen3.8で判断し、許可のみ避難所へ接近。', '物資を物理的に持ち上げる・運搬する機能は未実装。'])
y=bullets(y,'v3.1で発見した課題',[ '走行前は安全ガードの発行元を調べるが、走行中は追跡していなかった。', '別Publisherが直接 /cmd_velを送れば、ガードを迂回し得る。'])
y=box(y,'今回実装した改善',[ '独立ROSグラフ監視で発行元数・ノード名・型を継続検査。', '想定外Publisherは緊急停止要求＋監視ノード非ゼロ終了。', '成功・正常なAI拒否の両経路で監視証拠を必須化。'])
c.showPage()
header('走行中の安全制御と実行証拠','ROSグラフ監視は診断機構。安全認証や認証済Publisherではない',2)
labels=[('ROS / Gazebo','状態観測'),('速度ガード','唯一の出力'),('Graph Watch','0.2秒監視'),('異常時','ESTOP要求'),('証拠監査','成功判定')]
col=(W-72-4*7)/5
for i,(t,s) in enumerate(labels):
 x=35+i*(col+7);y=H-181
 c.setFillColorRGB(*(P if i%2==0 else (.87,.94,.96)));c.roundRect(x,y-81,col,81,6,fill=1,stroke=0)
 text(x+7,y-30,t,8.2,B);text(x+7,y-56,s,7.7,G)
y=H-294
y=bullets(y,'オフラインで検証できた内容',[ f'Pythonの自動テスト {V["unit_tests"]}件が全件成功。', f'新規Graph発行元の人工異常 {V["v31_synthetic_graph_matched"]}／{V["v31_synthetic_graph_conditions"]}条件が期待動作に一致。', '既存のROS bag終了・Jev＋Qwen判定・撮影・時計ゲートを回帰検査。', '3つのSDFシーンと4種類のオフライン起動計画を検査。'])
y=box(y,'走行中の発行者トポロジーを監視',[ '通常：/cmd_vel はrescuemind_velocity_guard 1件だけ。', '加えて /rescuemind/guard_ready も同ノードの1件だけ。', '異常：重複・消失・名前空間違い・型違い・時刻逆行でラッチ。', '監視ログに正常確認が継続していなければ成功扱いしない。'])
y=bullets(y,'監査の限界',[ 'グラフ情報は暗号学的なPublisher認証ではない。', '直接Gazebo Transportへ送信する外部ノードは検出対象外。', '実ROS上での200ms監視・緊急停止の効果は未測定。'])
c.showPage()
header('優秀賞へ向けた実証・動画・提出','オフライン検査を作品の実動作と取り違えず、実測と映像で示す',3)
y=H-172
y=bullets(y,'Ubuntuの実環境で確認すべき順序',[ '1. ROS 2 Jazzy・Gazebo HarmonicでAIなしのmotion-checkを完走。', '2. Graph WatchのログとGazeboの走行画面を比較。', '3. Jev＋Qwenのnominalでの許可と避難所への接近を実行。', '4. swapped・emptyで現地認識による拒否と静止を確認。', '5. 事前固定の30試行について実測のみを統計比較。'])
y=box(y,'動画構成：想定110秒（未撮影）',[ '0〜15秒：災害時の物資確認とタスクの狙い。', '15〜53秒：正常シーン、移動、撮影、二重AI許可。', '53〜80秒：誤物資・欠品での停止を比較。', '80〜99秒：実ROS /cmd_vel・監視ログ・独立走行証拠。', '99〜110秒：実測結果と把持・運搬未実装の説明。'])
y=bullets(y,'必要な提出物と公開時の注意',[ '説明PDFは指定ファイル名、GitHubはpublic。', '動画はMP4、YouTubeは最低限定公開。倍速なら明記。', '氏名・所属・メールアドレス・APIキーを含めない。'])
y=box(y,'未完成事項を明確に報告',[ '実Gazebo物理走行、ROSグラフ監視の実接続：未検証。', 'Jev／Qwen実API推論、ROS bag実収録：未検証。', '30試行の実測データ、動画1〜3分：未完成。'])
c.showPage();c.save()
print(OUT)
