#!/usr/bin/env python3
"""Create Japanese 4-page V100 local-first transition report (NOT final submission PDF)."""
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer,PageBreak,KeepTogether

R=Path(__file__).resolve().parents[1]
OUT=R/'docs/RescueMind_v32_Local_V100_HANDOFF.pdf'
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
FACE='HeiseiKakuGo-W5';NAVY=colors.HexColor('#173454');TEAL=colors.HexColor('#116c79');MUTED=colors.HexColor('#546375')
st={
 'hero':ParagraphStyle('hero',fontName=FACE,fontSize=21,leading=31,textColor=NAVY,spaceAfter=17),
 'h':ParagraphStyle('h',fontName=FACE,fontSize=13,leading=20,textColor=NAVY,spaceBefore=13,spaceAfter=6),
 'body':ParagraphStyle('body',fontName=FACE,fontSize=9.1,leading=15.6,spaceAfter=7),
 'tiny':ParagraphStyle('tiny',fontName=FACE,fontSize=8.1,leading=13.2,spaceAfter=5),
 'code':ParagraphStyle('code',fontName='Courier',fontSize=8.0,leading=13,spaceAfter=4),
 'sub':ParagraphStyle('sub',fontName=FACE,fontSize=10,leading=16,textColor=TEAL,spaceAfter=11),
}

def P(txt,kind='body'):return Paragraph(txt,st[kind])
def head(s):return P(s,'h')
def tbl(rows,widths):
 t=Table([[P(str(c),'tiny') for c in row] for row in rows],colWidths=widths,repeatRows=1,hAlign='LEFT')
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eaf0f5')),
  ('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor('#aab8c7')),
  ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f7f9fb')]),
  ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),9),
  ('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),7),
  ('BOTTOMPADDING',(0,0),(-1,-1),7)]))
 return t
story=[]
# P1
story += [P('RescueMind v3.2<br/>GPU / Linux 引き継ぎガイド','hero'),
          P('2026年10月16日 ・ NVIDIA Tesla V100 32GB ・ ローカルVLM優先','sub'),
          P('課題：Physical AI応用1講座「AI×ロボティクスによる創造的タスクの実現」。創造性・技術力・実用性・表現力の加点を意識し、物資の現地画像判断で移動継続／停止を分岐します。'),
          head('今回の最も重要な変更'),
          P('クラウドAPIへの依存を外し、<b>Qwen2.5-VL-3B-InstructをV100のFP16でローカル実行</b>する構成を実装。旧Jev 1.14.0＋Qwen3.8クラウド経路は比較用に保管。標準モードは同じモデルを異なる2プロンプトで確認し、別モデルとの合議ではありません。'),
          head('達成済みと未実施の境界'),
          tbl([
              ['項目','現状'],
              ['ROS/Gazebo・シーンSDF・速度ガード','コード／静的／模擬ROSで検証'],
              ['ローカル画像判定クライアント・サーバー','HTTPモック・契約試験で検証'],
              ['Python自動テスト','506/506 成功（GPU実行は含まず）'],
              ['実V100モデル推論・実Gazebo走行','未実施：Linux PCで最初に確認'],
              ['3シーン30試行・実ROS bag・MP4','未実施：GPU/Linuxで取得'],
              ['物資の把持／運搬','未実装。移動と現地確認のみ'],
          ],[78*mm,102*mm]),
          Spacer(1,6*mm),P('このPDFは引き継ぎ資料であり、提出用最終PDFではありません。実動画・実測データの完成が必要です。','tiny'),
          PageBreak()]
# P2
story += [P('01　V100 32GBでのセットアップ','hero'),
          head('互換性を最優先'),
          P('V100はVolta（計算能力7.0）。推奨はCUDA 12.1対応PyTorch 2.5.1、FP16、eager attention。BF16・FlashAttention2・新しいCUDA 12.8 wheelを前提にしません。GPUドライバとtorch CUDAが合うことを現地で確認してください。'),
          head('Ubuntu 24.04 / ROS 2 Jazzy / Gazebo Harmonic'),
          P('1. nvidia-smiでV100のメモリ／ドライバを確認。<br/>2. /opt/ros/jazzy/setup.bash と gz sim を確認。<br/>3. ZIPを展開し、下のコマンドを順番に実行。'),
          P('bash scripts/setup_ubuntu_jazzy.sh','code'),
          P('bash scripts/install_local_vlm_v100.sh','code'),
          P('source .venv/bin/activate','code'),
          P('python3 scripts/local_gpu_preflight.py --mode single','code'),
          P('bash scripts/v32_verify.sh','code'),
          head('まずモデル単体を起動'),
          P('端末A：HF_HUB_OFFLINE=1 python3 scripts/local_vlm_server.py --port 8765','tiny'),
          P('端末B：python3 scripts/v32_local_smoke.py --image fixtures/supply_schematic.jpg --expected water','tiny'),
          P('模式画像による接続テストは認識精度測定ではありません。ローカル3Bモデルは初回のみHugging Faceからダウンロード。重みはZIPに含めていません。'),
          head('追加モデルは任意'),
          P('--local-mode dualではSmolVLM2-2.2Bを2台目サーバーで利用。V100 32GBでの同時メモリ消費は未計測。まずsingleを完走させ、その後でdualを試してください。'),
          PageBreak()]
