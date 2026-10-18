# HANDOFF — RescueMind

作業を中断・文脈圧縮した後でも、**この最初の画面だけで**正確に再開できるようにまとめたもの。
構成：**現在地（今ここ）→ 履歴（要約）→ 参照（§2 実行環境・§3 コマンド・§4 落とし穴・§7 ファイルの地図）**。
旧版の全文（日付ごとに積み重なっていた節）は `docs/HANDOFF_ARCHIVE.md` に**一字も変えずに**残してある。細部（PID、当時の連鎖、日付ごとの判断の理由）が必要なときだけ見ればよい。
数値は結果ファイル（`experiments/results/*_summary.json`）と台帳から読み直したもの。文書の数値は `python3 scripts/check_consistency.py` が結果ファイルと突き合わせる（HANDOFF の数値は手で書いたので、結果が変わったらここも直す）。

---

## 現在地（2026-10-18 10:00）— 圧縮後はここから

### A. ユーザーの方針（必ず守る）

* **サブエージェントはちょうど1つ（Sonnet 5.5、`model: sonnet`）を常に動かす。** 同時に2つにしない。終わったら次を起動する。止まったら SendMessage で続きから再開させる。
* **メインの自分も改善作業をする**（サブエージェント任せにしない）。結果を分析し、最大の弱点に絞って、事前登録した評価で確かめる。だらだら改善を続けない。ユーザーが「ストップ」と言うまで自律的に改善を続ける。
* リポジトリの**公開設定（private → public）は絶対に変更しない**。公開と YouTube 投稿は**ユーザーが行う**。push は可。
* ユーザーへの質問・説明は**日本語・簡潔**に。omnicampus のアカウント名は `tetsutetsu`。
* **事前登録してから走らせる。失敗した主張も消さずに載せる**（論文で不成立の主張は六つ：T1 の「2% 未満」、F、T2、J、V4、W-b）。改善は `docs/IMPROVEMENT_LOG.md` に「動機→仮説→変更→計測(Before/After)→判断」で書き、**コミットの先頭は `I-xx`**。コミットは必ず push する。
* **sudo は使わない**（docker グループ権限だけで全て動く）。必要になったらユーザーに依頼する。
* **`rm` は使わない**（2026-10-18 ユーザー指示。`rm -rf`・`git clean`・`unlink`・`find -delete` も同じ）。消したいものは `~/rescue-mind-trash/<日時>/` に相対パスのまま移し、移したものをユーザーに伝える。削除はユーザーが確認してから行う。サブエージェントへの指示にも必ず書く。
* **個人情報を入れない**（ホームのパス、スクラッチパッドのパスは `tests/test_no_personal_paths.py` が落とす。文書では `<scratchpad>`、`<user>` と書く）。
* 動画は **1〜3 分**（現在 2:53）。倍速は区間ごとに画面表示（走行 8 倍、確認 3 倍、判断の瞬間は等速）。
* 説明資料のファイル名は **`説明資料_PAI最終課題_tetsutetsu.pdf`**（`docs/report/`）。**締切は 2026-11-02 10:00 JST**。
* 評価基準（創造性・技術力・実用性・表現力）と、論文として通用する水準を常に意識する。実機は用意できない → シミュレーションでできることはすべてやる。
* 当初計画（Jev＋Qwen の 2 つの AI による確認）から勝手に外れない（Jev の役割はローカルの Clef-Flash。J で実装・検証し、採用しなかった結果を論文に載せた）。
* 評価（GPU キャンペーン）の実行中は、重い処理（ビルド・テスト・図・動画）と実行時コードの編集をしない。CPU を使うときは `nice -n 19`。
* 第三者採点（Sonnet 5.5 に `docs/evaluations/EVALUATOR_PROMPT.md` で採点させる）を定期的に行い、点数を上げる改善点トップ5に沿って直す。最新は第8回 **34.0/40**（`docs/evaluations/EVAL_2026-10-18_8.md`）。模擬査読は R8 まで（`docs/paper/REVIEW_NOTES_R8.md`、判定は borderline）。

### B. ブランチの考え方

