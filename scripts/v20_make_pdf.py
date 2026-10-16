#!/usr/bin/env python3
"""Produce truthful, Japanese 3-page NON-SUBMISSION report for Physical AI v2.0."""
from pathlib import Path
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
R=Path(__file__).resolve().parents[1]
D=json.loads((R/'verification/v20/V20_VERIFICATION.json').read_text())
OUT=R/'docs/RescueMind_v20_REPORT_DRAFT_NOT_SUBMISSION.pdf'
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
W,H=A4;c=canvas.Canvas(str(OUT),pagesize=A4,pageCompression=1)
c.setTitle('RescueMind v2.0 Physical AI 最終課題説明資料（未提出）')
c.setAuthor('RescueMind / anonymous draft')
FONT='HeiseiKakuGo-W5';NAVY=(.06,.15,.23);ACCENT=(.01,.34,.57)
def txt(x,y,s,n=9.2,color=NAVY):
 c.setFillColorRGB(*color);c.setFont(FONT,n);c.drawString(x,y,s)
def header(t,pg):
 c.setFillColorRGB(*NAVY);c.rect(0,H-104,W,104,fill=1,stroke=0)
 txt(42,H-39,'RESCUEMIND / PHYSICAL AI 2026',12.5,(1,1,1))
 txt(42,H-74,t,15.5,(1,1,1))
 txt(41,32,'v2.0 / 2026-10-16 / 未提出・実Gazebo・実AI推論は未検証',8.5)
 txt(W-74,32,f'{pg} / 3',9)
def section(y,head,items):
 txt(42,y,head,11.5,ACCENT);y-=29
 for item in items:txt(46,y,'・'+item,9.1);y-=23
 return y-20
def note(y,title,rows):
 c.setFillColorRGB(.92,.96,.985);c.roundRect(40,y,W-80,91,8,fill=1,stroke=0)
 txt(53,y+66,title,11,ACCENT)
 for i,row in enumerate(rows):txt(53,y+45-21*i,row,9)
header('目的・研究課題・実装の範囲',1)
y=H-148
y=section(y,'課題原文の評価・提出条件',[ '創造性、技術力、実用性、表現力の4項目を加点評価。', '提出：実ロボット動画60〜180秒、public GitHub、PDF資料。', '締切：2026年11月2日（月）AM10:00。個人情報を含めない。'])
y=section(y,'RescueMind：現地の画像理解から行動分岐へ',[ '日本語指示で物資ステーションへ接近し、ROSカメラで撮影。', 'Jev 1.14.0（必須）＋Qwen3.8が物資を確認。', '条件が揃えば避難所Bへ接近、不一致・不確実なら停止。'])
y=section(y,'厳密な実装範囲と制約',[ '差動二輪の直接走行。Nav2による再計画は未検証。', '把持・積載・物資の実際の配送は未実装。', 'Jevの画像・Box機能は実験的で、実認識精度は未検証。'])
note(99,'検証したい因果関係',['新しい現地画像でAIが許可した後だけ、次区間へ進んだか？','独立ROS軌跡・時計・動画を照合して検証する。'])
c.showPage()
header('v2.0の技術改善とオフライン検証',2)
y=H-148
y=section(y,'発見した不備：GazeboとROSの時計ブリッジ',[ 'v1.9はシミュレーション用 /clock を明示的に橋渡ししていなかった。', 'v2.0は /world/rescuemind_arena/clock をROS /clockへ中継。', 'ホスト単調時刻・Unix時刻とセンサのシミュレーション時刻を区別。'])
y=section(y,'新しい時刻整合性ゲートとrosbag2',[ 'カメラ、LiDAR、オドムのstampがROS /clockと整合するか検査。', '時計停止・逆行・欠落・Unix秒との混在を拒否する。', 'ROS bagは --use-sim-time と /clock の収録を要求。'])
y=section(y,'実行した検証結果（実モデル推論ではない）',[ f'Pythonテスト {D["python_tests_passed"]}件：全件通過。', '人工の因果時系列10条件、理想運動学の閉ループ6条件。', '速度・カメラ・センサー等の旧故障注入も再実行。', '新ブリッジ5件の型・方向・ワールド名を静的確認。'])
img=R/'verification/v19/v19_synthetic_causal_timeline.png'
if img.exists():c.drawImage(str(img),50,97,width=W-100,height=162,preserveAspectRatio=True,anchor='c')
txt(46,78,'図：旧v1.9の合成時系列検証。実Gazeboの撮影画像ではない。',8.5)
c.showPage()
header('優秀賞戦略・外部実証と残る作業',3)
y=H-148
y=section(y,'課題の4評価基準に対して示す実際の証拠',[ '創造性：同一指示で現地物資が異なると行動が変わる動画。', '技術力：Jev/Qwen判断、ROS時計、移動制御、独立観測。', '実用性：実画像で偽許可・偽拒否・保留・遅延を比較。', '表現力：実Gazebo映像・カメラ画像・数値を2分で説明。'])
y=section(y,'10/16時点での実行状況とリスク',[ 'Pythonオフライン試験・静的検証・計画確認：成功。', 'Ubuntu実Gazebo走行／時計配信／rosbag保存：未検証。', '実Jev・実Qwen推論と実画像の統計評価：未検証。', '最終課題の60〜180秒ロボット動画：未完成。'])
y=section(y,'予定する実証ゲート',[ '10/20：実Gazebo上の車輪とROS /clockを先に確認。', '10/23：現地のJev・Qwen実推論を1件ずつ検証。', '10/29：正常／拒否動画と実画像比較の数値を固定。', '11/1：GitHub・PDF・YouTube・omnicampus提出を確認。'])
note(95,'根拠となる公開一次資料',['TypeSafe Jev 1.14／Alibaba Cloud Qwen3.8 公式資料','Gazebo Harmonic ROS 2 integration／rosbag2 README'])
c.save();print(OUT)
