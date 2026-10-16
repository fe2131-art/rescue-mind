#!/usr/bin/env python3
"""3-page visually reviewed *draft*, never masquerades as a submitted robot result."""
from pathlib import Path
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
R=Path(__file__).resolve().parents[1]
V=json.loads((R/'verification/v25/verification.json').read_text())
OUT=R/'docs/RescueMind_v25_REPORT_DRAFT_NOT_SUBMISSION.pdf'
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
W,H=A4;c=canvas.Canvas(str(OUT),pagesize=A4,pageCompression=1)
c.setTitle('RescueMind v2.5 PAI 最終課題 説明資料（未提出ドラフト）')
c.setAuthor('RescueMind Project — 個人情報非掲載')
navy=(.08,.15,.23);teal=(.0,.36,.40);grey=(.40,.44,.48);light=(.93,.96,.97)
F='HeiseiKakuGo-W5'
def t(x,y,s,size=9,color=navy):
 c.setFillColorRGB(*color);c.setFont(F,size);c.drawString(x,y,str(s))
def panel(y,title,lines):
 n=len(lines);height=39+23*n
 c.setFillColorRGB(*light);c.roundRect(34,y-height,W-68,height,7,stroke=0,fill=1)
 t(48,y-26,title,10,teal)
 for i,line in enumerate(lines):t(48,y-51-23*i,line,8.5)
 return y-height-22
def heading(title,sub,num):
 c.setFillColorRGB(*navy);c.rect(0,H-112,W,112,fill=1,stroke=0)
 t(34,H-43,'RESCUEMIND  /  PHYSICAL AI 2026',15,(1,1,1))
 t(34,H-80,title,12.3,(1,1,1))
 t(36,H-133,sub,8.5,teal)
 t(36,28,'v2.5 | 2026-10-16 | DRAFT: Gazebo実走行・実API結果は未取得',7.5,grey)
 t(W-66,28,f'{num} / 3',8,grey)
def items(y,title,lines):
 t(37,y,title,10.2,teal);y-=27
 for line in lines:t(41,y,'・'+line,8.7);y-=22
 return y-17
heading('AI×ロボティクスによる創造的タスク','提案作品：RescueMind（物資確認→避難所接近）',1)
y=H-171
y=items(y,'課題の目的と評価基準',[
 '人間の救援指示に基づき、仮想施設で物資拠点の正誤を確認する。',
 '創造性・技術力・実用性・表現力の4軸に対して実装と証拠を用意。',
 '1〜3分の実ロボット動画・公開コード・PDFレポートが提出条件。'])
y=panel(y,'提案する一連の動作',[
 '自然言語指示 → ROS 2差動二輪の物資拠点への移動',
 '新しいROSカメラ画像 → Jev 1.14.0＋Qwen3.8の判定',
 '一致・適正なら避難所へ／誤配置・欠品・異常なら停止',
 '独立速度ガード・LiDAR・オドメトリ記録で行動を監査'])
y=items(y,'v2.5で見つけた実装上の課題',[
 '従来：物資拠点到着時のカメラ向きが保証されず、誤認識の要因。',
 '改善：棚の方向へ回転 → 新しいカメラ画像 → Jev＋Qwenで判断。',
 'SDFのカメラを-0.12rad上向きに変更し、撮影前に向きを検証。'])
y=panel(y,'範囲と制約',[
 '物資の把持・積載・実際の輸送は実装していない。',
 '本バージョンの成果はソフトウェア検証であり、物理安全性を保証しない。'])
c.showPage()
heading('実装改善と実験設計','視線合わせ後の新規画像と30試行の比較',2)
y=H-170
y=items(y,'固定比較条件：3シーン×2物資×5反復＝30試行',[
 'nominal：正しい物資、swapped：誤った物資、empty：物資なし。',
 '水と医療物資、照明・経路・センサー条件を共通にして比較。',
 'seed=20261016で試行順を固定し、正解ラベルをAIから隠す。'])
y=panel(y,'追加したカメラ視線・証拠条件',[
 'camera_aim_aligned → checkpoint_frame → checkpoint_decision の順序',
 '物資中心への方位誤差 0.10 rad以下の確認後に画像を新規取得',
 '失敗時はAIを呼ばず拒否。既存の独立速度ガードは維持。',
 'SHA-256とROS撮影時刻、到着・向き合わせ・判定の順序を照合'])
y=items(y,'実行済みオフライン検証',[
 f'Python自動テスト：{V["python_tests"]}件、全件成功。',
 '人工条件・旧コードの回帰試験を新規テストと併せて実施。',
 'SDF・ROSブリッジの静的確認、3シーンの構造比較に成功。'])
y=panel(y,'研究上の注意',[
 '同一3シーンでの反復は独立な未知環境の性能保証ではない。',
 'モデル単独／二重モデルの優越性は実API結果が出るまで未確定。'])
c.showPage()
heading('実証・提出の工程','Ubuntu＋NVIDIA GPUでの次の最小ステップ',3)
y=H-170
y=items(y,'Ubuntu実証の順番',[
 '1. v25_verify.shでオフライン一括テストを再現。',
 '2. motion-checkで実Gazeboの車輪・カメラ・LiDAR・時計を確認。',
 '3. Jev/Qwenの実画像推論を確認し、認識失敗例も保存。',
 '4. 事前登録IDと実行フォルダを厳密に紐付ける。',
 '5. 受賞用動画と実測結果をPDFに置き換える。'])
y=panel(y,'提出要件を漏らさない',[
 '動画は60〜180秒（倍速は倍率を明記）、YouTube限定公開以上。',
 'GitHub publicに使用コードを置き、OmniCampusへURLを提出。',
 'PDF名：説明資料_PAI最終課題_omnicampusアカウント名.pdf',
 '氏名・所属・メール・APIキーをコード／レポート／映像に含めない。',
 '締切：2026年11月2日（月）午前10時（JST）。'])
y=items(y,'実証前に主張しないこと',[
 '実Gazeboの走行成功、Jev/Qwen実APIの精度、実画像の誤許可率。',
 '30試行を実行したという主張、完成済みMP4という表現。'])
y=panel(y,'次のGo / No-Go判断',[
 '10月23日までに実Gazebo走行が成立しなければ構成を縮小。',
 '動画・レポート・リポジトリの完成を最優先し、未達を明示する。'])
c.save();print(OUT)
