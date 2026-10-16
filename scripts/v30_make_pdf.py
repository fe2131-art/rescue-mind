#!/usr/bin/env python3
"""Draft report, not a submission or proof of live Gazebo execution."""
import json
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
R=Path(__file__).resolve().parents[1]
V=json.loads((R/'verification/v30/verification.json').read_text())
OUT=R/'docs/RescueMind_v30_REPORT_DRAFT_NOT_SUBMISSION.pdf'
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
W,H=A4; c=canvas.Canvas(str(OUT),pagesize=A4,pageCompression=1)
c.setTitle('RescueMind v3.0 — PAI final draft not submitted')
D=(.10,.18,.27);B=(.10,.31,.41);G=(.31,.39,.44);P=(.94,.965,.97);White=(1,1,1)
def txt(x,y,s,size=9,color=D):
 c.setFillColorRGB(*color);c.setFont('HeiseiKakuGo-W5',size);c.drawString(x,y,str(s))
def header(t,sub,p):
 c.setFillColorRGB(*D);c.rect(0,H-116,W,116,fill=1,stroke=0)
 txt(36,H-45,'RESCUEMIND  /  PHYSICAL AI 2026',14,White)
 txt(36,H-81,t,13,White)
 txt(36,H-138,sub,8.5,B)
 c.setStrokeColorRGB(.80,.84,.85);c.line(36,44,W-36,44)
 txt(36,25,'v3.0  |  2026-10-16  |  未提出／実Gazebo・実AI未検証',7.2,G)
 txt(W-65,25,f'{p} / 3',8,G)
def block(y,title,items):
 txt(38,y,title,10.3,B);y-=25
 for s in items:txt(45,y,'・'+s,8.4);y-=22
 return y-16
def panel(y,title,items):
 h=40+len(items)*22
 c.setFillColorRGB(*P);c.roundRect(35,y-h,W-70,h,8,fill=1,stroke=0)
 txt(47,y-27,title,10,B)
 for i,s in enumerate(items):txt(48,y-53-i*22,s,8.35)
 return y-h-26
header('AI×ロボティクスによる創造的タスク','RescueMind：物資の現地確認後に、AI許可で避難所へ接近',1)
y=H-170
y=block(y,'課題原文（10/8版）の要件',[ 'AI必須、ロボットによるタスクの実行動画（1〜3分）。', '創造性・技術力・実用性・表現力が加点対象。', 'コード一式、説明PDF、GitHub public、YouTube URLを提出。'])
y=panel(y,'作品の動作と物理的な限界',[ '自然言語→物資拠点へ走行→棚へ向けて静止。', 'ROSカメラの新規画像2枚・画質・Gazebo時計を検査。', 'Jev 1.14.0＋Qwen3.8の二重判定で進む／停止。', '荷物の把持・運搬やNav2動的再計画は未実装。'])
y=block(y,'v3.0の改良点',[ '成功/拒否の両経路でbagをSIGINT終了後、metadata監査。', '欠品シーンではJevへ存在しない物体のBox座標を要求しない。', 'モデル不一致・異常終了を正常なAI拒否と分離する。'])
y=panel(y,'結果の正直な表記',[ '本資料は提出前ドラフト。実Gazebo／実APIの成功を主張しない。', '人工故障テストは現実の認識精度や安全保証を意味しない。'])
c.showPage()
header('改善の検証と証拠の独立性','ロボットの自己申告だけではなく、別プロセスと録画の根拠を残す',2)
cols=[('Gazebo/ROS','センサー'),('棚へ向く','静止する'),('画像2枚','/clock照合'),('Jev+Qwen','一致を要求'),('ROS bag','終了後監査')]
left=36;gap=7;bw=(W-72-4*gap)/5
for i,(a,b) in enumerate(cols):
 x=left+i*(bw+gap);yy=H-183
 c.setFillColorRGB(*(P if i%2==0 else (.87,.94,.96)));c.roundRect(x,yy-79,bw,79,6,fill=1,stroke=0)
 txt(x+7,yy-29,a,8.6,B);txt(x+7,yy-54,b,7.7,G)
y=H-300
y=block(y,'オフラインで実行した検証',[f'Pythonテスト：{V["python_tests"]}件、全件成功。',
 f'Jev＋Qwen人工分類10条件：{V["v29_jev_synthetic_matched"]}/10で期待結果と一致。',
 '新規10条件の模擬起動＋子プロセスSIGINTで両経路を確認。',
 '3つのSDFシーン、4つの起動計画と旧回帰試験も確認。'])
y=panel(y,'従来の問題とv3.0の対策',[ '以前：正常AI拒否経路で録画の終了成否を検証せず。', '修正：成功/拒否の両経路で正常終了を待機。強制終了は失敗。', '追加：実行計画は独立収録器と実run_idの全コマンドを記録。', '維持：Jevのchoice/noul＋Qwen一致。Box診断は別実験。'])
y=block(y,'実行証拠の条件',[ '独立ROS/odom・/cmd_vel、ミッションID、AI許可時刻を照合。', '拒否時は継続静止を確認し、通信障害とは区別する。'])
c.showPage()
header('優秀賞に向けた次の実証と提出','技術的な準備から、実動画・実測で説得力を高める段階へ',3)
y=H-175
y=block(y,'Ubuntu＋Gazeboで実際に確認する順序',[ '1. 非AI motion-checkを走らせ、bag metadataを最終化。', '2. nominalで実Jev＋Qwenが物資を許可し避難所へ接近。', '3. swappedとemptyで実AIが拒否し、現地停止を確認。', '4. 30試行の実APIデータ・誤許可／誤拒否・推論時間を集計。', '5. 独立オドメトリと実Gazebo動画のタイムラインを突合。'])
y=panel(y,'動画構成案：約110秒（未撮影）',[ '0〜15秒：問題設定、タスク、2つのAIを説明。', '15〜55秒：実Gazeboで正常シーン、二重AI判断、接近。', '55〜85秒：誤物資・欠品での実停止を対比。', '85〜110秒：ROS bag・停止証拠、実測と限界を提示。'])
y=block(y,'提出前チェック',[ '2026年11月2日（月）10:00 JSTまで。', 'PDF名：説明資料_PAI最終課題_omnicampusアカウント名.pdf', 'GitHub public URL／YouTube 1〜3分MP4 URL／OmniCampus提出。', '氏名・所属・メール・APIキー・画面通知を提出物から除去。'])
y=panel(y,'未検証のまま記載する事項',[ '実Gazebo・Jev本番API・Qwen本番API・rosbag実録画は未検証。', '事前登録30試行は計画であり、認識精度の実測データではない。', '実動画と公開GitHubの提出作業は未完了。'])
c.showPage();c.save()
print(OUT)