* **`main`** = 事前登録とマージ済みの成果。メインのチェックアウトは `rescue-mind/`（GPU キャンペーンはここで走る。`rm-next` コンテナを使う）。研究の登録は「`main` に載った最初のコミット」で成立する（`docs/REGISTRATIONS.md`、`git log --first-parent` で検証）。
* **`i21-depot`** = 統合ブランチ。worktree は `rescue-mind/.claude/worktrees/i21`。**論文・説明資料・README・docs はここで編集する。** 再開するときは最初に `git pull --ff-only origin i21-depot`。
* **統合マージ `587f033`（2026-10-18 09:08）で i21-depot を main に入れた**（I-19〜I-24、研究 A・B・IF・Q・S・X・XD の登録を含む）。以後 main から i21 への取り込みはしていない：main には `caebcb7`（W-b の入力 `devset_t1_i11_h36_{full,tiles}.json`。`w_analysis.py` を再実行するのに要る）が i21 に無い。次の機会に `git merge origin/main` で i21 に取り込む。
* **HANDOFF は i21 でだけ編集する**（main 側でも編集すると、main へのマージで衝突して連鎖が止まる）。マージされるまで、この方針を守る。
* **main の作業ツリーに、i21 が追跡しているファイルを置かない**（untracked の同名ファイルがあると main へのマージが失敗する）。例：`experiments/results/xd_smoke_ok` は i21 が追跡、すでに main にもある。新しい `*_ok` や結果ファイルを main 側で作る前に `git ls-tree -r origin/i21-depot --name-only | grep <名前>` で確かめる。
* 現在 main の作業ツリーにある untracked（作業用の記録、削除しない）：`campaign_A_pilot_ledger.jsonl`（A のパイロット。`a_run.sh` が次にコミットする）、`experiments/vlm_testset_s/`・`vlm_testset_w/`・`worlds/vlm_devset_hazard2/`、`memory_film/` 等。i21 側にも untracked の描画物（`experiments/vlm_testset_s/`・`vlm_testset_xd/`・`worlds/testset_s/`・`worlds/testset_xd/`）があるが、コミットしない。

### C. 全研究の結果（すべて事前登録。数値は結果ファイルから）

