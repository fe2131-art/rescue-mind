# HANDOFF — RescueMind（最終更新 2026-10-17）

作業を中断・文脈圧縮した後でも、このファイルだけで正確に再開できるようにまとめたもの。
**最優先ルール**（ユーザー指示）：
* リポジトリの公開設定（private→public）は**絶対に変更しない**（ユーザー本人が行う）。push は可。
* ユーザーへの質問・説明は**日本語・簡潔**に。omnicampus アカウント名は `tetsutetsu`。YouTube 投稿はユーザーが行う。
* sudo は使わない（docker グループ権限のみで全て動く）。必要になったらユーザーに依頼。
* 改善は必ずトレース可能に：`docs/IMPROVEMENT_LOG.md` に「動機→仮説→変更→計測(Before/After)→判断」、コミット先頭に `I-xx`。
* 現在の目標：**研究論文として発表できる完成度**に仕上げる（課題の枠を前面に出さない）。

---

## 1. 現在の到達点（v3.4、タグ `v3.3.0` 以降の改善 I-01〜I-09）

| 項目 | 状態・数値 | 証拠 |
|---|---|---|
| 閉ループ評価D（事前登録42試行、v3.4） | **42/42 期待どおり、誤許可0**、判断遅延中央値3.06 s | `experiments/PREREGISTRATION_v34.md`, `experiments/results/campaign_D_ledger.jsonl`, `docs/figures/campaign_d_results.png` |
| 評価C（v3.3、30試行、Qwen2.5-VL-3B、回復なし） | VLM判断30/30、監査合格28/30 | `experiments/results/campaign_ledger.jsonl` |
| 評価A・B（中断、公開） | 起動競合・孤立スタック（FINDINGS #12,#13） | `campaign_A/B_aborted_ledger.jsonl` |
| VLM（I-08） | **Qwen3.5-9B**（2026-02, Apache-2.0）。開発176枚 176/176・誤許可0、説明125/128 | `experiments/results/i08_model_selection.json` |
| 指示理解（I-04） | 未知60文（held-out）55/60・危険な誤受理0（TF-IDF 31/60） | `experiments/results/intent_hybrid_selected_qwen35_9b_i35.json` |
| ドリフト（I-01） | 0.16 m → 0.011 m（車輪の円柱接触→球） | `experiments/results/i01_drift/` |
| 停止中の途絶（I-09） | 停止注入A/B：旧2/2失敗→新2/2完了 | `experiments/results/i09_*.jsonl` |
| 動画 | 2:30、日本語ナレーション（VOICEVOX:四国めたん）、Git管理外 | `outputs/video/PAI最終課題_tetsutetsu.mp4`, `docs/video_plan.json`, `docs/video_chapters.json` |
| レポートPDF | 6ページ | `docs/report/説明資料_PAI最終課題_tetsutetsu.pdf` |
| ドキュメント | README, ARCHITECTURE, DESIGN_DECISIONS(D1–D8), FINDINGS(14件), IMPROVEMENT_LOG, REVIEW_AND_PLAN, SUBMISSION, YOUTUBE_DESCRIPTION | `docs/` |
| テスト | 525件前後（`python3 -m unittest discover -s tests`）、GitHub Actions 緑 | `.github/workflows/test.yml` |

**凍結構成（v3.4、評価Dと同じ）**：
```
--model Qwen/Qwen3.5-9B --prompt-set v35 --intent-backend llm --intent-prompt i35 --recovery --explain [--capture-rosbag]
閾値 τ_s=0.50（依頼物資の確率）, τ_h=0.50（危険Yes確率）。説明プロンプト e0。
```

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
デモ収録 run（`--film` 付き、動画で使用）：deliver `a93d6a9cc8704e6c`、recover `8b54abfb36454b27`、fire `a213a61bc53e4787`（`outputs/runs/` 内、Git管理外）。

## 4. 落とし穴（実際に踏んだもの）

