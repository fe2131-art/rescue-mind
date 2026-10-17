# 提出物と提出手順（Physical AI 応用1講座 最終課題）

締切：**2026-11-02（月）10:00 JST**。個人情報（氏名・所属・メール）は成果物に含めない（omnicampus アカウント名のみ可）。

| 提出物 | 場所 | 状態 |
|---|---|---|
| 説明資料PDF | `docs/report/説明資料_PAI最終課題_tetsutetsu.pdf`（`scripts/make_report.py --account tetsutetsu` で再生成） | 作成済み |
| GitHub リポジトリ（public） | https://github.com/fe2131-art/rescue-mind | **公開設定はご本人が変更** |
| 動画（MP4、1〜3分） | `outputs/video/PAI最終課題_tetsutetsu.mp4`（長さ・デモ・章立ては下の「提出する版」を自動生成。Git管理外、`scripts/make_demo_video.py` で再生成。章立ては `docs/video_chapters.json`） | 作成済み |
| YouTube 投稿用テキスト | [`docs/YOUTUBE_DESCRIPTION.md`](YOUTUBE_DESCRIPTION.md)（タイトル・概要・倍速表記・チャプター・クレジット） | 作成済み |

## 提出する版（v3.6）の要点

* **構成**：Qwen3.5-9B（ローカル・V100）。v3.6 はオーケストレータの既定値（危険の問い方 h36＋拡大切り出し、τ_h=0.05、横から見直す 0.4 m、回復探索・状況報告、DDS非同期）。
<!-- VIDEO:START -->
* **動画の4デモ**：①言い換えた指示でも配達 ②物資の取り違え → 別の拠点を探索して配達 ③欠品 → 両拠点を確認して停止 ④物資の陰に隠れた小さな火 → 正面では見えないが、横から見て検知して停止。
* **倍速の明記**：走行8倍速・確認動作3倍速・AI判断の瞬間は等速（画面左上に常時表示。YouTube概要欄にも記載）。
* **動画の長さと章立て**：約2分46秒（1〜3分の枠内）、章9個、評価の表3枚。章立ては `docs/video_chapters.json`（`scripts/make_demo_video.py` が出力）、概要欄は `scripts/make_youtube_description.py` が再生成。
<!-- VIDEO:END -->
* **主な数値**（すべて事前登録、`experiments/results/` の結果ファイルから生成）：
  * 評価E（ランダムな世界の閉ループ60試行）：期待どおり 60/60、誤配達 0件
  * 未使用の画像600枚 T1：誤許可 5/408（登録した規則 v3.4）、3/408（v3.5の規則）。物資の陰に一部しか見えない火が残る弱点
  * 評価G（対比較、新しい世界）：3視点（正面・左右0.4 m）のどれかで火が見えた16世界で、火があるのに配達した回数 11/16 → 1/16（McNemar正確検定 p=0.002）、火の無い世界での誤った停止 0/8（`g_summary.json`）。これらの火の多くは設計上、正面からは見えにくい（または見えない）ため、これは「横から見る効果」の測定である
  * 評価F（問い方＋切り出し）：火があるのに配達した回数 12/13 → 7/13（p=0.0625、有意でない。`f_summary.json`）
  * 未使用の画像600枚 T2：v3.5 でも誤許可 0/407（天井で改善は測れない）。Clef-Flash（Jev役）単独も 0/407（`t2_summary.json`）
* **限界**：すべてシミュレーション。「届ける」は現物確認と避難所Bへの接近までで、物資の把持・荷降ろし・受け渡しは行わない。評価Gの唯一の見逃しは、正面から完全に隠れ、横からも最小だった火。

## 提出前チェック

1. GitHub：Settings → General → Danger Zone → Change visibility → **Public**。Actions（offline tests）が緑であること。
2. YouTube：タイトル `PAI最終課題_tetsutetsu`、概要欄は `docs/YOUTUBE_DESCRIPTION.md` を貼付（倍速の明記・VOICEVOX のクレジットを含む）。
   公開（推奨）または限定公開、子ども向け「いいえ」、年齢制限「いいえ」、インスタントプレミアム公開はチェックしない。
3. omnicampus：PDF、GitHub URL、YouTube URL を提出。採点完了まで動画を削除・非公開にしない。

## 再生成コマンド（結果ファイルから自動生成、数値の手入力なし）

```bash
bash docker/run.sh python3 scripts/export_evidence.py experiments/results/campaign_D_ledger.jsonl
bash docker/run.sh python3 scripts/make_figures.py
python3 scripts/update_readme_results.py
bash docker/run.sh python3 scripts/make_report.py --account tetsutetsu
```
