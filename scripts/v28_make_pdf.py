#!/usr/bin/env python3
"""Three-page Japanese draft. NOT submission-ready until real Gazebo/API video is recorded."""
from pathlib import Path
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
R=Path(__file__).resolve().parents[1]
V=json.loads((R/'verification/v28/verification.json').read_text())
OUT=R/'docs/RescueMind_v28_REPORT_DRAFT_NOT_SUBMISSION.pdf'
OUT.parent.mkdir(parents=True,exist_ok=True)
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
W,H=A4;c=canvas.Canvas(str(OUT),pagesize=A4,pageCompression=1)
c.setTitle('RescueMind v2.8 | PAI最終課題（未提出ドラフト）')
c.setAuthor('RescueMind - Personal information omitted')
D=(.10,.18,.27);B=(.10,.34,.43);G=(.32,.38,.43);P=(.93,.96,.97);WHITE=(1,1,1)
def txt(x,y,s,size=9,color=D):
 c.setFillColorRGB(*color);c.setFont('HeiseiKakuGo-W5',size);c.drawString(x,y,str(s))
def header(title,subtitle,num):
 c.setFillColorRGB(*D);c.rect(0,H-124,W,124,stroke=0,fill=1)
 txt(34,H-44,'RESCUEMIND  /  PHYSICAL AI 2026',15,WHITE)
 txt(34,H-85,title,13,WHITE)
 txt(34,H-146,subtitle,8.8,B)
 c.setStrokeColorRGB(.8,.84,.88);c.line(36,42,W-36,42)
 txt(36,24,'v2.8  |  2026-10-16  |  未提出・実Gazebo/実API未検証',7.4,G)
 txt(W-76,24,f'{num} / 3',8,G)
def block(y,title,lines):
 txt(38,y,title,10.7,B);y-=27
 for line in lines:
  txt(47,y,'・'+line,8.6);y-=23
 return y-15
def panel(y,title,lines):
 ht=45+len(lines)*22
 c.setFillColorRGB(*P);c.roundRect(36,y-ht,W-72,ht,8,stroke=0,fill=1)
 txt(47,y-25,title,10,B)
 for i,l in enumerate(lines):txt(49,y-52-i*22,l,8.6)
 return y-ht-22
header('AI×ロボティクスによる創造的タスク','作品：RescueMind｜現地画像の二重AI確認から条件付き移動',1)
y=H-180
y=block(y,'課題原文（10/8版）の要件',[ 
 'AI技術を活用し、ロボットがタスクを実行することが必須。',
 '創造性・技術力・実用性・表現力が加点対象。',
 '動画1〜3分、GitHub public全コード、説明資料PDFを提出。'])
y=panel(y,'本作品が実装しているタスク',[ 
 '自然言語指示→差動二輪ロボットが物資拠点へ移動。',
 '物資棚へ向きを変え、実測の静止状態を確認。',
 '新しいROS画像2枚を品質・時刻で検査し、Jev＋Qwenへ入力。',
 '両モデル一致で避難所へ接近。不一致・異常なら停止。'])
y=block(y,'v2.8の独自性と技術上の工夫',[ 
 'Gazebo /clock と画像取得時刻を独立照合するゲートを追加。',
 '時刻だけ進む遅延画像も拒否し、古い現場観測で進まない。',
 'ROSオドメトリ・速度ガード・監査ログを組み合わせて検証。'])
y=panel(y,'誇張しない実装範囲',[ 
 '物資の実把持・輸送は行わず、物資拠点確認と避難所への接近のみ。',
 'Nav2動的再計画や実シミュレータ走行成功は未証明。'])
c.showPage()
header('視野・静止・時刻・AIの検証','単に画像を受信しただけでは、現場で撮影したとは限らない',2)
items=[('拠点到着','ROS駆動'),('棚へ視線','角度一致'),('静止・2枚','速度／画質'),('時計照合','/clock'),('Jev＋Qwen','一致を要求')]
left=36;gap=7;bw=(W-72-4*gap)/5
for i,(a,b) in enumerate(items):
 x=left+i*(bw+gap);yt=H-190
 c.setFillColorRGB(*(P if i%2==0 else (.87,.94,.96)))
 c.roundRect(x,yt-85,bw,85,6,stroke=0,fill=1)
 txt(x+5,yt-31,a,8.4,B);txt(x+5,yt-57,b,7.3,G)
 if i<4:txt(x+bw+1,yt-46,'→',8,B)
y=H-317
y=block(y,'今回実際に行ったオフライン検証',[ 
 f'Python単体・統合テスト：{V["python_tests"]}件／{V["python_tests"]}件成功。',
 f'時計異常人工キャンペーン：{V["new_sim_clock_fault_conditions"]}件／{V["new_sim_clock_fault_matched"]}件一致。',
 '旧バージョンの静止・画像品質・拒否停止の回帰テストも成功。',
 'Gazebo 3シーンとROSブリッジ設定の静的監査が成功。'])
y=panel(y,'新規時計ゲート（未校正の工学的初期値）',[ 
 '画像取得時刻は最新Gazebo時計から最大1.2秒遅延まで。',
 '未来時刻の許容は0.25秒まで。時計前進停止0.9秒超は拒否。',
 '時計逆行・画像スタンプ不整合・監査イベント欠落も拒否。',
 '映像やROS graphの真正性を暗号学的に保証するものではない。'])
y=block(y,'証拠の独立性',[ 
 'ミッションのAI許可時刻と、別ノードのROSオドメトリを照合。',
 '正常なAI拒否をAPI障害から分離。実験ID／シーンハッシュを保存。'])
c.showPage()
header('実証・提出に向けた最終工程','実走行・実API・動画完成が優秀賞への最大の次工程',3)
y=H-179
y=block(y,'Ubuntu実機で最優先に行うこと',[ 
 '1. ROS 2 Jazzy / Gazebo Harmonicでmotion-checkを完走。',
 '2. /clock・/camera・/odom・/scan の実トピックを確認。',
 '3. nominalでJev＋Qwenが実画像から許可し避難所へ接近。',
 '4. swapped / emptyで実AI拒否と2.5秒以上の静止を確認。',
 '5. 事前登録30試行の実測・推論時間・誤許可率を集計。'])
y=panel(y,'提出動画の構成案（合計約105秒・未撮影）',[ 
 '0〜15秒：現場課題と自然言語指示を紹介。',
 '15〜50秒：正常シーンの実Gazebo走行と実AI判定。',
 '50〜80秒：誤物資・欠品シーンでの実停止。',
 '80〜105秒：ROSの独立証拠、結果比較、限界を説明。'])
y=block(y,'締切・個人情報・公開設定',[ 
 '2026年11月2日（月）午前10時までにOmniCampusへ提出。',
 'PDF名：説明資料_PAI最終課題_omnicampusアカウント名.pdf',
 'GitHub public、YouTube最低限定公開（公開推奨）。',
 '氏名・所属・メール・APIキーを動画／レポートへ載せない。'])
y=panel(y,'現在の到達点と正確な限界',[ 
 f'オフライン自動テスト{V["python_tests"]}件と人工時計故障14条件は成功。',
 '実Gazeboの物理走行・Jev実API・Qwen実APIは未検証。',
 'YouTube動画、公開GitHub、提出用PDFは現時点では未完成。'])
c.showPage();c.save()
print(OUT)
