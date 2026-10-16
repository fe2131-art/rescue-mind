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

## 5. 進行中・未コミット

* なし（回帰確認 E2：最終コードで 6/6 期待どおり、コミット済み）。
* 失敗した回帰確認 E（rosbag が LD_LIBRARY_PATH を失う、FINDINGS #14）も `regression_E_ledger.jsonl` として保存。

## 6. 論文化に向けた次の作業（優先順）

1. **論文原稿**：`docs/paper/`（Markdown→PDF）。構成：Abstract / Introduction / Related Work / System / Methods（閉集合スコアリング、回復探索、真値監査、事前登録）/ Experimental Setup / Results / Ablations / Failure analysis（FINDINGS, I-09）/ Limitations / Reproducibility。日本語版と英語版を検討。
2. **統計的な厳密さ**：比率に Wilson 95%信頼区間、試行数の拡大、**シーンを試行ごとにランダム化**（小道具位置・照明・視点・妨害物）して独立性を高めた評価E（事前登録）。
3. **ベースラインとアブレーション**（同一プロトコル）：確認なし（盲目的配達）／回復なし／質問1つのみ／危険質問なし／自由生成JSON／Qwen2.5-VL-3B／TF-IDF 指示理解。誤配達率・配達成功率・所要時間で比較。
4. **関連研究**（必ず一次情報で確認して引用）：ロボットの失敗検知・自己検証（例：REFLECT、AHA、Inner Monologue、SayCan、KnowNo の conformal prediction）、VLM による成功判定、Sim-to-Real。
5. 遅延の内訳（画像取得・推論・説明）と VRAM・消費の表。
6. 未解決：稀な 0.3 秒の送信停止の根本原因（I-09 で影響は除去済み）、小道具の写実性、実機（SO-101 等）での検証。

## 7. 主要ファイルの地図

`docs/ARCHITECTURE.md`（全体フロー図）、`docs/DESIGN_DECISIONS.md`（D1–D8）、`docs/IMPROVEMENT_LOG.md`（I-01–I-09）、
`docs/FINDINGS.md`（実行で見つけた14件）、`docs/REVIEW_AND_PLAN.md`（審査基準別レビュー）、`experiments/`（事前登録・プロトコル・開発セット・台帳・証拠）。
