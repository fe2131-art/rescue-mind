# HANDOFF — RescueMind（最終更新 2026-10-17 午後）

作業を中断・文脈圧縮した後でも、このファイルだけで正確に再開できるようにまとめたもの。
**最優先ルール**（ユーザー指示）：
* リポジトリの公開設定（private→public）は**絶対に変更しない**（ユーザー本人が行う）。push は可。
* ユーザーへの質問・説明は**日本語・簡潔**に。omnicampus アカウント名は `tetsutetsu`。YouTube 投稿はユーザーが行う。
* sudo は使わない（docker グループ権限のみで全て動く）。必要になったらユーザーに依頼。
* 改善は必ずトレース可能に：`docs/IMPROVEMENT_LOG.md` に「動機→仮説→変更→計測(Before/After)→判断」、コミット先頭に `I-xx`。
* 現在の目標：**研究論文として発表できる完成度**に仕上げる（課題の枠を前面に出さない）。

---

## 1. 現在の到達点（v3.6、2026-10-17。詳細は §5 と「★ 圧縮後はここから再開」）

| 項目 | 状態・数値 | 証拠 |
|---|---|---|
| 閉ループ D / E | 42/42、60/60（誤配達 0） | `campaign_D/E_ledger.jsonl` |
| 横から見直す（G、I-14） | 火が見えるのに配達 11/16 → 1/16（p=0.002）、誤停止 0/8 | `g_summary.json` |
| 出動をまたぐ記憶（H、I-15） | 危険な配達 素朴 20/32・検証つき 0/32・記憶なし 1/32、入れ替わり継続 114→79 s | `h_summary.json` |
| 未使用画像 T1 / T2 | v3.4 誤許可 5/408、v3.5 3/408、T2 0/407 | `t1_*.json`, `t2_*.json` |
| R / Z / P / K | 劣化12条件 0/2304、SigLIP 44/408、実写 298/300・誤警報 64/100（AUROC 0.96）、適合閾値 | `*_summary.json` |
| J / P2 / L | 実行中・待機中（§「★」参照） | — |
| 動画 | 2:46（v3.6）。記憶デモ入りの再描画は撮影後に自動 | `outputs/video/`（Git管理外） |
| 論文・説明資料 | 本文8頁＋補足、説明資料12頁、第三者採点 32.0/40（第6回） | `docs/paper/`, `docs/report/` |
| テスト | 620件（main。i19 ブランチは約750件） | `python3 -m unittest discover -s tests` |

**v3.6 = オーケストレータの既定構成**（`--model Qwen/Qwen3.5-9B --prompt-set v35 --intent-backend llm --intent-prompt i35`、τ_s=0.5、τ_h=0.05、h36＋tiles、横から見直す ±0.4 m、回復探索）。過去の評価の再現は各台帳の `stack_args` を使う。

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
デモ収録 run（`--film` 付き。**旧版の動画の run。現行の動画の run は §5 を参照**）：deliver `a93d6a9cc8704e6c`、recover `8b54abfb36454b27`、fire `a213a61bc53e4787`（`outputs/runs/` 内、Git管理外）。

## 4. 落とし穴（実際に踏んだもの）

* `pkill -f <pattern>` を `bash -c '...pattern...'` の中で使うと**自分自身のシェルも殺す**（exit 143）。スクリプトファイルから実行する。
* サーバ再起動直後は**古いサーバがまだ応答**することがある → `while curl -s -m 2 http://127.0.0.1:8765/health; do sleep 1; done` で消えるのを待つ。
* `nice` はファイルケーパビリティ付き → その exec は glibc セキュアモードで **LD_LIBRARY_PATH が消える**。`nice` は必ず「ROS を source するシェル」の外側に置く（`prioritised(shell_exec(...), n)`）。シェルスクリプト内は `renice -n N -p $$`。テスト `tests/test_v34_priority_wrapping.py`。
* ROS の `setup.bash` は `set -u` と相性が悪い → `set +u; source ...; set -u`。
* 画像トピックは Reliable QoS（`rescuemind/ros_qos.py`）。Best Effort だと 0.9 MB 画像が大量に欠落。
* 4コアのホストは CPU が飽和気味（ロードアベレージ約3.9）。**キャンペーン中に重い処理（動画合成・音声合成・ビルド）をしない**。キャンペーン中に実行時コードを編集しない（各試行がファイルを読み直す）。
* 非rootユーザーには `--cap-add` だけでは権限が渡らない（ファイルケーパビリティが必要）。
* Qwen3.5 は思考モードが既定 → `enable_thinking=False`（サーバで対応済み）。FP16 で非有限 logits なら判断拒否。
* 動画は **3分以内**（現在 2:46）。倍速は区間ごとに画面表示（走行8倍、確認3倍、判断の瞬間は等速）。

