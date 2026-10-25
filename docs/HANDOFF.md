# HANDOFF — RescueMind

作業を中断・文脈圧縮した後でも、**この最初の画面だけで**正確に再開できるようにまとめたもの。
構成：**現在地（今ここ）→ 履歴（要約）→ 参照（§2 実行環境・§3 コマンド・§4 落とし穴・§7 ファイルの地図）**。
旧版の全文（日付ごとに積み重なっていた節）は `docs/HANDOFF_ARCHIVE.md` に**一字も変えずに**残してある。細部（PID、当時の連鎖、日付ごとの判断の理由）が必要なときだけ見ればよい。
数値は結果ファイル（`experiments/results/*_summary.json`）と台帳から読み直したもの。文書の数値は `python3 scripts/check_consistency.py` が結果ファイルと突き合わせる（HANDOFF の数値は手で書いたので、結果が変わったらここも直す）。

---

## ★ 現在地（2026-10-25 完成。圧縮後はここだけ読めばよい）

**状態：完成。** `bash scripts/final_check.sh` → `FINAL_CHECK_DONE fails=0`（2026-10-25）。実験は凍結（`docs/FINAL_PLAN.md` の `EXPERIMENT_FREEZE`、ユーザーと合意）。新しい研究は登録しない。残りはユーザーの作業だけ（`docs/SUBMISSION_CHECKLIST.md`）。締め切り 2026-11-02 10:00 JST。

**成果物（すべて `main` に push 済み）**
| もの | 場所 | 状態 |
|---|---|---|
| 動画 v15 | `outputs/video/PAI最終課題_141628.mp4`（Git 管理外。YouTube タイトルは `PAI最終課題_141628`＝アカウントID、2026-10-25 ユーザー指示） | 175.0 s、1920×1080。v15 は v14 のナレーション・カードを平易な言葉に直したもの（I-177）。デモ4本（取り違え、記憶、「確認不要」、倉庫で左右0.8 mの追加視点が火を見つける＝JK の世界 GM041、run `0f97606079a94dfa`）、評価のまとめ（失敗は赤）、結び「失敗も残し、次の工夫につなげました」。走行8倍速・確認動作4倍速・判断は等速（左上に表示）。旧版 `_v14_backup.mp4`・`_v13_backup.mp4`、長すぎた版 `_v14a_over180.mp4` |
| 説明資料 | `docs/report/説明資料_PAI最終課題_tetsutetsu.pdf` | 本文10頁・全26頁、著者 tetsutetsu（ファイル名もアカウント名、課題の指定）。1頁目に審査向けの要点と提出情報、2頁目に審査基準表、試行錯誤の表（失敗した主張すべて） |
| 論文 | `docs/paper/main.pdf`、`supplement.pdf` | 本文8頁（9頁目は参考文献のみ）、要旨199語、補足46頁、参考文献384件（重複0） |
| README・YouTube 説明文 | `README.md`、`docs/YOUTUBE_DESCRIPTION.md` | 説明文 4,752 字（上限5000） |

**研究**：44本を事前登録（時刻証明26本すべてビットコインで確定、I-175）。最後の3本：JL（JL1〜JL3 成立：13/98 → 3/100）、IJ（IJ1・IJ3 成立、IJ2 不成立）、JM（JM1 不成立、JM2・JM3 成立）。論文で不成立の主張は23件：T1・F・T2・J・V4・W-b・IF1・S-perm・XD-eps・XD-rel・XD-cal・Q・YE2・YF4・JH1・QI1・QI2・QI3c・JC1・IJ2・JM1・IH1・IG1。すべて `scripts/trial_chain.py` の試行錯誤の表に置いてある。FINDINGS は 59 件。テスト関数は 1675 件。第三者採点の最新は第11回 **36.0/40**（`docs/evaluations/`）。

