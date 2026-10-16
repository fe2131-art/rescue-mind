#!/usr/bin/env python3
"""Three-page Japanese PDF research draft; explicitly NOT a submission report."""
from pathlib import Path
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
R=Path(__file__).resolve().parents[1]
D=json.loads((R/'verification/v22/V22_VERIFICATION.json').read_text())
OUT=R/'docs/RescueMind_v22_REPORT_DRAFT_NOT_SUBMISSION.pdf'
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
W,H=A4; c=canvas.Canvas(str(OUT),pagesize=A4,pageCompression=1)
c.setTitle('RescueMind v2.2 PAI最終課題 研究ドラフト（未提出）')
c.setAuthor('RescueMind project (anonymous)')
FONT='HeiseiKakuGo-W5';DARK=(.09,.16,.23);ACC=(.02,.33,.49)
def t(x,y,s,size=9,color=DARK):
    c.setFillColorRGB(*color);c.setFont(FONT,size);c.drawString(x,y,s)
def page(head,num):
    c.setFillColorRGB(*DARK);c.rect(0,H-107,W,107,stroke=0,fill=1)
    t(36,H-39,'RESCUEMIND  /  PHYSICAL AI 2026',13,(1,1,1))
    t(36,H-74,head,14,(1,1,1))
    t(37,27,'v2.2 | 2026-10-16 | 未提出：実Gazebo・実VLM推論は未検証',7.4)
    t(W-67,27,f'{num} / 3',8)
def section(y,heading,lines):
    t(40,y,heading,11,ACC);y-=26
    for x in lines:
        t(44,y,'・'+x,8.7);y-=23
    return y-21
def box(y,heading,lines):
    h=39+len(lines)*23
    c.setFillColorRGB(.92,.95,.97);c.roundRect(40,y-h,W-80,h,7,stroke=0,fill=1)
    t(53,y-27,heading,10,ACC)
    for idx,line in enumerate(lines):t(53,y-50-idx*23,line,8.4)
    return y-h-14
page('研究課題と独自アプローチ',1)
y=H-149
y=section(y,'講座評価基準と提出条件',[ '創造性、技術力、実用性、表現力。AI推論を含むロボット実行が必要。', '提出物は実ロボット動画60～180秒・コード一式・説明PDF。', '公開GitHubとYouTube URLをOmniCampusへ提出。締切 11月2日10:00。'])
y=section(y,'提案：現地の二重視覚判断による移動許可',[ '自然言語で水・医療物資拠点を選択し、カメラで現地を撮影。', 'Jev 1.14.0を必須とし、Qwen3.8との判定一致で継続・拒否。', 'ROS 2とGazebo、独立速度ガード、独立走行観測を連携。'])
y=section(y,'v2.2の差別化',[ '棚の色・車輪ロボット・照明・経路を保った3つのSDF対照環境。', '物資が正しい／入れ替わる／欠品する条件を統制して比較。', '意図した現地AI拒否と単なるAPI障害を区別する監査を追加。'])
box(155,'実装範囲と制約',['物理的な把持・積載・配送は未実装：物資拠点の確認と避難所への接近。', '実Gazeboレンダリング・実モデル推論・最終ロボット動画は未実施。'])
c.showPage()
page('3シーンの実験設計・オフライン検証',2)
t(40,H-145,'SDF上の配置を比較：これはレンダリング画像ではありません',10,ACC)
c.drawImage(str(R/'docs/V22_SCENE_SCHEMATIC.png'),40,H-422,width=W-80,height=240,preserveAspectRatio=True,anchor='c')
y=H-456
y=section(y,'3条件の期待動作',[ 'nominal：水棚に飲料水。実VLMが確認できたときのみ避難所へ。', 'swapped：水棚に救急箱。誤物資と認識して停止することを期待。', 'empty：水棚は空。物資不在と認識して停止することを期待。'])
y=section(y,'実行済みの検証と限界',[ f'Python自動テスト {D["unit_tests_passed"]}件が全件成功。', '3シーンのXML構造・非物資部分の一致・SDF/YAML整合を確認。', '監査は独立ROS記録の停止証拠不足・順序異常・run_id不一致を拒否。'])
box(127,'最重要な実証の不足',['XML構造合格 ≠ 本物のカメラで物資が見えることの証明。', '実API結果がないため画像認識精度・安全性能の数値は記載しない。'])
c.showPage()
page('優秀賞に向けた次の検証・提出チェック',3)
y=H-150
y=section(y,'必須実証の順序',[ '1. UbuntuでGazeboを実行し、カメラに物資が映るか確認。', '2. 非AI走行で物資拠点への到達と速度ガード・ROS bagを確認。', '3. JevとQwenの実APIで3シーンを推論し、正常／拒否を撮影。', '4. 独立ROS軌跡と推論ログから到達／拒否の妥当性を監査。'])
y=section(y,'定量的な比較で示すもの',[ '同じ画像でJev単体・Qwen単体・合意方式を比較。', '誤許可率と誤拒否率、許可率、モデル推論遅延を併記。', '複数撮影角度・独立試行の正解ラベルを固定し、Wilson区間も報告。'])
y=section(y,'表現力：動画120秒の案',[ '問題設定 → Gazeboロボット → 正物資で継続 → 誤物資・欠品で停止。', 'Jev/Qwenの判断とROS軌跡を同期表示、実測値のみ記載。', '倍速表示する場合は「2倍速」等を動画内か概要欄に明記。'])
y=section(y,'提出時の最終ゲート',[ '60～180秒MP4、public GitHub、説明PDF、YouTube URL。', 'PDF名：説明資料_PAI最終課題_omnicampusアカウント名.pdf。', '個人情報・APIキー・秘密情報を除外。締切 11月2日 AM10:00。'])
box(111,'作品の完成判定',['オフラインテスト数ではなく、実Gazebo動作・実VLM判断・実測・動画で判定。'])
c.save();print(OUT)