| 研究 | 何を測ったか | 結果（状態） |
|---|---|---|
| D（42 試行） | 固定配置の閉ループ（v3.4） | **完了**。42/42、誤配達 0。台帳は 44 行（再試行を含む。最終行で数えると 42） |
| E（60 試行） | 試行ごとにランダムな世界（v3.5） | **完了**。60/60、誤配達 0。ただし火は 12 件ともはっきり見える大きさ |
| T1（未使用画像 600 枚） | 画像レベル、v3.4 の誤許可 | **完了・主張は不成立**。誤許可 5/408（Wilson 上限 2.84% > 登録した 2%）。τ_h=0.05 では 3/408。物資の誤許可は 0/332 |
| T2（未使用画像 600 枚） | 画像レベル、v3.5 | **完了・天井で不成立**（改善が測れない）。誤許可 0/407、正しい許可 190/193 |
| F（24 世界×2、小さな火） | 閉ループの対比較、v3.5 対 B | **完了・不成立**。火が見える 13 世界で配達 12/13 → 7/13、p=0.0625。（B の見逃しのうち 1 件 W21 は 8,573 画素。訂正済み） |
| G（24 世界×2） | 横から見直す（I-14） | **完了・成立**。火が見えるのに配達 11/16 → 1/16（p=0.00195）、火の無い世界の誤停止 0/8 |
| H（16 系列、112 run） | 出動をまたぐ記憶（I-15） | **完了・成立**。危険な配達：素朴 20/32、検証つき 0/32（p=1.9e-6）、記憶なし 1/32。入れ替わりが続く出動の所要時間 114 → 79 s（8 組すべて短縮、p=0.0078） |
| J（24 世界×2、48 run） | Jev 役 Clef-Flash＋Qwen3.5-4B（I-16） | **完了**。V100 1 台で動く（ピーク 28,676 MiB、成立）が、危険な配達は J 1/24 対 v3.6 単独 0/24 で P2 は**不成立** → 不採用。論文に「実装し、検証し、採用しなかった」と書いた |
| K | 適合予測による閾値の較正 | **完了**。凍結した τ_h=0.05 は T2 で見逃し 0/76、誤許可 0/407（較正側の見逃しは 23/211） |
| L（24 世界） | 配置のランダム化（I-17） | **完了・成立**。24/24、危険な配達 0 |
| P / P2 | 実写（D-Fire）で危険の質問が通用するか | P：検出 298/300、誤警報 64/100（τ_h=0.05）。P2：h35・τ=0.30 で検出 282/300、誤警報 18/100（**成立**） |
| R（300 枚×12 劣化条件） | カメラ劣化 | **完了・成立**。誤許可 0/2304（Wilson 上限 0.17%）。もっとも厳しいのは強い露出オーバー |
| Z | ゼロショット SigLIP/CLIP との比較 | **完了**。SigLIP の誤許可は T1 で 44/408、T2 で 47/407（本方式は 3 と 0）。CLIP はほぼ全拒否（正しい許可 2/191） |
| V（10 系列×6 出動、160 run、失敗 0） | H のモデルの予測検証 | **完了**。モデルの予測は**成立**（時間差 14.9 s が予測区間 11.3〜20.1 s の内側、危険な配達 M0 0・M1 20・M2 1、速さ p=0.00586）。**記憶の安全 V4 は不成立**（余裕 M2−M0=1 ≤ 3 は成立、系列単位の McNemar 5 対 0 で p=0.0625）。原因は検出力不足と、M2 の 1 件（V156）の到着ぶれによる検査の誤り（右の視点 p_h=0.013。FINDINGS #29）。H＋V をまとめると危険な配達 M0 1/82、M2 1/82、M1 40/82 |
| W（小さく隠れた火 150＋双子 75、画像） | 見回しの取りこぼし上限と先行手法 | **完了**。見逃し 見回し 3/150（Wilson 上限 5.7% ≤ 15%、**成立**）、正面のみ 76/150（横からしか見えない火 23 件のうち 22 件）、双子の余計な停止 0/75（**成立**）。先行手法（同じ全体画像）：本方式 3/815、投票 9/815（Holm p=0.094）、KnowNo 風 α=0.05 は 1/815 で正しい許可が 303/384 に低下 → 判定規則そのものが優れる主張は**不成立（0/3）**。I-20（疑わしいとき視点を増やす）：見逃し 2/150、双子の損失 0/75 → 事前の規則を満たし v3.7 の既定にした |
| I-22 Gazebo 確認 | 配送インターロックの実機（シミュレーション）確認 | **合格**（4 ミッション。許可証は承認時のみ、隠れた火＋「確認不要」の助言は拒否・停止）。動画の素材にした |
| I-23 / I-24 | 命題 2 の z3 検証／助言の信用枠 | I-23：99 件が unsat、実関数との突き合わせ 9,000 件で不一致 0、変異 11/11 検出（F1〜F3 を修正）。I-24：命題 3、閉ループは B で測る |
| **A（226 run、予備走行 27 run）** | 助言は検査を緩められるか、攻撃者が買えるもの | **予備走行は失敗**（2026-10-18 09:14〜）。依頼文で助言する経路（operator）の run がすべて意図ゲートで拒否された（v3.6 の意図プロンプト i35 が、拠点を「避難所 B 以外の届け先」と読む）→ **FINDINGS #30**。i38 は事前に固定した規則（I-25）で採用済み（`experiments/results/intent_i38_check.json`：保留 55/60 で両方同じ・危険 0、dev の注入で正しい受理 86→92/94・取り違え 0）。**Amendment 1**（`experiments/PREREGISTRATION_A.md`、コミット 2a1bab0）で A の全試行を i38 にし、最初のパイロット台帳は `campaign_A_pilot1_ledger.jsonl` に残した（27 試行：依頼文チャネル 12 件中 0 件が意図どおり、うち 6 件は意図の段で拒否、残りは取れた項目が設計と違った）。**Amendment 2**（コミット 1163eee、10:38）で予備走行の合格条件を「依頼文チャネルの意図の受理 9/12 以上」に変え、正確な取り出し（FINDINGS #31：最初の予備走行で 0/6）は報告項目にした。新しい台帳でやり直した予備走行は合格した（`A_PILOT_OK` 10:56：意図の受理 12/12、ファイルチャネル 12/12、正確な取り出し 0/12）。**本走行（226 試行）は 11:11 に開始し、実行中**（結果はまだ無い）。論文・補遺・README・報告に反映済み（`tab_amend.tex`、マクロ `APilot*` `AInt*` `ARerun*`）。v3.6 の既定は i35 のまま、IF は i35 を測る |
| IF（72 文） | 依頼文で依頼物資を書き換えられるか | 登録済み・**未実行**（GPU 約 2 分） |
| S（64 世界、276 画像） | 場面内の文字（貼り紙・看板）による注入 | 登録済み・**未実行**（約 2.4 時間。看板の確認 `sign_check_ok` は済み） |
| B（48 run＋予備走行 6） | 信用枠（I-24）の閉ループ | 登録済み・**未実行**（約 1.5 時間。Amendment 2：両アームでインターロックを有効にする） |
| XD（画像、4 拠点の倉庫） | 倉庫で v3.6 の検査を再測定。I-20 を取り消す規則の判定を含む | 登録済み・**未実行**（スモーク確認 `xd_smoke_ok` は済み）。XD-R の実写の火のない倉庫写真は採点前に凍結済み（Commons の候補 394 枚から目視確認で 258 枚を採用、`experiments/xd_real_manifest.jsonl`・`xd_real_exclusions.json`。登録どおり先頭 200 枚を採点） |
| X（80 run＋予備走行 9） | 倉庫の閉ループ（M0 対 M2、k=4、助言の操縦） | 登録済み・**未実行** |
| Q（Wikimedia Commons 405 枚） | 実写の物資確認 | 登録済み・**未実行**（GPU 約 40 分。W の後の連鎖が .gitignore の衝突で止まり、一度も走っていない） |