## 5. 現状（2026-10-18 10時ごろ）— 圧縮後はここから再開する

**ユーザーの方針（必ず守る）**
* 当初計画（Jev＋Qwen の2つのAIによる確認）から勝手に外れない。Jev の役割はローカルの **Cloudflare Clef-Flash** で担う。
* 改善をだらだら続けない。**結果を分析し、最大の弱点に絞って、事前登録した評価で確かめる。**
* 評価基準（創造性・技術力・実用性・表現力）と、論文として通用する水準を常に意識する。課題をこなすためだけの作業にしない。
* **実機は用意できない → シミュレーションでできることはすべてやる。**
* サブエージェントは同時に1つまで（Sonnet 5.5）。説明は日本語で簡潔に。公開設定は絶対に変えない。

**v3.6 = オーケストレータの既定構成**
* Qwen3.5-9B、v35、指示理解 i35、τ_h=0.05、危険の問い方 h36＋拡大切り出し（tiles）、横から見直す 0.4 m、回復探索・状況報告あり、DDS 非同期。
* 過去の評価を再現するときは、各台帳の `stack_args` に記録されたフラグを明示する。

**主な結果**（すべて事前登録。数値は `scripts/paper_numbers.py` が結果ファイルから生成する）

| 評価 | 結果 |
|---|---|
| D（42試行） | 42/42 |
| E（60試行、試行ごとにランダムな世界） | 60/60、誤った配達 0 |
| T1（未使用の画像600枚） | v3.4 の誤許可 5/408（「2%未満」の主張は不成立）。物資の誤許可は 0/332。弱点は物資の陰の小さな火 |
| T2（未使用の画像600枚） | v3.5 でも 0/407 と天井で、改善は測れない。Clef（課題向けの質問）単独でも 0/407・正しい許可 187/193、1画像あたりの推論は中央値0.6秒 |
| 開発データ（I-11/I-13） | 見逃した火：v3.5 46 → h36＋tiles 17 → Clef＋Qwen 15（ただし 37 GB で V100 1台に載らない） |
| F（閉ループ、対比較） | 小さな火で配達してしまった回数：v3.5 12/13 → B 7/13（p=0.0625、有意でない） |
| G（閉ループ、対比較、新しい世界） | **横から見直す（I-14）で 11/16 → 1/16、p=0.002、誤った停止 0/8**。唯一の見逃し W19 は正面から0画素、横からも最小の2,308画素 |

**2026-10-17 の進捗**
* 動画（v3.6）は完成：2:46・ナレーションあり、走行8倍速・確認3倍速・判断は等速で、横から見直す場面を含む。
  * 使った run：deliver dbed92419f88479e、recover b4fcd9d164444db7、empty 367928c988f34e34、hidden_fire 9d73663832c94f16。
  * 再生成：`make_video_plan.py --deliver .. --recover .. --empty .. --hidden-fire ..` → `make_demo_video.py --narrate 2`。
* 説明資料PDF（当時9ページ、現在11ページ）・README・YouTube説明文・SUBMISSION を v3.6（F・G・T2・I-14）に更新した。論文の Abstract と貢献に G を追加した。
* 訂正：F で B が見逃した7件のうち1件（W21）は 8,573画素・p=0.019 だった（G の事前登録に Erratum を追記）。
* **R（カメラ劣化12条件、事前登録 `PREREGISTRATION_R.md`）**：
  * 実行：`scripts/r_eval.sh`（再開可能。停止は `scripts/stop_r.sh`）。結果は `devset_r_<条件>.json`。
  * 解析スクリプト `r_analysis.py` は未作成。主評価は P1：12条件をまとめた誤許可の、world 単位クラスタ CI の上限が 2% 未満かどうか。
* **新規性 I-15：出動をまたぐ記憶**（`rescuemind/mission_memory.py`、D13、IMPROVEMENT_LOG I-15）。
  * 記憶にできるのは順序の提案と慎重さの追加だけ。確認は減らさない（安全側への単調性。監査が再計算する）。
  * 文献調査の結果、この「記憶で確認の場所と量を決め、確認は減らさない」型の先行研究は見当たらなかった（ReMEmbR、Embodied-RAG、When Memory Lies など）。
  * 評価H は事前登録済み：`PREREGISTRATION_H.md`、16系列（1回目の出動は3方式で共通の16 run、2・3回目を M0・M1・M2 の3方式で 16×2×3=96 run）、計112 run。
    * 実行：`run_campaign.py --protocol experiments/campaign_h_protocol.json --ledger experiments/results/campaign_H_ledger.jsonl`
    * 解析：`scripts/h_analysis.py`、`scripts/h_change_rate_model.py`（変化率スイープ、図 `fig_h_change_rate.pdf`）。
  * 予備走行（`campaign_H_pilot*_ledger.jsonl`）で、見た物資の判定に誤りを発見して修正した（判断の確信度は依頼物資のものだった）。H の Amendment 1 に記録すること。

