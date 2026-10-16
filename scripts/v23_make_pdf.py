#!/usr/bin/env python3
"""Generate a clearly unsubmitted three-page research draft using verified offline results."""
from pathlib import Path
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
R=Path(__file__).resolve().parents[1]
D=json.loads((R/'verification/v23/verification.json').read_text())
OUT=R/'docs/RescueMind_v23_REPORT_DRAFT_NOT_SUBMISSION.pdf'
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
W,H=A4;c=canvas.Canvas(str(OUT),pagesize=A4,pageCompression=1)
c.setTitle('RescueMind v2.3 - PAI最終課題研究ドラフト（未提出）')
c.setAuthor('RescueMind')
F='HeiseiKakuGo-W5';navy=(.09,.17,.24);blue=(.02,.35,.50)
def text(x,y,s,size=9,color=navy):
    c.setFillColorRGB(*color);c.setFont(F,size);c.drawString(x,y,str(s))
def page(head,num):
    c.setFillColorRGB(*navy);c.rect(0,H-110,W,110,stroke=0,fill=1)
    text(36,H-43,'RESCUEMIND  /  PHYSICAL AI 2026',14,(1,1,1))
    text(36,H-80,head,13,(1,1,1))
    text(36,26,'v2.3  /  2026-10-16  /  未提出：実Gazebo・実モデル評価は未完了',7.4)
    text(W-63,26,f'{num} / 3',8)
def section(y,title,items):
    text(40,y,title,11,blue);y-=27
    for s in items:
        text(45,y,'・'+s,8.6);y-=22
    return y-19
def footer(y,title,lines):
    h=43+len(lines)*22
    c.setFillColorRGB(.92,.95,.97);c.roundRect(40,y-h,W-80,h,7,stroke=0,fill=1)
    text(53,y-29,title,9.6,blue)
    for i,s in enumerate(lines):text(53,y-51-22*i,s,8.4)
    return y-h-16
page('研究テーマと独自性',1)
y=H-149
y=section(y,'講座の評価・合格要件',[ '創造性・技術力・実用性・表現力の4項目で加点。', 'ロボットがタスクを実行する1～3分の動画、コード、PDFレポートが必要。', 'GitHub publicとYouTube動画URLをOmniCampusに提出。締切 11/2 10:00。'])
y=section(y,'提案：現地画像の二重判断がロボットの次の行動を変える',[ 'ROS 2・Gazebo差動二輪ロボットが物資拠点へ接近する。', '必須Jev 1.14.0＋Qwen3.8が、物資の種類と通路の危険を判定。', '許可なら避難所へ接近、不一致・不確実・通信障害なら停止する。'])
y=section(y,'作品固有の工夫',[ '同一照明・経路・車輪・センサーを保ち物資の配置だけ変更。', '独立速度ガード、ROS軌跡監査、許可時刻と走行時刻の照合。', 'ソフトウェアの結果と本物のGazebo・API結果を明確に区別。'])
footer(y,'現時点の制約',[ '物理把持・物資積載・運搬は未実装：拠点確認と避難所接近がタスク。', 'このPDFは実測データを追記する前の研究ドラフトであり未提出。'])
c.showPage()
page('v2.3実験計画と実行済み検証',2)
y=H-149
y=section(y,'反復可能な比較実験：事前固定した30試行',[ 'nominal（正しい物資）／swapped（入れ替え）／empty（欠品）。', '水指示・医療物資指示×3シーン×各5反復＝30試行。', 'seed=20261016で順序を事前固定。正解ラベルはAI入力から分離。'])
y=section(y,'評価する指標',[ 'Jev単独・Qwen単独・Jev＋Qwen合意方式を同じ画像で比較。', '危険な許可（誤許可）と正常時の拒否（誤拒否）を両方報告。', 'カバレッジ・推論遅延・実行成功率を別々に記録。'])
y=section(y,'今回実行したオフライン検証',[ f'Python自動テスト {D["python_tests_passed"]}件全件成功。', '3シーンのSDF構造・共通要素一致を検査。', '計画外ID、ラベル変更、重複画像、模擬結果、欠測を拒否。'])
footer(y,'統計・研究上の注意',[ '同じ3シーンの反復撮影は独立な未知環境試行とは見なせない。', '実APIの認識精度・実Gazeboの物理走行成功率は未測定。'])
c.showPage()
page('Ubuntu実行・優秀賞・提出計画',3)
y=H-149
y=section(y,'Ubuntu 24.04での実行順序',[ '1. v23_verify.sh を実行し、ROS・Gazebo導入を確認する。', '2. motion-checkで差動二輪、カメラ、LiDAR、ROS時計を検証。', '3. Gazeboの正配置／入れ替え／欠品の視覚確認を行う。', '4. 実Jev/QwenをAPIで呼び、観測画像と判定ログを保存。', '5. v23_evaluate_captures.pyで30試行と一致するか検査。'])
y=section(y,'表現力の改善：2分程度の実ロボット動画',[ '問題提示→ロボット接近→正しい物資で続行→誤配置／欠品で停止。', 'AI応答、ROS軌跡と時刻、正常／拒否の対照を画面に表示。', '倍速映像には倍率を明記し、実際の物理走行だけを成果とする。'])
y=section(y,'提出前チェック',[ 'GitHub public、PDFファイル名、YouTube最低限定公開、URL提出。', '氏名・所属・メールアドレス・APIキー・秘密情報の流出を禁止。', '11/1までに撮影・PDF・リポジトリ・リンクの検証を終える。'])
footer(y,'最重要な次の成果',[ '実Gazeboの動作と実Jev/Qwenの映像・ログが取得できるまでは完成としない。'])
c.save();print(OUT)