**圧縮後の確認手順（この順で。どれも数分）**
1. `git fetch origin && git status -sb`（`main` と `origin/main` が一致、未コミット0）
2. `bash scripts/final_check.sh`（`FINAL_CHECK_DONE fails=0`。文書の再ビルド・8頁・整合性・網羅・参考文献・試行錯誤・秘密情報・テスト・動画長さ・説明文字数を含む）
3. 動画：`ffprobe -v error -show_entries format=duration -of csv=p=0 outputs/video/PAI最終課題_141628.mp4`（60〜180）、10秒ごとのフレームを見る（`docs/FINAL_PLAN.md` の手順）
4. `python3 scripts/ingest_check.py JL IJ JM`（0件）、`python3 scripts/check_study_coverage.py`（0）、`python3 scripts/check_bib.py`（0）
5. `python3 scripts/secret_scan.py`（0件）、`python3 scripts/public_release_audit.py`（PASS）

**ユーザーの作業（アシスタントはしない）**：①動画 v15 を通して見る ②履歴の個人パス（`secret_scan.py --history` で235件、鍵・メールは0件）を (a) 残す／(b) 書き換える（コミットのハッシュが変わり、登録監査の作り直しが要る。チェックリスト 1b）③YouTube 投稿（タイトル `PAI最終課題_141628`）→ `python3 scripts/set_video_url.py '<URL>' --apply` ④public 化 → `gh run rerun`（CI の赤は Billing によるもので、public なら無料枠で動く）⑤omnicampus 提出 ⑥優秀生選出フォーム。加えて Q の目視確認、カーネル再起動と NVIDIA 更新。

**守ること**：公開設定を変えない／rm 禁止（`~/rescue-mind-trash/<日時>/` へ移す）／個人情報なし／履歴の書き換え・force push はユーザーが言うまでしない／明示したファイルだけ commit・push／sudo 不使用／研究の一覧は `make_registrations.STUDIES` からだけ作る／論文を直したら `check_bib.py` と `check_study_coverage.py` を 0 に／複数手順の commit は `set -e`／`build_paper.sh` を直接呼ばず `rebuild_docs.sh`。日本語で簡潔に報告し、最後にユーザーの作業を一行で念押しする。

**I-177（2026-10-25）**：ユーザー指摘「助言は『厳しくする』ことしかできない」のような意味の通りにくい言い回しを総点検し、README・説明資料・YouTube 説明文・動画・図・DEPLOYMENT を平易な言葉に直した（中心の考えは「見ていない情報では確認を省けない」）。あわせて説明資料の古い記述（B・IF2 が「実行中」、`**` の残り、「23件目」）と DEPLOYMENT の古い「結果が無い」を直した。英語の論文題目 *Advice May Only Tighten* は学術英語として残した。

**旧「最新」節と旧「現在地」**は `docs/HANDOFF_ARCHIVE.md` の末尾に一字も変えずに移した（2026-10-25）。

## 履歴（要約）— 旧 HANDOFF の日付ごとの節（全文は `docs/HANDOFF_ARCHIVE.md`）

