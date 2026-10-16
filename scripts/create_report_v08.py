"""Create Japanese 3-page report draft; replace measured results before final submission."""
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.units import mm
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/RescueMind_v08_説明資料_ドラフト_未提出.pdf'

def main():
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
    fn='HeiseiKakuGo-W5'; navy=colors.HexColor('#1f304a'); teal=colors.HexColor('#147c81')
    st={}
    st['title']=ParagraphStyle('JA-title',fontName=fn,fontSize=20,leading=29,spaceAfter=14,textColor=navy,wordWrap='CJK')
    st['h1']=ParagraphStyle('JA-h1',fontName=fn,fontSize=12,leading=18,spaceBefore=13,spaceAfter=5,textColor=teal,wordWrap='CJK')
    st['txt']=ParagraphStyle('JA-txt',fontName=fn,fontSize=9,leading=15,spaceAfter=7,wordWrap='CJK')
    st['tiny']=ParagraphStyle('JA-tiny',fontName=fn,fontSize=7.8,leading=12,wordWrap='CJK')
    st['note']=ParagraphStyle('JA-note',fontName=fn,fontSize=8,leading=13,textColor=colors.HexColor('#555555'),wordWrap='CJK')
    P=lambda t,style='txt':Paragraph(t,st[style])
    story=[]
    story += [P('RescueMind v0.8','title'),P('Jev 必須 × Qwen3.8 × ROS 2 / Gazebo：物資拠点の現地認識による行動分岐','h1'),
              P('Physical AI 応用1 最終課題（10/8版）に基づく、実行検証前の説明資料ドラフトです。<b>オフライン検証と本物のGazebo・API実測を厳格に区別</b>します。'),
              P('1. 解きたい課題','h1'),
              P('災害対応の施設で、人間の日本語指示から目標物資を選び、ロボットが現地で物資を再確認してから次の目的地へ移動する。画像モデルの誤認や通信途絶があれば、無条件に続行せず停止する。'),
              P('2. 実装したシステム','h1')]
    rows=[['役割','実装'],['要求理解','TF-IDF + ロジスティック回帰／曖昧な指示は出発拒否'],
          ['現地画像AI','Jev 1.14.0（Choice/Noul/Box）＋Qwen3.8-Omni-Flash'],
          ['意思決定','両モデルの物資判断が一致し、Jevの存在判定と信頼度が十分なら次の区間を許可'],
          ['ロボット','ROS 2 Jazzy想定、Gazebo Harmonic SDF、差動二輪の直接駆動'],
          ['監視','LiDAR近接/通信途絶/カメラ画像欠落/タイムアウトで停止']]
    table=Table([[P(x,'tiny') for x in row] for row in rows],colWidths=[35*mm,143*mm],hAlign='LEFT',repeatRows=1)
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9f1f4')),('VALIGN',(0,0),(-1,-1),'TOP'),
                              ('GRID',(0,0),(-1,-1),.35,colors.HexColor('#c2ccd5')),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    story+=[table,Spacer(1,7*mm),P('3. 提案手法の独自性','h1'),
            P('①指示に従って物資拠点へ移動 → ②到着後のROSカメラの新しい画像を取得 → ③JevとQwenで再判定 → ④結果が一致したときだけ避難所Bに接近する。両者の不一致、Jevの存在判定不足、センサ異常では次の走行を拒否する。'),
            P('※物資を把持・積載・配送するハードウェアは未実装。作品の達成範囲は「物資拠点認識と避難所への接近」であり、物流達成ではない。','note'),
            PageBreak(),P('検証結果と証拠の境界','title'),P('4. 完了したオフライン検証（2026-10-16）','h1'),
            P('・Python自動テスト：103件すべて成功。'),
            P('・人工入力108条件で、無条件続行・Jev単独・Jev＋Qwen合意方式の<b>判定ロジック</b>を比較。これは実モデル画像の正解率を示すものではない。'),
            P('・SDF/ROSブリッジの静的構造とLiDAR/camera/odom/cmd_velの名前を確認。二物資拠点の理想運動学で、停止位置からのカメラ角度差は水約1.5度、医療約4.0度。実レンダリングでは未確認。'),
            P('・空き通路のLiDAR +inf（正常な無反射）と、NaN（不正観測）を区別する修正をテスト済み。'),
            P('5. 未検証の重要事項','h1'),
            P('・実際のJev/Qwen APIからの画像推論結果、および誤許可率／認識精度。'),
            P('・Ubuntu/NVIDIA GPU上での実Gazebo物理走行、カメラレンダリング、ROSブリッジと車輪の連携。'),
            P('・独自ワールドでのNav2ナビゲーション統合・動的再計画。v0.8の直接駆動はNav2ではない。'),
            P('・1〜3分のロボット走行MP4の取得。'),
            P('6. 今後の実測プロトコル','h1'),
            P('水/医療/無しの条件を含む実際のGazeboカメラ画像を人手でラベル付けし、同一画像でJev単独・Qwen単独・合意方式を比較する。誤許可率・誤拒否率・許可率に分母とWilson 95%区間を明示し、撮影ごとの画像ハッシュとモデルIDを記録する。危険物判定と衝突回避の性能は別実験に分離する。'),
            P('7. 限界と安全上の注意','h1'),
            P('画像/BoxはJev公式の実験的機能であり、AIの確率値が実際の安全保証になるわけではない。今回の停止監視は教育用シミュレーション向けで、実災害や実機での運用を保証しない。'),
            PageBreak(),P('優秀賞に向けた提出戦略','title'),P('8. 課題評価基準との対応','h1')]
    award=[['講座の観点','独自の貢献と実証条件'],
           ['創造性','現地観測で二段階の行動判断が変わる。成功・不一致分岐を映像で比較。'],
           ['技術力','Jev+Qwenの二重判断、ROSカメラ、LiDAR監視、走行ログを統合。'],
           ['実用性','異常時停止・誤許可と不要な出発拒否のトレードオフを評価。'],
           ['表現力','2分動画にロボット、画像、Jev/Qwen判断、失敗例、比較結果を表示。']]
    t=Table([[P(x,'tiny') for x in row] for row in award],colWidths=[35*mm,143*mm],hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9f1f4')),('VALIGN',(0,0),(-1,-1),'TOP'),
                          ('GRID',(0,0),(-1,-1),.35,colors.HexColor('#c2ccd5')),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    story += [t,Spacer(1,6*mm),P('9. 動画構成（約120秒、実録画のみをロボット動作証拠とする）','h1'),
              P('0〜13秒 課題と環境／13〜32秒 指示入力／32〜56秒 物資拠点へ移動／56〜75秒 ロボットカメラ→Jev＋Qwen判定／75〜95秒 避難所へ接近／95〜108秒 不一致時の停止例／108〜120秒 実測と制約。'),
              P('10. 提出に必要なこと','h1'),
              P('2026年11月2日（月）午前10時締切。OmniCampusへPDFとpublicのGitHub URL、YouTubeへ1〜3分のMP4をアップロードしURL提出。動画タイトルは「PAI最終課題_omnicampusアカウント名」。最低限「限定公開」。提出物は氏名・所属・メール・APIキーなどを一切含めない。'),
              P('11. 再現性・出典','h1'),
              P('同梱のREADME、docs/V08_EXECUTION_AND_VERIFICATION.md、docs/RESEARCH_SOURCES_V08.md、scripts/v08_verify.shを参照。課題の基準は同梱のassignment/Physical-AI応用1講座-最終課題.txt（10/8版）。Jev公式 https://typesafe.ai/blog/jev-1-14 、Qwen公式 https://www.alibabacloud.com/help/en/model-studio/qwen3-8-omni-flash 、Gazebo公式 https://gazebosim.org/docs/harmonic/ros2_integration/ を確認。'),
              Spacer(1,12*mm),P('提出前に必ず実Gazebo画像、実API推論、実測値、最終GitHub URLを追記してください。このPDFは「未提出ドラフト」です。','note')]
    def footer(canv,doc):
        canv.saveState();canv.setFont(fn,8);canv.setFillColor(colors.HexColor('#6b7280'))
        canv.drawString(16*mm,12*mm,'RescueMind v0.8 | 未提出ドラフト / 実Gazebo・実API未実測')
        canv.drawRightString(195*mm,12*mm,str(doc.page));canv.restoreState()
    doc=SimpleDocTemplate(str(OUT),pagesize=A4,rightMargin=16*mm,leftMargin=16*mm,
                          topMargin=16*mm,bottomMargin=18*mm,title='RescueMind v0.8 研究課題ドラフト')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    print('Wrote',OUT)
if __name__=='__main__':main()