* 登録済み 7 本（A・B・IF・Q・S・X・XD）は統合マージ 09:08 で main に載り、A の予備走行が 09:14 に始まった時点で、IF・S・B・XD・X・Q は試行も推論もしていない。これらの登録ファイルには「DRAFT」の行が残るが、拘束力のある版は `docs/REGISTRATIONS.md` の表の版（ファイルは変えない。変更は日付とコミットつきの Amendment で追記する）。
* テスト関数は 1289 件（`python3 scripts/count_tests.py` の静的な数え方）。FINDINGS は 31 件。

### D. GPU の順番と、その動かし方

**予定の順番**：i38 の確認 → **A（再実行）** → IF → S → B → XD → X → Q。GPU は同時に 1 本だけ（同じ ROS ドメイン／Gazebo パーティション／ポート 8765 を使うので並行しない）。

**今の状態（10:00 ごろ）**
* （解決済み）A の最初のパイロットは 09:14 に始まり、i35 では依頼文チャネルが意図の段で拒否されて不合格になった（FINDINGS #30・#31）。i38 の採用（Amendment 1）と合格条件の変更（Amendment 2）のあと、パイロットは合格し（10:56）、本走行が 11:11 に始まった。
* スクラッチパッドの連鎖 `i38_check_chain.sh`（実行中）が、`after_q.log` に `A_CHAIN_ABORT`（または `A_CHAIN_DONE`）が出るのを待つ → main に i21-depot をマージして push → サーバを i35 と i38 で順に起動し `scripts/intent_i38_check.py --tag i35|i38`（約 10 分）→ `--decide` → `I38_CHECK_DONE`。**採用規則は走らせる前に固定済み**（`scripts/intent_i38_check.py` の冒頭と FINDINGS #30。IMPROVEMENT_LOG にはまだ i38 の項が無い）：保留テスト集合（held_out_v34）で危険な誤りが増えず、正しい答えの減りが 1 件以内、かつ注入文の dev 半分で避難所の取り違えが 0 件のまま正しい受理が増えること。結果は `experiments/results/intent_i38_check.json`。
* **このチェーンは main に `experiments/results/i38_stop_server.sh`・`i38_server_*.log`・`intent_i38_check.json` を作る（untracked）。** i21 側で同名のファイルを追跡しないこと。

**連鎖スクリプトは再作成が要る。** `after_a_chain.sh`（A の後に IF と S）、`after_s_chain.sh`（B）、`after_b_chain.sh`（XD→X）、`after_x_chain.sh`（Q）は、スクラッチパッド（`<scratchpad>`）に置いたものだが、**今は動いていない**（待ち条件が `after_q.log` の `A_CHAIN_DONE` で、A の本番が走らない限り来ない）。**スクラッチパッドが無い、またはプロセスが無いときは作り直す。** 型は次のとおり（各段は前の段の完了行をログで待ち、`git pull -q --ff-only` してから次を呼び、完了行を出す）：

