# 提出チェックリスト（ご本人用）

**締切：2026-11-02（月）10:00 JST**（提出開始は 2026-10-19）。課題文の要件は [`SUBMISSION.md`](SUBMISSION.md)（要件チェック表）にある。
omnicampus アカウント名は `tetsutetsu`。コマンドはすべて `~/work/rescue-mind`（ブランチ `main`。ブランチは `main` だけ）で実行する。
**公開設定の変更・YouTube への投稿・フォーム提出はご本人だけが行う**（アシスタントは行わない）。

流れ：**①アシスタントの最終確認 → ②YouTube → ③URL を文書に入れる → ④リポジトリを public にする → ⑤フォーム提出**。
余裕を見て **10/30（金）までに提出**する。

---

## 1. 渡す前の最終確認（アシスタントが行う。ご本人は結果の報告を読む）

| # | 確認 | コマンド・場所 | 合格 |
|---|---|---|---|
| 1 | 最新にする | `git fetch origin && git status -sb`（`main` が `origin/main` と一致） | 差分なし |
| 2 | 結果の反映（GPU を使わない） | `make finalize`（= `bash scripts/finalize_results.sh`。キャンペーン終了後） | FAIL なし |
| 3 | 文書と結果ファイルの一致 | `python3 scripts/check_consistency.py` | **0 mismatch**（終了コード 0） |
| 4 | 単体テスト | `make test`（`docker exec rm-dev rescuemind-entrypoint ...` で実行） | 全件成功 |
| 5 | **最終版かスナップショットか** | 下の判定 | 下記 |
| 6 | 動画 1〜3 分 | `ffprobe -v error -show_entries format=duration -of csv=p=0 ~/work/rescue-mind/outputs/video/PAI最終課題_tetsutetsu.mp4` | 60 以上 180 以下（秒）。続けて `python3 scripts/update_submission_facts.py`（`docs/SUBMISSION.md` の実測値を更新）。`docs/video_chapters.json` の終端と一致 |
| 7 | 倍速表示 | 下の「倍速の目視」 | 走行 8 倍速・確認 3 倍速が画面左上に出ている |
| 8 | 概要欄が上限内 | `sed -n '/^## 概要欄/,/^## 公開設定チェック/p' docs/YOUTUBE_DESCRIPTION.md \| sed '1d;$d' \| wc -m` | 5000 **文字**以下（YouTube Studio の上限は文字数。生成側は 4900 文字で抑える。2026-10-20 時点は約 3700 文字） |
| 9 | レポートのファイル名・著者 | `ls docs/report/`、`docker run --rm -v "$PWD/docs/report:/w:ro" rescuemind:latex pdfinfo "/w/説明資料_PAI最終課題_tetsutetsu.pdf" \| grep -E 'Author\|Pages'` | ファイル名は **`説明資料_PAI最終課題_tetsutetsu.pdf`** だけ。Author は `tetsutetsu` |
| 10 | 個人情報・秘密情報の検査 | `python3 scripts/secret_scan.py --history` と `python3 scripts/public_release_audit.py` と `python3 -m unittest tests.test_no_personal_paths` | いずれも指摘 0 / PASS。動画の画面・ナレーションに氏名が無いことは**目視**（下記） |
| 11 | ライセンス・第三者表記 | `LICENSE`（MIT）、[`THIRD_PARTY.md`](THIRD_PARTY.md)、`grep -c 'VOICEVOX:四国めたん' docs/YOUTUBE_DESCRIPTION.md README.md` | 両方 1 以上（クレジット必須）。第三者の重み・画像・音声・動画を同梱していない（`THIRD_PARTY.md` の冒頭） |
| 12 | `main` が最終版 | `git fetch origin && git status -sb`、`git log origin/main -1 --format=%h` | `main` が `origin/main` と同じ（GitHub に見えるのは `main`） |
| 13 | GitHub Actions | `gh run list -R fe2131-art/rescue-mind -L 3` | `main` の最新が success（2026-10-18 時点は赤。下の「Actions」参照） |

**5. 最終版かスナップショットか**
* `make paper FINAL=1` が成功する（`TBD` も `(pending)` も残っていない）＝全研究の結果が揃っている → **最終版**。`docs/report/説明資料_PAI最終課題_tetsutetsu.pdf` をそのまま提出する。
* 失敗する（結果の出ていない研究がある）→ **スナップショット**：`make snapshot`（結果の無い研究は「登録済み・提出時点で未実施」と書かれ、`TBD`・`pending` が消える）→ `bash scripts/build_snapshot.sh --apply`（README と `docs/YOUTUBE_DESCRIPTION.md` に反映）→ `python3 scripts/check_consistency.py --snapshot`（0 mismatch）。**提出する PDF は `docs/snapshot/report/説明資料_PAI最終課題_tetsutetsu.pdf`**。リポジトリの `docs/report/` の PDF も同じものに置き換える（旧ファイルは `~/rescue-mind-trash/<日時>/` へ移す。`rm` は使わない）。論文は `docs/snapshot/paper/main.pdf`。
* 判断した結果（どちらにしたか）をアシスタントがご本人に報告する。