* **I-16：当初計画の Jev＋Qwen を実機（閉ループ）で動かす**。ユーザーの指示（2026-10-17）。
  * 構成：Clef-Flash（課題向けの質問、τ 0.05）＋Qwen3.5-4B。V100 1台に載る（約28GB）。
  * 評価J を事前登録済み：`PREREGISTRATION_J.md`、24世界の対比較（A：v3.6、J：2モデル）、48 run。解析は `scripts/j_analysis.py`。
  * フラグ：`--jev-local clef --jev-schema task --jev-hazard-threshold 0.05 --model Qwen/Qwen3.5-4B --hazard-prompt h35 --hazard-views full`。
* H の予備走行2回目に合格し、Amendment 1 として記録済み。
* **実行中の連鎖**：`scripts/final_chain.sh`。R の終了 → `r_analysis.py` → J の試運転（GPUメモリの確認）→ H 本番 → J 本番（試運転が成功した場合のみ）。
  * 出力：`r_analysis_stdout.log`、`j_smoke_stdout.log`、`campaign_H_ledger.jsonl`、`campaign_J_ledger.jsonl`、`campaign_J_vram.csv`。

* **Z（事前登録、完了）**：比較対象として、画像と言葉の対応だけで判定するゼロショットの SigLIP と CLIP を、未使用データ T1/T2 で評価した。
  * SigLIP は誤許可 44/408（T1）、47/407（T2）。こちらは 3 と 0 で、p<1e-6。
  * CLIP はほぼすべて拒否した（正しい許可 2/191、0/193）。
  * 論文の表は `tab_z.tex`。
* **P（事前登録、実行中）**：実写画像で危険の質問が通用するか。D-Fire（CC0）のテスト用400枚を使う。画像はリポジトリの外の `~/.cache/rescuemind/dfire` に置く。
  * 実行：`scripts/p_realphoto_eval.py --run`（pyarrow が必要。スクラッチパッドの venv を使う）。解析は `--analyse`。
* **第三者評価（ユーザー指示）**：Sonnet 5.5 に、評価基準に基づいて定期的に採点させる。
  * 指示文は固定：`docs/evaluations/EVALUATOR_PROMPT.md`。課題文の場所は起動時に渡す。
  * 結果は `docs/evaluations/EVAL_<日付>_<連番>.md`。点数を上げる改善点トップ5に沿って改善する。
* **論文**：
  * 新しい章：横から見直す・Jev役・記憶（命題1と Algorithm 1）、全11研究の一覧表、R・H・J・Z の結果、Discussion、事前登録の時系列監査（付録）。
  * 図：横から見直す例、火の大きさと検出、R の例、系統図。
  * 参考文献は 77件以上（検証メモは `docs/paper/REFERENCES_NOTES.md`）。
  * 注意：Clef-Flash は Qwen3.5-9B からの追加学習なので、Qwen とは系統が同じ。論文と D11 に明記済み。
  * 論文中の `% CHECK-AFTER-H` の文は、H の結果で必ず確認する。
* サブエージェントは必ず Sonnet 5.5（`model: sonnet`）。同時に1つまで（ユーザー指示 2026-10-17、2→1に変更）。常に1つ稼働させる。

**2026-10-17 13:10 時点**
* 完了：
  * R：12条件の誤許可は合計 0/2304 で、主張は成立。もっとも厳しいのは強い露出オーバーで、正しい許可 59/108。
  * J の試運転：完了、GPU メモリのピークは 28.7 GB。
  * Z、P（実写）。
  * 論文：命題を「観察」と「1出動あたりの系」に変更、要旨を中立的に書き直し、用語を定義。
  * 第三者採点：1回目 28.0、2回目 29.5/40。
* 実行中：H 本番（13:03 開始、1 run 約3分、19時ごろ終了予定）→ J 本番 → `post_j_chain.sh`（記憶デモの撮影 → P2）。
* 配置のランダム化（study L）：worktree のブランチ `worktree-agent-ac85b5ba081cc1f61` に実装済み。中身は確認済みで未マージ。
  * 次：J の後でマージ → Gazebo で試運転 → 事前登録 → 実行。