| 段 | 呼び出し | 完了の印 |
|---|---|---|
| i38 確認 | `i38_check_chain.sh`（上記） | `I38_CHECK_DONE` |
| A（再実行） | i38 を採用したときだけ：A の事前登録に **Amendment** を追記・コミット・main に載せ、古いパイロット台帳を別名（例 `campaign_A_pilot1_ledger.jsonl`）に退避して残してから `bash scripts/a_run.sh`（予備走行 27 → マスク → 登録の確認 → 226 run、約 11.5 時間 → `a_analysis.py`） | `A_DONE` / `A_ABORT` |
| IF | `bash scripts/if_run.sh`（約 2 分） | `IF_DONE` |
| S | `docker exec rm-next rescuemind-entrypoint bash -c "cd $PWD && bash scripts/s_render.sh"` → `bash scripts/s_eval.sh`（`experiments/vlm_testset_s/sign_check_ok` があること） | `S_DONE` |
| B | `bash scripts/b_run.sh`（予備走行 6 → 本番 48） | `B_CHAIN_DONE` |
| XD | `docker exec rm-next rescuemind-entrypoint bash -c "cd $PWD && bash scripts/xd_render.sh"` → `bash scripts/xd_eval.sh`（`xd_smoke_ok` があること） | `XD_DONE` |
| X | `bash scripts/x_run.sh`（予備走行 9 → 本番 80） | `X_DONE` |
| Q | `bash scripts/q_run.sh`（約 40 分） | `Q_DONE` |

* 各スクリプトは、登録（コミット済み・未変更）を確かめてから始める。`*_run.sh` が `ABORT` を出したら原因を直し、Amendment に記録してから再実行する（キャンペーンは再開できる。`--only` は台帳にある試行をやり直すので注意）。
* i38 を**採用しない**場合：A の依頼文チャネルは測れない。ファイルチャネルだけで走らせるか、不成立として報告するかを、Amendment に理由を書いて決める。IF は i35 を測るので、どちらでも変えない。
* 実行中はホストの負荷を見る（`awk '{print $1}' /proc/loadavg`、4 コアで 6 未満）。`docker ps` に `rm-next`（GPU）、`rm-dev`（図・PDF・テスト）、`rm-voicevox` がいること。
* 各段が終わったら `bash scripts/finalize_results.sh`（結果の解析 → 論文・説明資料・README・YouTube 文の再生成 → 整合性検査。`nice` つき、GPU を使わない）。コミットはしない処理なので、確認してから `docs:` か `study X results` でコミットする。

### E. 主要コマンド（詳しくは §3）

```bash
git pull --ff-only origin i21-depot                         # 再開の最初（worktree .claude/worktrees/i21 で）
nice -n 19 python3 scripts/check_consistency.py             # 文書と結果ファイルの突き合わせ（0 mismatch が正常）
python3 scripts/count_tests.py                              # テスト関数の数（静的）。実行は python3 -m unittest discover -s tests
bash scripts/finalize_results.sh                            # 結果が出たあとの再生成（GPU を使わない）
make help                                                   # make paper / report / readme / youtube / video / check / verify-quick
make paper FINAL=1                                          # 提出用ビルド（TBD と (pending) が残っていれば失敗する）
python3 scripts/intent_i38_check.py --decide                # i38 の採否（規則は固定済み）
docker exec rm-dev rescuemind-entrypoint python3 scripts/make_video_plan.py ... --advice <run_id>   # 動画 v5 の助言の場面
```

* 動画 v5 の撮影済みの run（I-22 の確認で撮影）：`076f3cb047064fae`（隠れた火＋「確認不要」を却下し、左の視点で停止）。記憶の run は `b93040decbf04ca4`、デモの run は `dbed92419f88479e`（配達）・`b4fcd9d164444db7`（取り違え）・`9d73663832c94f16`（隠れた火）。`outputs/` は Git 管理外。
* 論文の `docs/paper/numbers.tex` と各 `tab_*.tex` は `scripts/paper_numbers.py` が生成する（手で直さない）。助言まわりの数値は `scripts/advice_numbers.py`。