**倍速の目視（#7・#10）**：
```bash
mkdir -p ~/rescue-mind-check && V=~/work/rescue-mind/outputs/video/PAI最終課題_tetsutetsu.mp4
for t in 20 55 95 130; do nice -n 19 ffmpeg -v error -y -ss $t -i "$V" -frames:v 1 ~/rescue-mind-check/f_$t.png; done
```
4 枚（各デモの途中）を開き、左上の倍速表示を確認する。音声は一度通して聞き、氏名・所属・メールが出ないことを確認する。
`docs/video_chapters.json` の `speed` が走行 8 倍速・確認 3 倍速・AI 判断は等速になっている。YouTube 概要欄にも同じ文（「倍速表示」）が入っている。

**チャプターについて**：`docs/video_chapters.json` に 10 秒未満の章がある場合、`make_youtube_description.py` が警告を出す。YouTube はチャプターを無視することがあるが、課題の要件ではないので提出に支障はない（気になる場合は概要欄の末尾の時刻つき章立てだけ消してよい）。

**Actions について**：`.github/workflows/test.yml` は単体テストと `scripts/public_release_audit.py` を実行する。2026-10-18 時点で赤だった原因は 2 つ（浅い clone では履歴を使う `REGISTRATIONS.md` の検査が通らない → `fetch-depth: 0` に修正済み。`public_release_audit.py` が `noreply@anthropic.com` と第三者コード `worlds/assets/` のメールを誤検出 → 許可リストを追加済み）。修正後の push で緑になったことを #13 で確認する。

---

## 2. YouTube（ご本人）

アップロードするファイル：`~/work/rescue-mind/outputs/video/PAI最終課題_tetsutetsu.mp4`（MP4、Git 管理外）。

1. YouTube Studio → 作成 → 動画をアップロード。
2. **タイトル**：`PAI最終課題_tetsutetsu`（課題の指定どおり）。
3. **概要欄**：次のコマンドの出力をそのまま貼る（倍速の明記・VOICEVOX のクレジット・コードの URL・チャプター〔0:00 から〕を含む）。出力は `docs/YOUTUBE_DESCRIPTION.md` の「概要欄」の節。
   ```bash
   sed -n '/^## 概要欄/,/^## 公開設定チェック/p' docs/YOUTUBE_DESCRIPTION.md | sed '1d;$d'
   ```
4. **視聴者**：「いいえ、子ども向けではありません」。**年齢制限**：「いいえ」（18 歳以上に限定しない）。
5. **公開設定**（課題の指定）：**限定公開は必須（最低条件）、公開（全体公開）は推奨（優秀生選出で公開なら加点）**。→ **「公開」を選ぶ**。限定公開でも提出は成立する。
6. 「**インスタントプレミアム公開**」には**チェックしない**。**予約公開は使わない**（即時公開）。使う場合は締切（2026-11-02 10:00 JST）より前の日時を必ず設定する。
7. 公開後、動画ページの URL（`https://www.youtube.com/watch?v=...`）をコピーする。ログアウト状態（シークレットウィンドウ）で開けること、再生できること、概要欄が貼れていることを確認する。
8. **採点完了まで動画を削除・非公開にしない**。

---

## 3. URL を文書に入れる（1 コマンド）

```bash
python3 scripts/set_video_url.py 'https://www.youtube.com/watch?v=XXXXXXXXXXX'          # まず確認（既定は dry-run。何も書かない）
python3 scripts/set_video_url.py 'https://www.youtube.com/watch?v=XXXXXXXXXXX' --apply   # README.md・docs/SUBMISSION.md に書き、説明資料 PDF を再生成
```
* `youtu.be/...` 形式でもよい（`watch?v=` 形式に正規化される）。11 文字の ID でない URL は拒否される。
* スナップショットで提出する場合は `--snapshot` を付ける（`docs/snapshot/report/` の PDF にも URL が入る）。docker を使わないときは `--no-report`。
* 書き換える場所：`README.md` の「動画」の項（`<!--VIDEOURL-->` の間）、`docs/SUBMISSION.md` の「YouTube の動画URL」、説明資料 PDF の「動画」の行（`make_report.py --video-url`）。取り消しは `--clear --apply`。
* 続けて：
  ```bash
  python3 scripts/check_consistency.py        # 0 mismatch（スナップショットなら --snapshot）
  git add README.md docs/SUBMISSION.md docs/report && git commit -m "docs: YouTube URL" && git push origin main
  ```
  **GitHub の既定ブランチ `main` に URL が入っていること**を、public にしたあとで README の表示で確認する（手順 4-3）。