* **旧 §1「現在の到達点（v3.6、10/17）」の表**：D/E/G/H/T1/T2/R/Z/P/K/J/P2/L/V/W の数値と v3.6 の既定構成（Qwen3.5-9B、v35、i35、τ_s=0.5、τ_h=0.05、h36＋tiles、横から見直す ±0.4 m、回復探索）。上の表に統合した。過去の評価の再現は各台帳の `stack_args` を使う。
* **旧 §5「現状（10/18 10 時ごろ）」**：方針（Jev は Clef-Flash、結果を分析して最大の弱点に絞る、実機なし）、v3.6 の既定構成、主な結果、10/17 の進捗（動画 v3.6、R・H・J・Z・P の事前登録と実行、第三者採点の開始、論文の章立て）。
* **10/17 13:10**：R（0/2304）、J の試運転（28.7 GiB）、Z・P 完了、命題を「観察」と「1 出動あたりの系」に変更、第三者採点 1 回目 28.0・2 回目 29.5。H 本番を 13:03 に開始。
* **10/17 夕方（利用上限で中断）**：H 53/112、再開手順（`finalize_results.sh`、`% CHECK-AFTER-H`、動画の作り直し、L のマージ、OpenTimestamps の質問）を記録。
* **10/17 16:20**：K（適合予測）、I-18（現場への 1 枚報告）、グラフィカルアブストラクト、連鎖 `final_chain.sh`・`post_j_chain.sh`・`after_p2_chain.sh` を作った。評価中は実行時コードを変えない規則。
* **10/17 16:50**：H 完了（主張はすべて成立）。危険な配達 20/32 → 0/32、114 → 79 秒。
* **10/17 17:15（重要）**：評価中に重い処理をして J の判断時間が 3〜7 秒から 25〜33 秒に延びた（J の事前登録に逸脱を記録、FINDINGS #23）。中央値の計算誤りを訂正（FINDINGS #22）。第三者採点 4 回目 31.5、模擬査読 3 回目 borderline。
* **10/17 17:25（★）**：連鎖 `final_chain`（J）→ `post_j_chain` → `render_after_film` → `after_p2_chain`（L）→ `after_l_chain`（V）→ `after_v_chain`（W）を並べた。study V（H のモデルの予測検証）の設計。
* **10/17 19:30**：J 完了（P1 成立、P2 不成立 → I-16 不採用）。第三者採点 5 回目 31.5/32.0。**中心の貢献 I-19「信頼できない入力は締める方向にしか使えない」**を立てた（`docs/design/I19_untrusted_inputs.md`、研究 A・S の設計、注入文 224 件を dev/test に分割）。
* **10/17 20:15**：P2 成立、L 実行中、第三者採点 6 回目 32.0。動画 2:53 に再描画。A に LLM フィルタ群を足して 162 run に。
* **10/17 21:00**：I-20（疑わしいときだけ視点を増やす）、I-21（現実的な倉庫と k 拠点）、文献調査（`LITERATURE_REVIEW.md`）、一貫性と頑健性の曲線、研究 Q の設計。
* **10/17 21:45**：L 完了（成立）、I-18 を main にマージ、V の予備走行合格、倉庫が Gazebo で読み込めた。模擬査読 5 回目への対応（保証の書き直し）。
* **10/17 22:00・23:00**：連鎖の並び（V → W → Q → 統合マージ → A）。統合ブランチ `i21-depot` に I-19〜I-22・軟拒否・scrutiny・研究 S/X/XD・信頼基盤テスト（変異体 196 個）・論文の再構成を集約。模擬査読 6 回目は「結果が設計どおりなら RA-L で weak accept 圏」。
* **10/17 23:30（★★）**：V 本番 160 run 実行中（50/160）、連鎖 `after_v`→`after_w`→`after_q`（統合マージ → A）。第三者採点 7 回目 33.0。
* **10/18 0:30（★★★）**：FINDINGS #26〜#28 の修正（fail-open、τ_h 未検証、記憶の自己固定）を i21-depot にマージ。I-24（助言の信用枠）完了。研究 IF・B を登録。I-23（z3 による機械検証）を Sonnet が実行。追加の連鎖 `after_a`・`after_s`。
* **10/18 2:30（★★★★）**：ユーザー指示「Sonnet はちょうど 1 つ、メインも改善作業」。I-23 の機械検証、I-24 v2（R7 の反例 4 件）、命題 2 の必要性、重みの固定（PINNED_REVISIONS）、B・IF の登録。HANDOFF は i21 でだけ編集する。第三者採点 8 回目を Sonnet が実行。
* **10/18 3:45（★★★★★）**：V 完了（モデルの予測は成立、記憶の安全は不成立）。I-22 の Gazebo 確認は合格（4 件）。動画セグメント 4 を撮影。S の看板確認・XD のスモーク確認は合格。
* **10/18 午前（★★★★★★）**：W 完了（見逃し 3/150 成立、双子 0/75 成立、先行手法の優位は不成立）。I-20 を v3.7 の既定に採用。`\Nfailed` を six に。第三者採点 8 回目 34.0/40、模擬査読 R8（borderline）。
* **10/18 09:08〜09:40（旧 HANDOFF の後に起きたこと）**：統合マージ `587f033` で登録 7 本が main に載る（`docs/REGISTRATIONS.md`）。A のパイロットが 09:14 に始まり、依頼文チャネルが全滅 → FINDINGS #30、i38 の候補と採用規則を固定。I-20 の構成の固定と元に戻す規則（XD で判定）、R8 の指摘への対応（主張の衛生）。
* **10/18 10:09〜10:40**：i38 を採用（I-25）、A の Amendment 1（2a1bab0）、最初のパイロット台帳を保存（2270812）、XD-R の写真を凍結（263ad8e）。論文（本文に 1 文、補遺 S9 に段落と修正表 S10）、登録監査（`tab_prereg` の Amendments 列は見出し数で数える。B は 0→2、A は 0→1、C は 0→1 に直った）、`docs/REGISTRATIONS.md` の Amendments 表、README・報告の生成器を更新。Amendment の文中の時刻（A は 10:30）と git の時刻（10:09）は違う。表は git の時刻を使う。
* **旧 §6「論文化で残っている作業」**：T1・E の結果の反映、図、遅延の内訳と VRAM の表、推敲。いずれも済み。未解決として、稀に 0.3 秒間送信が止まる現象の根本原因（I-09 で影響は除去済み）と実機での検証（用意できない）が残る。

