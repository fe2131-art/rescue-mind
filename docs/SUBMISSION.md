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
* **動画の4デモ**：①言い換えた指示でも配達 ②物資の取り違え → 別の拠点を探索して配達 ③出動をまたぐ記憶 → 直行 ④物資の陰に隠れた小さな火 → 正面では見えないが、横から見て検知して停止。
* **倍速の明記**：走行8倍速・確認動作3倍速・AI判断の瞬間は等速（画面左上に常時表示。YouTube概要欄にも記載）。
* **動画の長さと章立て**：約2分53秒（1〜3分の枠内）、章9個、評価の表1枚。章立ては `docs/video_chapters.json`（`scripts/make_demo_video.py` が出力）、概要欄は `scripts/make_youtube_description.py` が再生成。
<!-- VIDEO:END -->
* **主な数値**（すべて事前登録、`experiments/results/` の結果ファイルから生成）：
  * 評価E（ランダムな世界の閉ループ60試行）：期待どおり 60/60、誤配達 0件
  * 未使用の画像600枚 T1：誤許可 5/408（登録した規則 v3.4）、3/408（v3.5の規則）。物資の陰に一部しか見えない火が残る弱点
  * 評価G（対比較、新しい世界）：3視点（正面・左右0.4 m）のどれかで火が見えた16世界で、火があるのに配達した回数 11/16 → 1/16（McNemar正確検定 p=0.002）、火の無い世界での誤った停止 0/8（`g_summary.json`）。これらの火の多くは設計上、正面からは見えにくい（または見えない）ため、これは「横から見る効果」の測定である
  * 評価F（問い方＋切り出し）：火があるのに配達した回数 12/13 → 7/13（p=0.0625、有意でない。`f_summary.json`）
  * 未使用の画像600枚 T2：v3.5 でも誤許可 0/407（天井で改善は測れない）。Clef-Flash（Jev役）単独も 0/407（`t2_summary.json`）
* **限界**：すべてシミュレーション。「届ける」は現物確認と避難所Bへの接近までで、物資の把持・荷降ろし・受け渡しは行わない。評価Gの唯一の見逃しは、正面から完全に隠れ、横からも最小だった火。

## 要件チェック表（課題 10/8版 と成果物の対応、2026-10-17 時点）

状態：**済**／**要対応（ユーザー）**＝ご本人のみ可能／**要対応（自動で今夜）**＝キャンペーン終了後に再生成。

