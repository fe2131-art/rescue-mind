#!/usr/bin/env python3
"""Create Japanese three-page report *draft*; no claims of Gazebo/API success."""
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer,PageBreak
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/RescueMind_v27_REPORT_DRAFT_NOT_SUBMISSION.pdf'
FONT='HeiseiKakuGo-W5'
pdfmetrics.registerFont(UnicodeCIDFont(FONT))
body=ParagraphStyle('body',fontName=FONT,fontSize=9.0,leading=15,spaceAfter=8,wordWrap='CJK',textColor=colors.HexColor('#24354A'))
small=ParagraphStyle('small',parent=body,fontSize=8.0,leading=12.7,spaceAfter=4)
h1=ParagraphStyle('heading',parent=body,fontSize=13.0,leading=20,textColor=colors.HexColor('#006E7D'),spaceBefore=10,spaceAfter=7)
big=ParagraphStyle('big',parent=body,fontSize=21,leading=29,spaceAfter=9,textColor=colors.HexColor('#142C43'))
P=lambda s,style=body:Paragraph(s,style)
def T(rows,widths):
    tab=Table([[P(str(x),small) for x in row] for row in rows],colWidths=widths,repeatRows=1,hAlign='LEFT')
    tab.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),
      ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#DDEDF0')),
      ('LINEBELOW',(0,0),(-1,0),.8,colors.HexColor('#267889')),
      ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F7FAFC')]),
      ('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#D1DDE3')),
      ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
      ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    return tab

def footer(c,d):
    c.saveState();c.setFillColor(colors.HexColor('#79838F'));c.setFont(FONT,7)
    c.drawString(17*mm,13*mm,'RescueMind v2.7 / 提出前ドラフト / 実Gazebo・実Jev/Qwen未検証')
    c.drawRightString(190*mm,13*mm,str(d.page));c.restoreState()