### F. 判断待ち・未決

* **OpenTimestamps（事前登録のハッシュの外部タイムスタンプ。送るのはハッシュのみ）を実施してよいか、ユーザーの回答待ち。** 回答が来るまで実施しない（`docs/REGISTRATIONS.md` に未実施と明記済み）。
* **I-20 は v3.7 の既定にした（W で事前の規則を満たした）が、証拠は 1 世界だけ**（見逃し 3/150 → 2/150）。閉ループでは一度も測っていない。**元に戻す規則を XD で判定する**（XD の O3：双子での追加視点の起動が 15% 超、正しい許可が 5 ポイント以上低下、知覚できる危険で見逃しが 1 件も減らない、のどれか 1 つで取り消し）。登録済みの A・S・X・XD・B・IF は凍結した v3.6 で走る。
* **i38 の採否は決着**（採用、Amendment 1）。i35 を既定とする IF の登録は変えない。
* **動画 v5 は暫定**：`outputs/video/PAI最終課題_tetsutetsu_v5.mp4`（2:53＝172.5 秒、`docs/video_chapters.json` が章立て）。助言注入のデモ（I-22 の撮影）、評価 V（予測は成立、記憶の安全は不成立）、z3 を入れた証拠カードがある。P/P2 の行は 64/100 のみ。**倉庫（デポ）の場面は X の後**（`docs/design/video_v5_plan.md`）。概要欄は章立てから再生成する（`make_youtube_description.py`）。
* X の後に決めること：A・X でインターロック（I-22）を有効にするか（B は有効、A は無効のまま登録）。信用枠（I-24）の閉ループ確認は B で測る。
* ユーザーがすること：リポジトリの公開、YouTube への投稿、README とフォームへの URL 記入、提出。

### G. 成果物の状態と整合性

* 論文：`docs/paper/main.pdf` 10 頁（本文は 8 頁以内、参考文献は 8 頁目から）、補足 `supplement.pdf` 22 頁。未実行の研究の結果欄は灰色の「(pending)」（`make paper FINAL=1` は pending が残ると失敗する）。説明資料 `docs/report/説明資料_PAI最終課題_tetsutetsu.pdf` は **20 頁**（旧版の HANDOFF は 18 頁と書いていた）。
* `python3 scripts/check_consistency.py`：**0 mismatch**（2026-10-18 09:43 に確認）。A・S・X の README の行は「実行中」、V・W は結果ありで検査する。結果が出るたびに、検査の「結果待ち」の期待も更新する。
* 整合性検査を通し、`make paper FINAL=1` が通る状態を締切（11/02 10:00）の数日前までに作る。結果が出ない研究があっても、登録どおり「未実行」と書いた版で確定できるようにしておく。

---

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
docker exec rm-dev rescuemind-entrypoint python3 scripts/make_demo_video.py --plan docs/video_plan.json --out outputs/video/PAI最終課題_tetsutetsu.mp4 --narrate 2
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
* `docs/ARCHITECTURE.md`（全体フロー図）、`docs/DESIGN_DECISIONS.md`（D1–D15）、`docs/IMPROVEMENT_LOG.md`（I-01–I-24）、`docs/FINDINGS.md`（実行で見つけた31件）、`docs/REVIEW_AND_PLAN.md`（審査基準別レビュー）。
* `docs/REGISTRATIONS.md`（事前登録の台帳：main に載った最初のコミットと sha256）、`docs/REPRODUCE.md`（クリーンな Ubuntu＋NVIDIA 環境での 3 段階の再現手順）、`docs/REPRODUCIBILITY.md`。
* `docs/evaluations/`（第三者採点、第1〜8回と固定の指示文）、`docs/paper/`（論文・補足・`REVIEW_NOTES*.md`・`LITERATURE_*.md`・`PROOF_REVIEW.md`）、`docs/report/`（説明資料）、`docs/design/`（I-19〜I-24 の設計、動画 v5 の計画）。
* `experiments/`（事前登録 `PREREGISTRATION_*.md`・プロトコル・開発セット・台帳 `results/campaign_*_ledger.jsonl`・要約 `results/*_summary.json`）。