* 結果が出たら：
  * `h_analysis.py` → `h_change_rate_model.py` → `paper_numbers.py` → `build_paper.sh`。
  * `% CHECK-AFTER-H` を確認する。
  * 動画を作り直す：`make_video_plan.py --memory <id>` に要約カード。
  * README・説明資料・YouTube 説明文を更新し、第三者採点の3回目を行う。

**2026-10-17 夕方の状態（利用上限で中断）**
* 自動で動き続けているもの：H 本番（53/112、失敗 0。結果は仮説どおり）→ J 本番 → `post_j_chain.sh`（記憶デモの撮影 → P2）。
* 再開したら：
  1. `bash scripts/finalize_results.sh` で全解析 → 論文・説明資料・README・YouTube説明文を再生成する。TBD が残っていないことを確認する。
  2. 論文の `% CHECK-AFTER-H` を確認する。H の変化率の図を本文に戻すか検討する。
  3. 動画を作り直す。`film_memory_runs.txt` の mem_verified の run_id を使い、`make_video_plan.py ... --memory <id>` → `make_demo_video.py --narrate 2`（3分以内）。
  4. study L：ブランチ `worktree-agent-ac85b5ba081cc1f61` をマージ → `scripts/l_smoke.sh` → 事前登録をコミット → 実行。
  5. 第三者採点の3回目（Sonnet、`docs/evaluations/EVALUATOR_PROMPT.md`）。
  6. ユーザーへの質問：事前登録の外部タイムスタンプ（OpenTimestamps。送るのはハッシュのみ）を実施してよいか。回答待ち。
* サブエージェントは Sonnet 5.5 で、同時に1つまで。

**2026-10-17 16:20 追記**
* 追加で完了：
  * K：適合予測（conformal）による閾値の較正。事前登録済みで、T2 では既定の τ_h=0.05 が保証の範囲内だった。
  * I-18：現場への1枚報告（`scripts/make_operator_report.py`。例は `docs/figures/operator_report_*.png`）。
  * グラフィカルアブストラクト（`docs/figures/graphical_abstract_*.png`）、記憶の原理図。
  * 動画：ナレーションを推敲し、記憶カード・変化の報告・最後のカードに現場報告を加えた。
  * 論文：本文8ページ＋補足、英文校正済み。
* 自動の連鎖：
  * `final_chain.sh`：H → J。
  * `post_j_chain.sh`：記憶デモの撮影 → P2。
  * `after_p2_chain.sh`：L のブランチをマージ（I-17）→ テスト → `l_run.sh`（マスク → 試運転 → 本番 → 解析）。
* 評価中は実行時コードを変更しない規則がある。そのため評価が終わってから、オーケストレータが毎回 I-18 の報告を自動生成するよう組み込む。

**2026-10-17 16:50：H 完了（主張はすべて成立）**
* 危険な配達：素朴な記憶 20/32、検証つき記憶 0/32（p=1.9e-6）、記憶なし 1/32。
* 入れ替わりが続く出動の所要時間：114 → 79秒（8組すべてで短縮、p=0.0078。中央値の計算誤りを訂正済み）。元に戻った場合は 97 → 113秒（遠回りの代償）。
* 事例：記憶による慎重さ（τ_h=0.01）が、記憶なしで見逃した火を止めた（Q09 の3回目）。
* 論文・説明資料・README・グラフィカルアブストラクトに反映済み（`finalize_results.sh`）。
* 実行中：J（48 run、19:30ごろ終了予定）→ 記憶デモの撮影 → 動画の再描画（`render_after_film.sh`）と P2 → L（I-17 をマージしてから）。
* 未マージのブランチ：
  * I-18 のオーケストレータ組み込み：`worktree-agent-a94afbeadff714e1e`。P2 の間に手動でマージする。
  * L：`worktree-agent-ac85b5ba081cc1f61`。`after_p2_chain` が自動でマージする。
* サブエージェントは Sonnet 5.5 で同時に2つまで（再び許可された）。

**2026-10-17 17:15 追記（重要）**
* **評価中は重い処理（ビルド・テスト・図の生成・動画の描画）をしない**。J の途中でこれを破り、負荷平均が8〜10になった。
  * その影響で、判断時間が両方の構成で 3〜7秒から 25〜33秒に延びた（J007 以降）。
  * J の事前登録に逸脱の注記を追記済み。結果の判断時間は J001〜006 と J007 以降に分けて報告する。
* 中央値の計算誤りを修正した（偶数個のときに上側の値を取っていた）。H は 114 → 79秒。元に戻った場合は 97 → 113秒（遠回りの代償）。H・G・F の事前登録に Erratum を追記済み。
* 論文：
  * 系1を「確認する拠点の数 k × ε」に修正した。
  * 系列単位の検定（p=0.0005）、Jev の誤りの重なり（Qwen が見逃した17件のうち15件を Clef も見逃した）、R の条件ごとの上限（1.96%）を追記した。
  * 本文は8ページに収めた。
