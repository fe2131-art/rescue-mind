#!/usr/bin/env python3
"""Draft only: no Gazebo screenshot or claimed Jev/Qwen accuracy."""
from pathlib import Path
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
R=Path(__file__).resolve().parents[1]
V=json.loads((R/'verification/v26/verification.json').read_text())
OUT=R/'docs/RescueMind_v26_REPORT_DRAFT_NOT_SUBMISSION.pdf'
OUT.parent.mkdir(exist_ok=True)
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
W,H=A4
c=canvas.Canvas(str(OUT),pagesize=A4,pageCompression=1)
c.setTitle('RescueMind v2.6 PAI最終課題 説明資料（未提出・実Gazebo未検証）')
c.setAuthor('RescueMind — Personal details omitted')
DARK=(.075,.16,.24); TEAL=(.05,.36,.43); MUTED=(.37,.42,.48); PALE=(.93,.96,.97); WHITE=(1.,1.,1.)
FONT='HeiseiKakuGo-W5'
def text(x,y,label,size=9,color=DARK):
 c.setFillColorRGB(*color);c.setFont(FONT,size);c.drawString(x,y,str(label))
def header(title,sub,page):
 c.setFillColorRGB(*DARK);c.rect(0,H-120,W,120,fill=1,stroke=0)
 text(35,H-43,'RESCUEMIND   /   PHYSICAL AI 2026',15,WHITE)
 text(35,H-82,title,12,WHITE)
 text(35,H-143,sub,8.6,TEAL)
 c.setStrokeColorRGB(.8,.85,.88);c.line(35,44,W-35,44)
 text(36,25,'v2.6  |  2026-10-16  |  未提出ドラフト・実Gazebo/実API未検証',7.5,MUTED)
 text(W-71,25,f'{page} / 3',8,MUTED)
def bullet(y,head,lines):
 text(38,y,head,11,TEAL);y-=29
 for s in lines:
  text(43,y,'・'+s,9);y-=24
 return y-14
def panel(y,heading,lines):
 height=50+22*len(lines)
 c.setFillColorRGB(*PALE);c.roundRect(36,y-height,W-72,height,7,fill=1,stroke=0)
 text(50,y-27,heading,10,TEAL)
 for i,s in enumerate(lines):text(50,y-54-22*i,s,8.7)
 return y-height-25

header('AI×ロボティクスによる創造的タスク','提案作品：RescueMind ｜ 物資確認→条件付き避難所への移動',1)
y=H-179
y=bullet(y,'課題原文からの提出・評価要件',[
 'AIの利用が必須。創造性・技術力・実用性・表現力を加点評価。',
 'ロボット実行動画1〜3分、GitHub publicの全コード、PDFが必要。',
 'YouTube（最低限定公開）とOmniCampusの両方に提出。'])
y=panel(y,'プロトタイプのタスクと制御',[
 '自然言語の指示で差動二輪が物資拠点へ移動する。',
 '棚を向いて停止し、新しいROSカメラ画像を取得する。',
 'TypeSafe Jev 1.14.0＋Qwen3.8が一致した場合のみ続行。',
 '拒否時は停止。独立速度ガード・オドメトリで監視する。'])
y=bullet(y,'v2.6の技術的課題と解決',[
 'v2.5までは、向き合わせ後の「停止指令」を車体停止と同一視。',
 '新機能：実測速度と位置／姿勢変化の0.65秒連続チェック。',
 '動いているときはカメラ取得・AI推論・次区間走行を拒否。'])
y=panel(y,'発表で必ず明示する限界',[
 '実物資の把持・輸送・手渡しは行わない。',
 'Gazebo物理走行と実APIの推論は、この版では未計測。'])
c.showPage()
header('移動→静止→認識→許可の検証','二重VLM判断前の撮影姿勢と因果順序を監査',2)
# diagram: clear horizontal pipeline in blocks
stages=[('到着・向き合わせ','0.10rad以下'),('実測静止確認','0.65秒以上'),('新カメラ撮影','取得時刻・SHA'),('二重AI判断','Jev＋Qwen')]
x0=37;w=(W-74-30)/4
for i,(head,sub) in enumerate(stages):
 x=x0+i*(w+10); ytop=H-205
 c.setFillColorRGB(*(PALE if i%2==0 else (.87,.94,.95)))
 c.roundRect(x,ytop-78,w,78,7,stroke=0,fill=1)
 text(x+8,ytop-27,head,8.7,TEAL)
 text(x+8,ytop-53,sub,7.3,MUTED)
 if i<3:text(x+w+1,ytop-43,'→',10,TEAL)
y=H-317
y=bullet(y,'今回の新しい自動検証',[
 f'Python回帰・模擬ROS結合テスト：{V["python_tests"]}件、全件通過。',
 f'新しい停止・移動注入：{V["new_synthetic_stationary_conditions"]}人工条件、期待結果と一致。',
 '車体に外力を与える模擬ROS異常でAI推論を防止。',
 '正常続行・正常拒否とも撮影姿勢の監査を必須化。'])
y=panel(y,'静止を認める条件（校正前の設計値）',[
 '線速度 0.025m/s以内・角速度 0.055rad/s以内。',
 '位置ドリフト 0.020m以内・姿勢変化 0.040rad以内。',
 '取得が異なる4件以上のオドメトリ、0.65秒以上。',
 '撮影・推論中に移動を検知した場合も即座に中断。'])
y=bullet(y,'正しく評価するための注意',[
 '数値は人工検証の合格数であり、実AI正答率ではない。',
 '物資配置3条件×2物資×5反復＝30試行は「事前計画」。'])
c.showPage()
header('実証工程・提出工程','Ubuntu＋実Gazeboで「本当に動く」証拠を完成させる',3)
y=H-180
y=bullet(y,'再現可能なUbuntu作業',[
 '1. v26_verify.shで全オフラインテストを再実行。',
 '2. v26_orchestrate.pyでmotion-check：Gazeboの車輪・時計・センサー。',
 '3. nominalでJev/Qwenの本物の画像推論と避難所到着。',
 '4. swapped/emptyでAIの正常拒否と独立ROSの静止観測。',
 '5. 実測30試行、映像、PDF、public GitHubを完成。'])
y=panel(y,'動画構成案（実際に撮影する必要あり）',[
 '0～15秒：タスク紹介。15～55秒：正常シーンの一連動作。',
 '55～95秒：入れ替え／欠品シーンでの拒否と停止。',
 '95～125秒：実ログ・実測性能の比較と制約。',
 '倍速時は倍率を明記。未撮影の映像を実行結果と表示しない。'])
y=bullet(y,'提出形式と個人情報',[
 'PDF：説明資料_PAI最終課題_omnicampusアカウント名.pdf',
 'YouTubeタイトル：PAI最終課題_omnicampusアカウント名',
 'GitHub public、YouTube限定公開以上、2026年11月2日10:00締切。',
 '氏名・所属・メール・秘密鍵は公開コード・PDF・動画から除外。'])
y=panel(y,'実証のGo / No-Go',[
 'まずnominalを実Gazeboで1回完走し、swappedを1回正常拒否。',
 '物理走行・実APIが無理なら未完成と明記し、故障分析を提出。',
 'オフライン合格のみで「優秀賞確実」や「安全認証」を主張しない。'])
c.save()
print(OUT)