w=176*mm
story=[P('Physical AI 応用1講座 最終課題 — 2026-10-16 / 技術評価レポート草案',small),
       P('RescueMind v2.7',big),
       P('Jev＋Qwenによる物資棚の現地確認と、センサー・撮影品質を検証した後の避難所への接近'),
       P('ねらいと制作範囲',h1),
       P('日本語の物資指示を差動二輪ロボットの拠点接近タスクへ変換する。現地で物資棚へ方向合わせを行い、オドメトリの速度・姿勢から静止を確認。2枚の新規ROSカメラ画像の取得・品質確認を経て、Jev 1.14.0とQwen3.8-Omni-Flashの双方が許可した場合のみ避難所Bへ進む。拒否・観測障害では停止し、独立ROS記録で照合する。'),
       T([['評価項目','本プロトタイプで示す工夫'],
         ['創造性','同一指示・同一路線のまま物資だけを入替・欠品し、AI判断で継続／停止を分岐'],
         ['技術力','ROS/Gazebo、Jev＋Qwen、カメラ方向合わせ、静止ゲート、2フレーム取得、独立ガード'],
         ['実用性','センサー異常、誤物資、壊れた画像、API失敗を区別して走行を拒否'],
         ['表現力','実行ID・独立軌跡・画像SHA・AI判断を同じ時間軸に関連付ける']],[32*mm,144*mm]),
       Spacer(1,7*mm),P('制作範囲の正確な説明',h1),
       P('物資の把持・積載・運搬は未実装。避難所への「配送」ではなく、物資拠点の視覚確認と避難所への接近デモである。Nav2による自律経路再計画もカスタムGazeboワールドでは実証していない。'),
       PageBreak(),
       P('v2.7 技術改善：観測品質によるAI開始ゲート',h1),
       P('v2.6の静止確認に加え、カメラから得た1枚だけをそのまま推論へ送る代わりに、静止後の異なるタイムスタンプを持つ有効な2枚を要求する。2枚目をJPEGへ保存し、再監査でSHA-256・取得時刻・判断順を照合する。'),
       T([['確認内容','失敗条件と挙動'],
         ['ROS Imageデコード','encoding不明、短すぎる／余分なpayload、stride不整合は拒否'],
         ['画像の露光異常','黒つぶれ・白飛び99%以上、輝度分位幅が4未満の単色画像を拒否'],
         ['撮影時刻','静止確認0.5秒後から。2枚目は1枚目から最低0.15秒。古い・重複stampはカウントしない'],
         ['AIの開始','有効2フレーム取得後のみJevとQwenを呼ぶ。画像品質不良はAIの否決成功とは分類しない'],
         ['安全制御','独立速度ガードとLiDAR/odomカメラ監視を維持。異常時は停止側へ遷移']],[41*mm,135*mm]),
       Spacer(1,5*mm),P('2026-10-16に実際に実行したオフライン検証',h1),
       T([['試験種類','結果・検証範囲'],
          ['Pythonの回帰・結合テスト','412件 / 412件成功（合成センサーデータ・模擬ROSを含む）'],
          ['新規取得異常キャンペーン','14人工条件が事前定義した許可／拒否結果と一致'],
          ['Gazeboワールドとプラン','3シーンSDF・ROSブリッジ・起動計画を静的検査'],
          ['真のGazebo・Jev・Qwen','すべて未実施。実画像での認識性能・物理走行は未測定']],[59*mm,117*mm]),
       P('制限：輝度の検査は対象物の視認性、遮蔽、画像の意味、反射・ブラーを保証しない。閾値は実Gazeboで撮影結果を見て事前校正する必要がある。'),
       PageBreak(),
       P('優秀賞向け：実証と提出の計画',h1),
       P('比較実験の組み立て',h1),
       P('同じカメラ、距離、物資指示のもとでnominal（正配置）・swapped（入替）・empty（欠品）を水／医療物資で反復。Jev単独、Qwen単独、二重許可の誤許可・不要拒否・推論時間を比較し、取得異常とAPI障害は別集計する。30試行は事前登録プランであり、30件の実API推論は未実行。'),
       T([['実証ステップ','必要な外部環境で取得する証拠'],
         ['1. Gazebo実走行','Ubuntu 24.04/ROS 2 Jazzy/Gazebo Harmonicで移動・カメラ画像を収録'],
         ['2. 画像確認','棚が映っていることを目視、静止・2フレーム品質イベントとJPEGを確認'],
         ['3. AI判断','Jev/Qwen本物のレスポンス、遅延、許可・否決、独立位置軌跡を紐付け'],
         ['4. 比較・動画','許可なら避難所へ進む試行、否決なら止まる試行を実画面で比較'],
         ['5. 提出','public GitHub、指定名PDF、YouTube 1～3分MP4、OmniCampus URL登録']],[39*mm,137*mm]),
       Spacer(1,5*mm),P('動画の約2分構成例',h1),
       P('0:00～0:18 課題と指示 ／ 0:18～0:45 物資拠点へ移動 ／ 0:45～1:03 棚向き合わせ・静止・2画像の品質判定 ／ 1:03～1:22 Jev/Qwen結果 ／ 1:22～1:43 正常時に避難所へ進む ／ 1:43～2:00 誤物資時の停止と測定結果。実際に取得した映像だけを実動作として示す。倍速使用時は明記。'),
       P('提出要件と利用者への注意',h1),
       P('提出開始2026-10-19／締切2026-11-02 10:00 JST。PDF名は「説明資料_PAI最終課題_omnicampusアカウント名.pdf」。YouTubeタイトルは「PAI最終課題_omnicampusアカウント名」。最低限定公開、公開は加点対象。氏名・所属・メール・認証情報を成果物へ含めない。'),
       P('これは<b>実測前の未提出ドラフト</b>である。実Gazebo・実AI推論の録画と実測値がないため、最終課題の動画要件は現時点では未充足。',small)]
OUT.parent.mkdir(parents=True,exist_ok=True)
SimpleDocTemplate(str(OUT),pagesize=A4,leftMargin=17*mm,rightMargin=17*mm,topMargin=19*mm,bottomMargin=20*mm,
  title='RescueMind v2.7 Report Draft / Not Submission').build(story,onFirstPage=footer,onLaterPages=footer)
print(OUT)