| 要件（課題の出典） | 対応する成果物・場所 | 状態 |
|---|---|---|
| 動画：ロボットがタスクを実行する様子（§1・§2） | 実レンダリングの Gazebo 映像、実走デモ4本（`outputs/video/PAI最終課題_tetsutetsu.mp4`） | 済 |
| 動画の長さ 1〜3分 | 173.0秒（約2分53秒、`docs/video_chapters.json` の終端と一致）。1920×1080、H.264/AAC | 済 |
| 倍速は明記（動画内または概要欄） | 動画内の左上に常時表示（走行8倍速・確認動作3倍速・AI判断は等速）＋ `docs/YOUTUBE_DESCRIPTION.md` の概要欄文面 | 済（概要欄への貼付は下の YouTube 投稿時） |
| 動画形式 MP4 | 上記 mp4 | 済 |
| 動画タイトル `PAI最終課題_omnicampusアカウント名` | `PAI最終課題_tetsutetsu`（`YOUTUBE_DESCRIPTION.md`） | 済（YouTube 投稿時に入力） |
| YouTube へアップロード、URL をフォームへ提出 | 動画ファイルと投稿用テキストは用意済み。**URL は未取得** | **要対応（ユーザー）** |
| 公開設定：限定公開は必須（最低条件）、公開は推奨（加点） | 公開（推奨）で投稿。`YOUTUBE_DESCRIPTION.md` に手順 | **要対応（ユーザー）** |
| 「子ども向け」いいえ／年齢制限 いいえ／インスタントプレミアム公開はチェックしない | 同上のチェックリスト | **要対応（ユーザー）** |
| 予約公開を使う場合は締切までの日時を設定／採点完了まで削除・非公開にしない | 即時公開を推奨（予約公開は使わない） | **要対応（ユーザー）** |
| レポート（PDF）：概要・目的・工夫した点 | `docs/report/説明資料_PAI最終課題_tetsutetsu.pdf`（本文5ページ＋付録。ページ数は再生成で変わるので `pdfinfo` で確認する。1章 課題の概要と目的、2〜4章 AIの活用と工夫、審査基準との対応表、限界。PDF の著者欄は `tetsutetsu` のみ） | 済 |
| PDF ファイル名 `説明資料_PAI最終課題_omnicampusアカウント名.pdf` | 上記ファイル名のとおり | 済 |
| PDF を最新の結果で再生成 | J・L・P2 の結果は反映済み。A・S・V・W・XD・X・Q は結果が出るまで「未実行／実行中」と表記される。結果が出るたびに `scripts/make_report.py --account tetsutetsu`（rm-dev）で再生成し、`make check` で README・YouTube・論文・説明資料の数値が結果ファイルと一致することを確認する | 済（結果が出るたびに再生成） |
| 使用したコード一式 | 本リポジトリ（`rescuemind/`, `ros/`, `scripts/`, `tests/`, `docker/`, `worlds/`, `configs/`、動かし方は README） | 済 |
| リポジトリの公開設定は必ず public | https://github.com/fe2131-art/rescue-mind（現在の設定はご本人が確認・変更） | **要対応（ユーザー）** |
| 個人情報（氏名・所属・メール）を成果物に含めない | 公開前チェックで検出なし：メール・所属名なし、git のコミッターは `fe2131-art`（noreply アドレス）、PDF の著者は `tetsutetsu`、CITATION.cff は `tetsutetsu`。動画は日本語ナレーション（VOICEVOX）と Gazebo 映像のみ | 済（動画のナレーション・画面に氏名が無いことは提出前に一度目視を推奨） |
| 未追跡の `.claude/`（作業用の一時ファイル）をリポジトリに入れない | `.gitignore` に `.claude/` を追加済み | 済 |
| 課題文・配布物を含めない／明らかに関係のないファイルを提出しない | 課題文 `Physical-AI*.txt` と引継ぎ zip は `.gitignore` 済みで未追跡 | 済 |
| AI の使用（必須。推論のみでも可） | ローカル LLM（指示の理解）・VLM Qwen3.5-9B（現物・火災の確認、状況報告）で推論。報告 PDF の「AIの活用」に明記 | 済 |
| 剽窃・サンプルの丸写しでないこと／サンプルを元にした工夫点をレポートに明記 | 独自のタスク設計（確認してから届ける、横から見直す、検証つき記憶）。工夫点は PDF の審査基準の対応表と README「工夫した点」 | 済 |
| ライセンス | `LICENSE`（MIT）。使用モデルのライセンスは README 末尾に記載 | 済 |
| README（概要・動かし方・動画リンク） | `README.md`。動画の項は「YouTube（提出時にURLを記載）」のまま | **要対応（ユーザー）**（YouTube の URL を貼付） |
| 動画の URL を PDF にも載せる（任意） | URL 取得後に `make_report.py --account tetsutetsu --video-url <URL>` で再生成 | **要対応（ユーザー）**（任意。URL が必要） |
| omnicampus のフォームで提出（PDF＋GitHub URL＋YouTube URL） | 提出開始は 2026-10-19（月）、**締切 2026-11-02（月）10:00 JST** | **要対応（ユーザー）** |
| 生成AIの利用開示の要求 | 課題文に要求なし（AI 利用は課題内容としての「ロボットが使う AI」のみ）。開発支援の AI 利用は求められていないため記載不要 | 済（該当なし） |

ユーザーが行う作業（順番）：① リポジトリを public にする → ② YouTube に投稿して URL を取得 → ③ README の「YouTube（提出時にURLを記載）」を URL に置き換えてプッシュ（必要なら PDF も再生成）→ ④ omnicampus で提出（2026-10-19〜11-02 10:00）。

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