* 提出する PDF は、このコマンドで再生成された `docs/report/説明資料_PAI最終課題_tetsutetsu.pdf`（スナップショットは `docs/snapshot/report/` の同名ファイル）。

---

## 4. リポジトリを public にする（ご本人。アシスタントは変更しない）

**事前に満たすこと**（1 のチェックで確認済みであること）：
* [ ] 秘密情報なし：`python3 scripts/secret_scan.py --history` → `RESULT: 0 finding(s)`（追跡ファイルと全履歴の鍵・トークン・メール・秘密鍵のファイル名を検査。値は表示しない）
* [ ] 個人情報なし：コミットの作者・コミッターは `fe2131-art`（GitHub の noreply アドレス）だけ。PDF の Author は `tetsutetsu`。ホームのパスは `tests/test_no_personal_paths.py` が追跡ファイル全体で検査
* [ ] 大きなファイルなし：追跡ファイルの最大は 約 4.6 MB（`secret_scan.py` が 10 MB 超を警告。GitHub の上限は 100 MB）。動画・重み・`outputs/runs/` は `.gitignore` で除外
* [ ] LFS なし：`.gitattributes` は無い（`secret_scan.py` が `filter=lfs` を検出する）
* [ ] 課題文（`Physical-AI*.txt`）・zip・`.claude/` は未追跡（`.gitignore` 済み）
* [ ] `main` が最終版（1 の #12）、Actions が緑（#13）、README の動画の項に YouTube の URL（3 の手順）

**手順**：
1. https://github.com/fe2131-art/rescue-mind → Settings → General → 一番下の Danger Zone → **Change visibility → Make public**（確認のためリポジトリ名を入力）。
2. Settings → Branches で既定ブランチが `main` であることを確認する。
3. シークレットウィンドウで https://github.com/fe2131-art/rescue-mind を開く：README が表示される、動画のリンクが YouTube に飛ぶ、説明資料 PDF のリンクが開く、画像（hero GIF）が出る。
4. （任意）別の場所で `git clone https://github.com/fe2131-art/rescue-mind.git` が認証なしで成功する。

---

## 5. 提出フォーム（omnicampus。2026-10-19〜11-02 10:00）

課題文（§6）が示す提出物と、その答えの場所：

| フォームの項目 | 答え | 場所・取得方法 |
|---|---|---|
| ① レポート（PDF、ファイル名は `説明資料_PAI最終課題_omnicampusアカウント名.pdf`） | `説明資料_PAI最終課題_tetsutetsu.pdf` | `docs/report/説明資料_PAI最終課題_tetsutetsu.pdf`（スナップショットは `docs/snapshot/report/`。#5 の判定に従う。URL 入りの再生成後のもの） |
| ② GitHub のリポジトリ URL（公開設定は必ず public） | `https://github.com/fe2131-art/rescue-mind` | 4 で public にしたあと。シークレットウィンドウで開けること |
| ③ YouTube の動画 URL（指定フォーム） | `https://www.youtube.com/watch?v=...` | 2 で取得した URL（3 で README・PDF に入れたものと同じ） |
| アカウント名 | `tetsutetsu` | タイトル・PDF のファイル名に使用済み |

フォームの実際の項目名が上と違う場合は、課題文のとおりに上の 3 つ（PDF・GitHub URL・YouTube URL）を入れる。
提出後：提出完了の画面（またはメール）を保存する。**採点完了まで、動画の削除・非公開、リポジトリの private 化をしない。**

---

## 参照

| 内容 | 場所 |
|---|---|
| 課題文と要件チェック表 | [`SUBMISSION.md`](SUBMISSION.md)（原文は `~/work/rescue-mind/Physical-AI応用1講座-最終課題.txt`、未追跡） |
| YouTube 投稿用テキスト | [`YOUTUBE_DESCRIPTION.md`](YOUTUBE_DESCRIPTION.md)（`scripts/make_youtube_description.py` が生成） |
| 動画の章立て | [`video_chapters.json`](video_chapters.json)（`scripts/make_demo_video.py` が出力） |
| 実測値（動画の長さ・PDF のページ数） | `scripts/update_submission_facts.py` |
| URL の差し込み | `scripts/set_video_url.py`（テスト：`tests/test_set_video_url.py`） |
| 秘密情報・個人情報の検査 | `scripts/secret_scan.py`、`scripts/public_release_audit.py` |
| 第三者のライセンス | [`THIRD_PARTY.md`](THIRD_PARTY.md) |
| 現在地・再開手順 | [`HANDOFF.md`](HANDOFF.md) |