* 説明資料は11ページ。README は先頭を整え、記憶の事例図を入れた。
* L と I-18 のブランチは main に追従させ、同時にマージしても衝突しないことを確認済み（main を変更したら再度の追従が必要）。
* 第三者採点の4回目は 31.5/40、模擬査読の3回目は borderline。

## ★ 圧縮後はここから再開（2026-10-17 17:25）

**自動で動いているもの（止めない・触らない）**
1. `final_chain.sh`：J 本番（48 run。17:25 時点で約17。20時ごろ終了）→ `J_DONE`。出力は `.../tasks/brbkqd8zb.output`。
2. `post_j_chain.sh`：J の後に記憶デモの撮影（`film_memory.sh` → `experiments/results/film_memory_runs.txt`）→ `FILM_MEMORY_DONE` → P2（`p2_eval.sh`）→ `P2_DONE`。
3. `render_after_film.sh`：撮影の後に動画を作り直す（`--memory <mem_verified id>`、記憶カード・事例カード、空の拠点のデモを外して約163秒）→ `make_youtube_description.py` → `RENDER_DONE`。
4. `after_p2_chain.sh`：P2 の後に L のブランチ（`worktree-agent-ac85b5ba081cc1f61`）を main へマージ → テスト → push → `l_run.sh`（マスク → 試運転 → 本番 → 解析）。
   * マージで衝突したら `MERGE_CONFLICT` で止まる。その場合はブランチを main に追従させてから、手動でマージして `l_run.sh` を実行する。
5. 待機中：`broolkxvo`（J 終了後に `j_analysis.py` を実行）。
6. **（17:50 追加）`after_l_chain.sh`**（タスク `byvmbjuo9`）：L の終了（`L_DONE`/`L_ABORT`/`MERGE_CONFLICT`）を待つ → I-18 ブランチをマージ（テストが通らなければ revert）→ **study V**（`v_run.sh`：予備走行 → マスク → 予測を自動コミット → 160 run → `v_analysis.py`）→ `V_DONE`。
   * study V（`PREREGISTRATION_V.md`）：H のモデルの予測（M0−M2 の時間差、各群の危険な配達の 95% 予測区間）を、ランダムな変化（q=0.2、10系列×6出動）の閉ループで検証する。「台本が結果を決めている」という指摘への回答。
   * 予備走行が失敗したら `V_ABORT` で止まる → 原因を直し、Amendment に記録してから `bash scripts/v_run.sh` を再実行する。
7. **（18:35 追加）`after_v_chain.sh`**（タスク `bn71t32h1`）：`V_DONE` を待つ → study W のブランチ `worktree-agent-a065158341fac6202` をマージ（これが事前登録。テストが通らなければ revert）→ `w_render.sh`（約2時間）→ `w_eval.sh`（約3時間）→ `W_DONE`。
   * study W（`PREREGISTRATION_W.md`）：W-a は小さく隠れた火の新しい世界150と、火のない双子75。正面だけと横から見直す場合を画像単位で比べ、見逃し率の上限を絞る。W-b は先行手法との比較（VAP-TAMP風の言い換え5問の多数決、KnowNo風の適合予測集合）。主比較は同じ入力（全体画像のみ）の本方式。
   * 模擬査読4回目（`REVIEW_NOTES_R4.md`）：borderline の上側。V の緊急指摘は Amendment 1 で対応済み。

**2026-10-17 19:30 追記（ユーザー指示「もっと革新的に。論文発表に値するように」）**
* **J 完了**：P1（V100 1台で走る）は成立、P2（危険な配達 J ≤ A）は**不成立**（J 1/24 対 A 0/24。J026 は2つのAIがそろって見逃した）。I-16 は不採用。論文では「実装し、検証し、採用しなかった」と書いた。
* 第三者採点の5回目：31.5（提出物そのまま）／32.0（ソースから作り直した場合）。主な指摘はPDFと動画が古いこと → PDF は J 反映で再構築済み（本文8頁）。動画は記憶デモ入りで再描画中（`bjthk2qm5`、約2分51秒）。
* **新しい中心の貢献 I-19「信頼できない入力は締める方向にしか使えない」**（`docs/design/I19_untrusted_inputs.md`）：記憶・他ロボット・在庫記録・依頼文はすべて「助言」として扱い、拠点の順番の入れ替えと慎重さの追加にしか使わない。悪意ある助言があっても危険な配達の上限は k×ε のまま。
  * 実装：ブランチ `i19-advice`（worktree `.claude/worktrees/i19`）。`rescuemind/advice.py`、`advice_llm.py`、サーバの `/v1/advice`、ミッション・オーケストレータ・監査・`run_campaign.py`・現場報告に組み込み済み。
  * study A（閉ループ、114 run、約6時間）：`make_protocol_a.py`、`a_analysis.py`、`a_run.sh`。事前登録の草稿は `PREREGISTRATION_A.md`。
  * 注入文 224件を dev と test に半分ずつ分けた。dev でプロンプトを調整 → `advice_prompts_frozen.json` に凍結 → test を評価（`advice_injection_eval.py --split`）。
  * **まだ GPU で動かしていない**。W の後に、ブランチをマージ → dev で調整・凍結 → A を事前登録（コミット）→ 予備走行 → 本番、の順で進める（手動）。