# P3
story += [P('02　実Gazebo走行・実AI判定','hero'),
          head('Step 1：AIを使わない車輪・カメラの確認'),
          P('python3 scripts/v32_orchestrate.py --run --scenario motion-check --scene nominal --capture-rosbag','tiny'),
          P('合格条件：GazeboとROSの/clock、/camera、/odom、/scanが動作。物資拠点と避難所への独立軌跡が監査に合格し、ROS bagが正常終了すること。'),
          head('Step 2：ローカルAIを使う本命シーン'),
          P('python3 scripts/v32_orchestrate.py --run --scenario live --scene nominal --local-mode single --capture-rosbag --instruction "避難所Bに飲料水を届けて"','tiny'),
          P('正常が完走できたら、同じ指示で --scene swapped、--scene emptyへ変更し、誤物資・欠品の停止を撮影。実画像・推論秒数・ROS軌跡を保存する。'),
          tbl([
              ['シーン','期待される結果','合格の証拠'],
              ['nominal：正物資','COMPLETED','現地画像で許可、避難所へ接近'],
              ['swapped：入れ替え','COMPLETED_EXPECTED_DENIAL','AI拒否後の停止と独立ROS観測'],
              ['empty：欠品','COMPLETED_EXPECTED_DENIAL','AI拒否後の停止と独立ROS観測'],
              ['API・推論・センサー障害','FAILED','誤認識の成功と混同しない'],
          ],[45*mm,61*mm,74*mm]),
          head('失敗したとき最初に確認するファイル'),
          P('outputs/runs/&lt;run_id&gt;/stack_result.json → readiness_last.txt → mission.log → guard_graph_watch.jsonl → ROS bag。録画・ロボット制御・AIモデルが同じrun_idで整合するか調べます。'),
          PageBreak()]
# P4
story += [P('03　評価・動画・提出まで','hero'),
          head('30試行の研究計画'),
          P('python3 scripts/v32_print_trial_commands.py で、事前登録済み3シーン×2物資×5反復の順番とコマンドを確認できます。未実施の試行は成功数に含めない。30試行は30種類の未知環境ではありません。'),
          head('映像は1分〜3分（推奨110秒前後）'),
          P('①救援タスクの目的 → ②正常な物資で現地判断・続行 → ③誤物資でAI拒否・停止 → ④欠品で拒否 → ⑤技術構成とログ比較。倍速使用時は明記。'),
          head('締切と提出方法'),
          tbl([
              ['締切','2026年11月2日（月）10:00 JST'],
              ['OmniCampus','説明PDF・public GitHubリポジトリURL'],
              ['YouTube','実ロボット動画MP4を公開／限定公開で提出。URLもOmniCampusへ'],
              ['命名','説明資料_PAI最終課題_omnicampusアカウント名.pdf'],
              ['個人情報','氏名・所属・メール・認証情報を一切含めない'],
          ],[46*mm,134*mm]),
          head('確認済み公式情報'),
          P('Qwen2.5-VL-3B：huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct<br/>SmolVLM2：huggingface.co/HuggingFaceTB/SmolVLM2-2.2B-Instruct<br/>ROS/Gazebo：gazebosim.org/docs/harmonic/ros_installation/<br/>Volta互換：dev-discuss.pytorch.org（Volta CUDA 12.8 wheelの対応終了）','tiny'),
          Spacer(1,7*mm),
          P('最終判断：ローカル推論コードとオフライン検証は完了。<b>GPUで本物のVLM推論とGazebo走行を録画して初めて最終課題の実行成果と呼べます。</b>','body')]

def footer(canvas,doc):
 canvas.setStrokeColor(colors.HexColor('#d9e2eb'));canvas.line(18*mm,18*mm,192*mm,18*mm)
 canvas.setFont(FACE,8);canvas.setFillColor(MUTED)
 canvas.drawString(19*mm,12.3*mm,'RescueMind v3.2 | GPU/Linux引き継ぎ | 2026-10-16')
 canvas.drawRightString(190*mm,12.3*mm,f'{doc.page} / 4')
doc=SimpleDocTemplate(str(OUT),pagesize=A4,leftMargin=18*mm,rightMargin=18*mm,
 topMargin=18*mm,bottomMargin=22*mm,title='RescueMind v3.2 GPU/Linux 引き継ぎ',author='RescueMind Project')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(OUT)
