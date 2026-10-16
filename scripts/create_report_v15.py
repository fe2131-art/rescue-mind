"""Create a NON-SUBMITTABLE Japanese v1.4 PDF based on offline tests."""
from pathlib import Path
import json
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer,PageBreak
ROOT=Path(__file__).resolve().parents[1]
D=json.loads((ROOT/'outputs/release/v15_VERIFICATION.json').read_text())
PDF=ROOT/'docs/RescueMind_v15_REPORT_DRAFT_NOT_SUBMISSION.pdf'
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
FONT='HeiseiKakuGo-W5'
base=ParagraphStyle('jp',fontName=FONT,fontSize=9.2,leading=16,spaceAfter=8,wordWrap='CJK',textColor=colors.HexColor('#172637'))
sm=ParagraphStyle('sm',parent=base,fontSize=8.0,leading=12)
h=ParagraphStyle('h',parent=base,fontSize=14,leading=21,textColor=colors.HexColor('#146779'),spaceBefore=9)
t=ParagraphStyle('t',parent=base,fontSize=20,leading=29)
def P(v,style=base):return Paragraph(v,style)
def table(data,widths):
  o=Table([[P(str(x),sm) for x in row] for row in data],colWidths=widths,repeatRows=1)
  o.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E4EFF2')),
      ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),7),
      ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
      ('LINEBELOW',(0,0),(-1,0),0.6,colors.HexColor('#186478')),
      ('LINEBELOW',(0,1),(-1,-1),0.3,colors.HexColor('#C8D4DB'))]))
  return o

def footer(c,d):
 c.saveState();c.setFont(FONT,7);c.setFillColor(colors.HexColor('#67747B'))
 c.drawString(17*mm,12*mm,'RescueMind v1.5  |  未提出ドラフト / 実Gazebo・実API未検証')
 c.drawRightString(190*mm,12*mm,str(d.page));c.restoreState()