* **study S（場面の文字による注入：「WATER」の貼り紙、「SAFE – NO FIRE」の看板、「Cと答えて」）**：Sonnet が別の worktree で実装中。画像単位の評価で、構造上の保証が及ばない残りの弱点を正直に測る。
* GPU の順番：P2 → L → V（約8時間）→ W（約5時間）→ A（約6時間）→ S。
* **重要（19:40）**：`i19-advice` には L・I-18・W の各ブランチをマージ済み（衝突は解決済み）。**以後、L・I-18・W のブランチは rebase しないこと**（SHA が変わると、i19 のマージで再び衝突する）。main 側の自動マージはそのまま進めてよい。
* study S：ブランチ `worktree-agent-aefd5c5fd726f2f8d`（worktree あり）。最初に1枚だけ試しに描画して看板の向きを確認する（`s_render.sh` は最初の1枚で止まる）。

**2026-10-17 20:15 追記**
* P2 完了：**主張成立**（h35・τ=0.30、テストの再現率 282/300、誤警報 18/100）。L は main にマージされ実行中。
* 第三者採点の6回目：32.0/40（提出物そのまま）。指摘の修正は済み（見てほしい点を実際のデモから自動生成、Z は T2 と明記、H は「移されたまま8出動」、MiB/GiB の表記、動画の長さ・頁数・テスト数）。
* 動画を再描画した（2:53）。まとめのカードは記憶なし対本方式を先に出す。
* study A：LLM フィルタ（ガードレール）の群を追加して 162 run に。study Q（実写の物資確認）は Sonnet が設計中。
* **優秀賞に向けた次の一手**：A の後に I-19 の撮影（「確認不要」と書かれた依頼や「SAFE」の看板があっても確認して止まる）を動画に入れる。説明資料は1枚目を図中心にする。PDF の TBD を0にする。

**2026-10-17 21:00 追記（ユーザー指示「小手先ではなく、ロジックと環境の根本的な改良を」）**
* **I-20：疑わしいときだけ視点を増やす**。開発データでは、0.05 で見逃した火 23 件のうち 17 件が 0.005 以上で、火の無い画像は 40/380。
  * W の Amendment 1 に登録済み（main とブランチ）：±0.8 m と 0.3 m 近い正面の3視点を追加で描画し、副次解析 `summarise_adaptive` で評価する。F/L/R の世界は変えていない。
* **I-21：現実的な救援物資の倉庫**（`docs/design/I21_realistic_depot.md`、ブランチ `i21-depot`、worktree `.claude/worktrees/i21`）。
  * AWS small warehouse（MIT-0）を `worlds/assets/aws-wh` に置く（git 管理外。`scripts/fetch_depot_assets.sh` で取得）。
  * 壁・床・棚・散乱物（世界ごとのランダム配置）・パレットジャッキの障害物・粒子の煙を、操作領域の外に配置した。
  * `build_variant(depot={...})` で使う。テスト合格。
  * `v_run.sh` が V の前にプレビュー画像を描画する（`docs/figures/depot_preview_*.jpg`、ログは `experiments/results/depot_preview.log`）。
  * 次の段階：拠点を4か所にして研究X。
* **文献調査（全文）**：`docs/paper/LITERATURE_REVIEW.md` に、新規性への脅威トップ5と、論文に貼れる位置づけ文がある。
  * I-19 版の論文の関連研究を書き直した（「完全性の非干渉を一方向に緩めたもの」「予測つきアルゴリズム」と位置づけ、新規なのは知覚の門への適用・上界・監査つきの閉ループ評価）。