* `pkill -f <pattern>` を `bash -c '...pattern...'` の中で使うと**自分自身のシェルも殺す**（exit 143）。スクリプトファイルから実行する。
* サーバ再起動直後は**古いサーバがまだ応答**することがある → `while curl -s -m 2 http://127.0.0.1:8765/health; do sleep 1; done` で消えるのを待つ。
* `nice` はファイルケーパビリティ付き → その exec は glibc セキュアモードで **LD_LIBRARY_PATH が消える**。`nice` は必ず「ROS を source するシェル」の外側に置く（`prioritised(shell_exec(...), n)`）。シェルスクリプト内は `renice -n N -p $$`。テスト `tests/test_v34_priority_wrapping.py`。
* ROS の `setup.bash` は `set -u` と相性が悪い → `set +u; source ...; set -u`。
* 画像トピックは Reliable QoS（`rescuemind/ros_qos.py`）。Best Effort だと 0.9 MB 画像が大量に欠落。
* 4コアのホストは CPU が飽和気味（ロードアベレージ約3.9）。**キャンペーン中に重い処理（動画合成・音声合成・ビルド）をしない**。キャンペーン中に実行時コードを編集しない（各試行がファイルを読み直す）。
* 非rootユーザーには `--cap-add` だけでは権限が渡らない（ファイルケーパビリティが必要）。
* Qwen3.5 は思考モードが既定 → `enable_thinking=False`（サーバで対応済み）。FP16 で非有限 logits なら判断拒否。
* 動画は **3分以内**（現在 2:30）。倍速は区間ごとに画面表示（走行4倍、確認2倍、判断の瞬間は等速）。

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
| T2（未使用の画像600枚） | v3.5 でも 0/407 と天井で、改善は測れない。Clef（課題向けの質問）単独でも 0/407・正しい許可 187/193、判断は約0.8秒 |
| 開発データ（I-11/I-13） | 見逃した火：v3.5 46 → h36＋tiles 17 → Clef＋Qwen 15（ただし 37 GB で V100 1台に載らない） |
| F（閉ループ、対比較） | 小さな火で配達してしまった回数：v3.5 12/13 → B 7/13（p=0.0625、有意でない） |
| G（閉ループ、対比較、新しい世界） | **横から見直す（I-14）で 11/16 → 1/16、p=0.002、誤った停止 0/8**。唯一の見逃し W19 は正面から0画素、横からも最小の2,308画素 |

**実行中（バックグラウンド）**
* `scripts/film_v36.sh`：最終構成での動画撮影（deliver / recover / empty / hidden_fire）。結果の run_id は `experiments/results/film_v36_runs.txt`。

**次の手順（優先順）**
1. **動画**：
   * `docker exec rm-dev rescuemind-entrypoint python3 scripts/make_video_plan.py --deliver <id> --recover <id> --empty <id> --hidden-fire <id>`（v3.6 の絵コンテに対応済み、目安175秒以下）
   * → `docker exec rm-dev rescuemind-entrypoint python3 scripts/make_demo_video.py --plan docs/video_plan.json --out outputs/video/PAI最終課題_tetsutetsu.mp4 --narrate 2`
   * VOICEVOX の docker（rm-voicevox）が必要。**3分以内**であることと、倍速が画面に表示されていることを確認する。
2. **最終数値の反映**：
   * `bash scripts/build_paper.sh`（論文。G の数値は自動で入る。TBD が残っていないか確認）
   * `python3 scripts/update_readme_results.py`（README）
   * `make_report.py`（説明資料PDF。サブエージェントが更新済み。G・F・T2・I-14 を追加する必要がある）
   * YOUTUBE_DESCRIPTION・SUBMISSION を更新する。
3. **シミュレーションでできる、現実への近さの検証**（実機の代わり。論文の最大の弱点への対策）。候補：
   * (a) カメラのノイズ・ぼけ・露出の変化・圧縮劣化への頑健性
   * (b) 写実的なテクスチャ・モデルの物資と火災
   * (c) 公開されている実写画像（ライセンスを確認）でのオフライン検査
   * (d) センサー遅延・ホイールの滑り
   * どれも、事前登録 → 開発／テストの分離、の手順で行う。
4. 論文の残り：`docs/paper/REVIEW_NOTES.md` の未対応分、図（G の結果、横からの視点の例）、Abstract と Contribution を v3.6 の結果で書き直す。

## 6. 論文化で残っている作業

1. T1・E の結果を反映し、Results と Abstract を確定する（TBD を消す）。
2. 図：T1の例画像（`fig_t1_examples.pdf`）、リスク‐カバレッジ曲線、E の真値軌跡。
3. 遅延の内訳と VRAM の表。モデル比較の開発データ表は付録に入れる。
4. 推敲（主張と数値の整合、Limitations）。日本語版の要約を README に載せる。
5. 未解決：稀に 0.3 秒間送信が止まる現象の根本原因（I-09 で影響は除去済み）、実機での検証。

## 7. 主要ファイルの地図

`docs/ARCHITECTURE.md`（全体フロー図）、`docs/DESIGN_DECISIONS.md`（D1–D8）、`docs/IMPROVEMENT_LOG.md`（I-01–I-09）、
`docs/FINDINGS.md`（実行で見つけた14件）、`docs/REVIEW_AND_PLAN.md`（審査基準別レビュー）、`experiments/`（事前登録・プロトコル・開発セット・台帳・証拠）。