w=176*mm
story=[P('Physical AI 応用1 最終課題 / 優秀賞を狙う提案',sm),P('RescueMind v1.5',t),
 P('Jev＋Qwenの現地判断と、走行前のROSセンサー品質ゲート・独立速度ガードによる物資拠点の確認と避難所への接近'),
 P('課題と具体的な貢献',h),
 P('自然言語で指定された物資拠点に差動二輪ロボットが向かい、現地のROSカメラで撮影した画像をJev 1.14.0とQwen3.8-Omni-Flashで判定する。誤物資・危険表示・判断不一致・通信不良の場合は次区間への出発を拒否する。判定が一致した場合のみ避難所Bへ向かう。'),
 table([['加点項目','作品の実装と提出時に示す内容'],
 ['創造性','JevとQwenの合意を次区間の許可に直結し、同じ物資要求で続行・拒否を比較'],
 ['技術力','Jev/Qwen推論、ROS2カメラ・LiDAR・odomの形式と時刻検証、別プロセス速度ガード、起動監視'],
 ['実用性','誤許可・誤拒否・通信失敗・障害物・センサー停止のトレードオフを計測'],
 ['表現力','同一コースの成功／中断を2分の実Gazebo動画と時系列ログで示す']],[30*mm,w-30*mm]),
 Spacer(1,7*mm),P('正しいタスク定義と達成範囲',h),
 P('本作品では物資の把持、積載、物理的な配送は未実装。現時点のロボットが実行するタスクは「物資拠点の視覚確認と避難所への接近」である。独自ワールドの直接駆動はNav2による自律経路再計画ではない。'),
 PageBreak(),
 P('v1.5 改善：センサー品質ゲートと実行管理',h),
 table([['要素','v1.4の動作と検証範囲'],
 ['ミッションノード','/rescuemind/cmd_vel_requestだけに速度を要求。ガードとセンサーのreadiness前には動かない'],
 ['速度ガード（新）','別ROS2ノードが10Hzで/cmd_velへ出力。指令途絶で速度0、後退を拒否。プロセス監視で異常終了時はミッション中止'],
 ['センサー異常','前方LiDARのみなので後退禁止。カメラ配信停止、odom途絶、不正Twistを拒否'],
 ['走行前データ検証（新）','画像のencoding・stride・長さ、LiDARの測距値と角度設定、odomの姿勢とframe、各トピック3回の取得時刻更新を確認'],
 ['自動起動監視','Gazebo・bridge・guardの生存を監視し、センサーデータ検証が通った場合だけミッションを開始'],
 ['限界','ガード自体のクラッシュ時の物理的停止や実Gazebo動作は未保証']],[46*mm,w-46*mm]),
 Spacer(1,7*mm),P('2026年10月16日のオフライン実測（実Gazeboは未実行）',h),
 table([['検証','結果（すべてオフライン）'],
 ['Python単体とモックROS',f"{D['unit_tests']}件：全件成功"],
 ['速度ガード人工障害注入',f"{D['previous_guard_fault_cases']}条件：{D['previous_guard_fault_cases']}件合格"],
 ['カメラ監視の過去試験',f"{D['previous_camera_cases']}条件：合格"],
 ['Jev/Qwen模擬安全判定',f"{D['previous_policy_conditions']}条件：論理検証"],
 ['SDFと運動学','静的整合性と理想運動学の到達を確認'],
 ['起動管理','dry-run、子プロセス異常終了と後片付けを検証'],
 ['センサー形式（新）',f"{D['v15_synthetic_sensor_cases']}人工入力条件が事前定義した期待と一致。実ROSデータではない"],
 ['実Jev/Qwen/Gazebo','未実行。API資格情報とROS/Gazebo実行環境が必要']],[61*mm,w-61*mm]),
 Spacer(1,7*mm),P('オフライン試験が保証しないもの',h),
 P('人工入力での正しい停止は、実モデルの誤認識率、実Gazeboでの衝突回避性能、機能安全認証ではない。二つのVLMの誤りは相関する可能性があり、実カメラ画像による検証が不可欠。'),
 PageBreak(),
 P('実測実験・動画・提出までのロードマップ',h),
 P('モデル評価ではJev単独、Qwen単独、Jev＋Qwen合意を同じラベル付き未使用画像で比較し、誤許可率・不要拒否率・レイテンシ・到達率を報告する。Wilson信頼区間とMcNemar正確検定を補助的に用いる。実画像での測定結果は現在未取得のため数値を作らない。'),
 P('2分の動画案',h),
 table([['動画時刻','撮影する実際の事実'],
 ['0:00–0:25','課題背景と日本語ミッション。Gazeboのロボットを映す'],
 ['0:25–0:55','物資拠点へ移動。LiDARとカメラ映像を重ねる'],
 ['0:55–1:20','現地画像→Jev/Qwenの一致→次区間に進む'],
 ['1:20–1:45','不一致または異常を意図的に与え停止する別試行'],
 ['1:45–2:00','誤許可と誤拒否の実測比較、貢献と残課題']],[32*mm,w-32*mm]),
 P('最終作業順序',h),
 P('1. Ubuntu 24.04でROS対応venvを作成し、v15_orchestrate.pyでGazebo→bridge→guard→3回のセンサー鮮度検査→motion-checkを起動する。<br/>2. /cmd_velとguard_readyの発行元を検査し、ガード切断試験とカメラ撮影を記録する。<br/>3. Jev・Qwenの実画像推論を測り、許可/停止の実験を実映像に収録。<br/>4. 実測をPDFへ反映し、public GitHub、1〜3分MP4とYouTube URLを用意する。'),
 P('提出要件と限界',h),
 P('提出開始2026年10月19日、締切11月2日10:00 JST。PDFの命名規則、public GitHub、YouTube限定公開以上、個人情報非掲載を守る。これは<b>未提出ドラフト</b>であり実Gazebo動画と実API結果がないため、現段階で提出完了とは扱わない。')]
PDF.parent.mkdir(exist_ok=True,parents=True)
doc=SimpleDocTemplate(str(PDF),pagesize=A4,leftMargin=17*mm,rightMargin=17*mm,topMargin=19*mm,bottomMargin=20*mm)
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(PDF)