* **一貫性と頑健性の曲線**（`scripts/advice_curve.py`、`fig_advice_curve.pdf`）：本方式は助言の正答率によらず危険が助言なしと同じで、正しい助言では 118→74 秒（k=4）。素朴な追従は 10〜51/100、LLM フィルタは 3〜11/100 の危険が残る。
* **研究Q（実写の物資確認）**：ブランチ `worktree-agent-ac893207bdda069d9`。Wikimedia Commons の 405 枚で、ラベルは目視確認済み。GPU で 30〜40 分。`q_run.sh` は作成中。
* **研究S**：OCR マスクと「文字を無視せよ」の防御群を追加中（Sonnet）。
* GPU の順番（予定）：L → V → W → Q → A → S → X。

**2026-10-17 21:45 追記**
* **L 完了：主張成立**（未知の配置 24/24、危険な配達 0）。
* I-18 は main にマージ済み。チェーンの「I18_TESTS_FAILED」はホスト環境だけの問題（sklearn なし・Python 3.10 に enterContext なし）だった。コンテナでは 657/657 合格。ホストにも sklearn を入れ、テストにシムを足して 657 OK。revert は実行されていない（`-q` が使えないため）。
* V：予備走行は合格。マスクを描画したあと予測を自動でコミットし、本番 160 run に進む（一晩）。**V の実行中は重い処理をしない**。
* I-21：倉庫の世界が Gazebo で読み込めるようになった（AWS モデルの不正な慣性値を除去）。プレビュー画像は `docs/figures/depot_preview_sheet.jpg`（ブランチ i21）。粒子の煙の写り方と、台をパレットらしい見た目にすることが残っている。
  * Gazebo の試験は、別の区画（`GZ_PARTITION=depottest ROS_DOMAIN_ID=99`）なら V と並行して走らせられる。ただし `nice` は付けない（環境変数が消える）。
* 4拠点化は完了（ブランチ i21-depot、818 テスト）。
* 査読5回目（`REVIEW_NOTES_R5.md`）への対応：
  * 済み：保証の書き直し（命題2は相対保証）。
  * Sonnet が進行中：軟拒否・scrutiny・A-steer、信頼基盤テスト。

**評価中の厳守事項**：重い処理（ビルド・テスト・図の生成・動画）をしない。J では CPU 負荷とページキャッシュの取り合いで判断時間が延びた。逸脱は J の事前登録に記録済み。

**各段が終わったらすること**
* J の後：
  * `bash scripts/finalize_results.sh`。J の結果を論文・説明資料・README・グラフィカルアブストラクトに反映する。
  * J の論文の文面（中立的な書き方）を確認する。判断時間は「負荷あり」の注記つきで報告する。
  * IMPROVEMENT_LOG の I-16 の判断を書く。
* 撮影の後：
  * `outputs/video/render_v4.log` と動画の長さ（3分以内）を確認する。数フレームを切り出して目で確認する。
  * `docs/video_chapters.json` と YouTube 説明文が更新されているか確認する。
* P2 の後：`finalize_results.sh` を実行し、P2 の主張（再現率0.90以上かつ誤警報0.20以下）を確認する。
* L の後：
  * `finalize_results.sh` を実行し、L の結果を I-17 に記入する。
  * I-18 のブランチ（`worktree-agent-a94afbeadff714e1e`、オーケストレータで報告を自動生成）を main に追従させてマージし、テストする。
  * README と説明資料にある「自動生成は評価後」の表現を直す。
* 最後に：第三者採点の5回目（Sonnet、`EVALUATOR_PROMPT.md`）と模擬査読の4回目を行い、指摘を直す。HANDOFF を更新する。

**ここまでの到達点**
* H：
  * 主張はすべて成立した。危険な配達は素朴な記憶 20/32、検証つき記憶 0/32、記憶なし 1/32。
  * 物資の入れ替わりが続く出動は 114 → 79秒（p=0.0078）。系列単位の検定は p=0.0005。
  * 記憶の慎重さが見逃しを止めた事例がある（Q09 の3回目）。
* その他：R は 0/2304、Z・P・K は完了。
* 論文：本文8ページ（系1は k×ε）＋補足。説明資料は11ページ。
* 第三者採点：31.5/40（4回目）。模擬査読は borderline。
* 未完了：J、P2、L、動画の作り直し、I-18 の自動生成の組み込み。
* ユーザーがすること：リポジトリの公開、YouTube への投稿、README とフォームへの URL 記入、提出。
* 未回答：OpenTimestamps（ハッシュのみ送る）を実施してよいか。

**次の手順**
1. （済）予備走行2回目（HP02・HP03：記憶による経路と、素朴な記憶の確認省略の監査）を確認する → H の Amendment 1 → H を本実行（約7時間。R の終了後に）。
2. R の解析（`r_analysis.py`。事前登録どおり）→ 論文に「センサー劣化」節、図。
3. H の解析 → 論文の主貢献に I-15 を入れる。題名・Abstract・Method（単調性の命題）・Results・図（変化率）を書き直す。
4. 残り：アーキテクチャ図（v3.4 表記が古い）、`video_frame_decision.png` の更新、REVIEW_NOTES、HANDOFF の更新。

