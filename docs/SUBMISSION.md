# 提出物と提出手順（Physical AI 応用1講座 最終課題）

締切：**2026-11-02（月）10:00 JST**。個人情報（氏名・所属・メール）は成果物に含めない（omnicampus アカウント名のみ可）。

| 提出物 | 場所 | 状態 |
|---|---|---|
| 説明資料PDF | `docs/report/説明資料_PAI最終課題_tetsutetsu.pdf`（`scripts/make_report.py --account tetsutetsu` で再生成） | 作成済み |
| GitHub リポジトリ（public） | https://github.com/fe2131-art/rescue-mind | **公開設定はご本人が変更** |
| 動画（MP4、1〜3分） | `outputs/video/PAI最終課題_tetsutetsu.mp4`（Git管理外、`scripts/make_demo_video.py` で再生成） | 作成済み |
| YouTube 投稿用テキスト | [`docs/YOUTUBE_DESCRIPTION.md`](YOUTUBE_DESCRIPTION.md)（タイトル・概要・倍速表記・チャプター・クレジット） | 作成済み |

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