---

## 2. 実行環境（ホスト：Ubuntu 22.04、Tesla V100 32GB、4コア、ROSはホストに無い）

* Docker イメージ
  * `rescuemind:jazzy-next`（**標準**、`docker/Dockerfile` の `STACK=next`）：ROS 2 Jazzy + Gazebo Harmonic + torch 2.8.0+cu126 + transformers 5.20、`nice` に `cap_sys_nice`。
  * `rescuemind:jazzy`（旧 v3.3 スタック：torch 2.5.1 + transformers 4.53）。図・PDF・テスト用のコンテナ `rm-dev` はこちら（IPAex フォントを apt で後入れ済み。再作成時は `docker exec -u 0 rm-dev bash -c 'apt-get update && apt-get install -y fonts-ipaexfont'`、ただし jazzy-next にはフォントが入っている）。
* 作業用コンテナ（`docker/run.sh` は repo を同じ絶対パスでマウント、HFキャッシュ `/hf`、host network、`--init --cap-add SYS_NICE`）
```bash
S=<scratch>   # 任意の一時ディレクトリ
RESCUEMIND_IMAGE=rescuemind:jazzy-next RESCUEMIND_DOCKER_EXTRA="-v $S:$S" RESCUEMIND_CONTAINER=rm-next bash docker/run.sh sleep infinity
RESCUEMIND_DOCKER_EXTRA="-v $S:$S" RESCUEMIND_CONTAINER=rm-dev bash docker/run.sh sleep infinity
docker exec rm-next rescuemind-entrypoint <command>     # entrypoint 経由で ROS と venv を source
docker run -d --name rm-voicevox -p 127.0.0.1:50021:50021 voicevox/voicevox_engine:cpu-latest   # ナレーション用
```
* モデル重みはホストの `~/.cache/huggingface`（Qwen2.5-VL-3B, SmolVLM2, Qwen3-VL-8B, Qwen3.5-4B/9B 取得済み）。実行時は `HF_HUB_OFFLINE=1`。
* ポート：VLM 8765（オーケストレータが自動起動）、VOICEVOX 50021。ROS_DOMAIN_ID=73、GZ_PARTITION=rescuemind_1008。
* **同時に2つのスタックを走らせない**（同じ ROS ドメイン / Gazebo パーティション）。

## 3. 主要コマンド