## 6. 論文化で残っている作業

1. T1・E の結果を反映し、Results と Abstract を確定する（TBD を消す）。
2. 図：T1の例画像（`fig_t1_examples.pdf`）、リスク‐カバレッジ曲線、E の真値軌跡。
3. 遅延の内訳と VRAM の表。モデル比較の開発データ表は付録に入れる。
4. 推敲（主張と数値の整合、Limitations）。日本語版の要約を README に載せる。
5. 未解決：稀に 0.3 秒間送信が止まる現象の根本原因（I-09 で影響は除去済み）、実機での検証。

## 7. 主要ファイルの地図

`docs/ARCHITECTURE.md`（全体フロー図）、`docs/DESIGN_DECISIONS.md`（D1–D15）、`docs/IMPROVEMENT_LOG.md`（I-01–I-18）、
`docs/FINDINGS.md`（実行で見つけた25件）、`docs/REVIEW_AND_PLAN.md`（審査基準別レビュー）、`experiments/`（事前登録・プロトコル・開発セット・台帳・証拠）。

**2026-10-17 22:00 実行中の連鎖（最新）**
* `byvmbjuo9`：V の本番（予測は最初の試行より前にコミット済み：0118289）→ `V_DONE`（10月18日 6時ごろの見込み）。
* `bn71t32h1`：`V_DONE` を待つ → W のブランチをマージ（Amendment 1 の追加視点を含む）→ 描画（約2.6時間）→ 採点 → `W_DONE`。
* `b1lqzbr20`：`W_DONE` を待つ → Q のブランチをマージ（これが事前登録）→ テスト → `q_run.sh`（約40分）→ `Q_CHAIN_DONE`。
* その後は手動で進める：
  1. 統合ブランチ `i21-depot` を main にマージする（I-19・I-20・I-21・4拠点・軟拒否・scrutiny を含む）。
  2. 注入文の dev 半分でプロンプトを調整し、凍結 → A を事前登録 → 予備走行 → 本番（226 run、約11.5時間）。
  3. S（約2.4時間）→ XD・X（Sonnet が設計中）。

**2026-10-17 23:00 統合ブランチ `i21-depot`（worktree `.claude/worktrees/i21`）の状態**
* 含むもの：
  * I-19（助言は締めるだけ、study A は 226 run の草稿）
  * I-20（疑わしいときの追加視点）
  * I-21（倉庫、k=4、パレット、煙だけの火災）
  * 軟拒否（`--caution-soft`）、scrutiny（`--advice-scrutiny`）
  * 研究 S（看板・OCR マスク・文字を無視させる）、X・XD（倉庫）、L、I-18、W
  * 信頼基盤テスト（独立した参照実装・変異体 196 個・fuzz。実バグ 6 件を修正、FINDINGS #24・#25）
  * 論文（「Advice May Only Tighten」として一本の筋に再構成、本文 8 頁以内）
  * 説明資料（本文 5 頁、付録 A〜N）
* 模擬査読6回目（`REVIEW_NOTES_R6.md`）：結果が設計どおりなら RA-L で weak accept 圏。登録前に文言を固める作業（W Amendment 2・A/S/X/XD・命題2 の ε_any）を Sonnet が進めている。
* V・W・Q の後にすること：`i21-depot` を main にマージする → 全テスト → A（文言を固め、dev で調整して凍結、予備走行）→ XD → S → X。
* 要約図は新しい筋（助言は締めるだけ）に作り直す必要がある。結果が出てから行う。

**2026-10-17 23:00 連鎖の追加**
* `after_q_chain.sh`（PID で実行中。通知は来ない。ログは scratchpad の `after_q.log`）：`Q_CHAIN_DONE` を待つ → `origin/i21-depot` を main にマージ → 全テスト → 倉庫の素材を取得 → `a_run.sh`。
  * `a_run.sh`：予備走行 → マスク → 登録の確認（prereg・protocol・凍結したプロンプト）→ 226 run → 解析。
* 助言を取り出すプロンプトは、推論の前に書いたまま凍結した（`advice_prompts_frozen.json`）。dev 側では調整していない。
* 統合ブランチの追加分：
  * I-22 配送インターロックと、ガード側の避難所ジオフェンス。
  * Makefile（`make help`）。
  * 一本の筋に沿った要約図と README。
* 採点7回目（統合ブランチ）を Sonnet が実行中。