```bash
# 1試行（例：取り違え）
docker exec rm-next rescuemind-entrypoint python3 scripts/v32_orchestrate.py --run --scenario live --scene swapped \
  --model Qwen/Qwen3.5-9B --prompt-set v35 --intent-backend llm --intent-prompt i35 --recovery --explain --capture-rosbag \
  --instruction 'Bの避難所にペットボトルの水を運んで'     # 追加: --hazard-at medicine / --lighting dim_evening / --distractor-at water / --film
# 事前登録キャンペーン（台帳に追記、中断しても再開可）
docker exec rm-next rescuemind-entrypoint python3 scripts/run_campaign.py --protocol experiments/v34_protocol.json \
  --ledger experiments/results/campaign_D_ledger.jsonl -- <凍結構成のフラグ>
# 成果物の再生成（数値の手入力なし）
docker exec rm-dev rescuemind-entrypoint python3 scripts/export_evidence.py experiments/results/campaign_D_ledger.jsonl
docker exec rm-dev rescuemind-entrypoint python3 scripts/make_figures.py
python3 scripts/update_readme_results.py
docker exec rm-dev rescuemind-entrypoint python3 scripts/make_report.py --account tetsutetsu
docker exec rm-dev rescuemind-entrypoint python3 scripts/make_video_plan.py --deliver a93d6a9cc8704e6c --recover 8b54abfb36454b27 --fire a213a61bc53e4787
docker exec rm-dev rescuemind-entrypoint python3 scripts/make_demo_video.py --plan docs/video_plan.json --out outputs/video/PAI最終課題_141628.mp4 --narrate 2
# 開発セット・モデル比較
scripts/robust_devset_build.py, scripts/vlm_devset_eval.py, scripts/robust_devset_report.py, scripts/model_comparison_v35.sh, scripts/model_selection_table.py
scripts/intent_eval.py --method hybrid --model <id> --split dev_v35|held_out_v34   # held-out はチューニングに使わない
```
デモ収録 run（`--film` 付き。**旧版の動画の run。現行の動画の run は §5 を参照**）：deliver `a93d6a9cc8704e6c`、recover `8b54abfb36454b27`、fire `a213a61bc53e4787`（`outputs/runs/` 内、Git管理外）。現行の動画の run は「現在地」E を参照。

## 4. 落とし穴（実際に踏んだもの）

* `pkill -f <pattern>` を `bash -c '...pattern...'` の中で使うと**自分自身のシェルも殺す**（exit 143）。スクリプトファイルから実行する。
* サーバ再起動直後は**古いサーバがまだ応答**することがある → `while curl -s -m 2 http://127.0.0.1:8765/health; do sleep 1; done` で消えるのを待つ。
* `nice` はファイルケーパビリティ付き → その exec は glibc セキュアモードで **LD_LIBRARY_PATH が消える**。`nice` は必ず「ROS を source するシェル」の外側に置く（`prioritised(shell_exec(...), n)`）。シェルスクリプト内は `renice -n N -p $$`。テスト `tests/test_v34_priority_wrapping.py`。
* ROS の `setup.bash` は `set -u` と相性が悪い → `set +u; source ...; set -u`。
* 画像トピックは Reliable QoS（`rescuemind/ros_qos.py`）。Best Effort だと 0.9 MB 画像が大量に欠落。
* 4コアのホストは CPU が飽和気味（ロードアベレージ約3.9）。**キャンペーン中に重い処理（動画合成・音声合成・ビルド）をしない**。キャンペーン中に実行時コードを編集しない（各試行がファイルを読み直す）。
* 非rootユーザーには `--cap-add` だけでは権限が渡らない（ファイルケーパビリティが必要）。
* Qwen3.5 は思考モードが既定 → `enable_thinking=False`（サーバで対応済み）。FP16 で非有限 logits なら判断拒否。
* 動画は **3分以内**（現在 2:53）。倍速は区間ごとに画面表示（走行8倍、確認3倍、判断の瞬間は等速）。


## 7. 主要ファイルの地図

* 現在地・履歴：このファイル。旧版の全文：`docs/HANDOFF_ARCHIVE.md`。
* `docs/ARCHITECTURE.md`（全体フロー図）、`docs/DESIGN_DECISIONS.md`（D1–D15）、`docs/IMPROVEMENT_LOG.md`（I-01–I-24）、`docs/FINDINGS.md`（実行で見つけた59件）、`docs/REVIEW_AND_PLAN.md`（審査基準別レビュー）。
* `docs/REGISTRATIONS.md`（事前登録の台帳：main に載った最初のコミットと sha256）、`docs/REPRODUCE.md`（クリーンな Ubuntu＋NVIDIA 環境での 3 段階の再現手順）、`docs/REPRODUCIBILITY.md`。
* `docs/evaluations/`（第三者採点、第1〜8回と固定の指示文）、`docs/paper/`（論文・補足・`REVIEW_NOTES*.md`・`LITERATURE_*.md`・`PROOF_REVIEW.md`）、`docs/report/`（説明資料）、`docs/design/`（I-19〜I-24 の設計、動画 v5 の計画）。
* `experiments/`（事前登録 `PREREGISTRATION_*.md`・プロトコル・開発セット・台帳 `results/campaign_*_ledger.jsonl`・要約 `results/*_summary.json`）。
