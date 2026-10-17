# 再現手順（査読者・採点者向け）

事前登録した各研究を再現し、論文・報告書・README の数値を再生成するための手順。パスは `<repo>`（リポジトリのルート）からの相対で書く。
研究の内容・結論は `README.md`、`docs/paper/main.pdf`、`docs/HANDOFF.md` を参照。

## 1. 前提

| 項目 | 内容 |
|---|---|
| GPU | NVIDIA V100 32GB 相当（検証環境は Tesla V100 32GB、4コア）。研究 J の 2 モデル構成のピークは約 28.7 GB（`experiments/results/j_smoke_stdout.log`、`j_smoke_vram.csv`）。 |
| ホスト | Ubuntu 22.04、Docker（`docker` グループ、nvidia-container-toolkit）。sudo は不要。ROS はホストに不要。 |
| コンテナ | ROS 2 Jazzy + Gazebo Harmonic + CUDA PyTorch（`docker/Dockerfile`）。標準は `STACK=next`（torch 2.8.0+cu126、transformers 5.20.0）。`STACK=v33` は旧スタック（torch 2.5.1、transformers 4.53.3）。 |
| モデル重み | Hugging Face から一度だけ取得し、以降は `HF_HUB_OFFLINE=1`（`docker/run.sh` の既定）。キャッシュはホストの `$HF_HOME`（既定 `~/.cache/huggingface`）を `/hf` に共有。 |
| 同時実行 | 2 つのスタックを同時に走らせない（同じ ROS ドメイン 73 / Gazebo パーティション / ポート 8765）。キャンペーン中に `rescuemind/` や `scripts/` を編集しない。 |

詳細な落とし穴は `docs/HANDOFF.md` §2–§4。

## 2. イメージのビルドとコンテナ起動

```bash
# 標準（next）スタック
RESCUEMIND_IMAGE=rescuemind:jazzy-next bash docker/build.sh
# 旧スタック（図・PDF・テスト用の rm-dev で使用）
docker build --build-arg STACK=v33 -t rescuemind:jazzy docker
# 論文の LaTeX 用
docker build -t rescuemind:latex docker/latex

# 作業用コンテナ（repo を同じ絶対パスでマウント）
RESCUEMIND_IMAGE=rescuemind:jazzy-next RESCUEMIND_CONTAINER=rm-next bash docker/run.sh sleep infinity   # 閉ループ・GPU 実験
RESCUEMIND_CONTAINER=rm-dev bash docker/run.sh sleep infinity                                           # テスト・図・解析
# モデル重みの取得（初回のみ。HF_HUB_OFFLINE=0 が必要）
HF_HUB_OFFLINE=0 bash docker/run.sh python3 -c "from huggingface_hub import snapshot_download as s; s('Qwen/Qwen3.5-9B')"
```

以降の `X` は `docker exec rm-next rescuemind-entrypoint`（GPU 実験）、`Y` は `docker exec rm-dev rescuemind-entrypoint`（解析）の略。
取得するモデル：Qwen/Qwen3.5-9B（既定）、Qwen/Qwen3.5-4B、Qwen/Qwen3-VL-8B-Instruct、Qwen/Qwen2.5-VL-3B-Instruct（比較用）。研究 J は Clef-Flash（`scripts/clef_server.py`）も使う。

## 3. 事前登録した研究ごとの再現

共通：結果は追記式の台帳（`*_ledger.jsonl`）に保存され、同じコマンドを再実行すると中断した所から再開する。閉ループ 1 試行は中央値で約 100 秒（台帳の `wall_s`）。解析スクリプトは結果ファイルだけを入力とし、数値を手入力しない。
`<flags>` は台帳の `stack_args` に記録された凍結構成（D と E は `--model Qwen/Qwen3.5-9B --prompt-set v35 --intent-backend llm --intent-prompt i35 --recovery --explain`、E はさらに `--hazard-threshold 0.05`）。

### 閉ループ（Gazebo + ROS 2 + VLM）

| 研究 | 登録 | 試行数 | 実行コマンド | 目安 | 出力 | 解析（要約 JSON） |
|---|---|---|---|---|---|---|
| D | `experiments/PREREGISTRATION_v34.md`、`experiments/v34_protocol.json` | 42 | `X python3 scripts/run_campaign.py --protocol experiments/v34_protocol.json --ledger experiments/results/campaign_D_ledger.jsonl -- <flags>` | 約 1.2 h | `campaign_D_ledger.jsonl`、`campaign_D_ledger_fire_visibility.json` | 専用の要約 JSON なし。`Y python3 scripts/export_evidence.py experiments/results/campaign_D_ledger.jsonl` → `make_figures.py`（`figure_stats.json`）、`paper_numbers.py` |
| E | `PREREGISTRATION_E.md`、`campaign_e_protocol.json`（`scripts/make_protocol_e.py`、seed `E-2026`） | 60 | `X python3 scripts/run_campaign.py --protocol experiments/campaign_e_protocol.json --ledger experiments/results/campaign_E_ledger.jsonl -- <flags> --hazard-threshold 0.05` | 約 1.7 h | `campaign_E_ledger.jsonl` | 専用の要約 JSON なし。`paper_numbers.py`、`update_readme_results.py` が台帳から直接集計 |
| F | `PREREGISTRATION_F.md`、`campaign_f_protocol.json`（`make_protocol_f.py`、`F-2026`） | 48（対比較 A/B） | `X python3 scripts/run_campaign.py --protocol experiments/campaign_f_protocol.json --ledger experiments/results/campaign_F_ledger.jsonl` | 約 1.4 h | `campaign_F_ledger.jsonl`、`campaign_F_ledger_fire_masks.json` | `X python3 scripts/fire_mask_at_pose.py --protocol experiments/campaign_f_protocol.json --ledger experiments/results/campaign_F_ledger.jsonl`（Gazebo 起動、他のスタックなし）→ `Y python3 scripts/f_analysis.py` → `f_summary.json` |
| G | `PREREGISTRATION_G.md`、`campaign_g_protocol.json`（`make_protocol_g.py`、`G-2026`） | 48（対比較 B/C） | `X python3 scripts/run_campaign.py --protocol experiments/campaign_g_protocol.json --ledger experiments/results/campaign_G_ledger.jsonl` | 約 1.4 h | `campaign_G_ledger.jsonl`、`campaign_G_ledger_fire_masks.json`（`fire_mask_at_pose.py` で生成） | `fire_mask_at_pose.py`（F と同じ形式で G の protocol と台帳を指定）→ `g_analysis.py` → `g_summary.json` |
| H | `PREREGISTRATION_H.md`、`campaign_h_protocol.json`（`make_protocol_h.py`、`H-2026`）。設計時の火マスク `campaign_h_protocol_design_fire_masks.json` | 112（16 系列×3 出動、M0/M1/M2） | `X python3 scripts/run_campaign.py --protocol experiments/campaign_h_protocol.json --ledger experiments/results/campaign_H_ledger.jsonl` | 約 3–6 h | `campaign_H_ledger.jsonl`、`memory_H/`（系列ごとの記憶ファイル） | `Y python3 scripts/h_analysis.py` → `h_summary.json`；`Y python3 scripts/h_change_rate_model.py` → `h_change_rate.json`、`docs/paper/fig_h_change_rate.pdf` |
| J | `PREREGISTRATION_J.md`、`campaign_j_protocol.json`（`make_protocol_j.py`、`J-2026`）。2 モデル構成は protocol の `configs.J` | 48（24 世界の対比較 A/J） | `X python3 scripts/run_campaign.py --protocol experiments/campaign_j_protocol.json --ledger experiments/results/campaign_J_ledger.jsonl` | 約 1.5–2.5 h | `campaign_J_ledger.jsonl`、`campaign_J_vram.csv` | `Y python3 scripts/j_analysis.py` → `j_summary.json` |

H と J の本番は `scripts/final_chain.sh` が連鎖実行していた（J の前に試運転で VRAM を確認）。H・J の結果ファイルは、実行が完了するまで存在しない（本書の作成時点で `h_summary.json`、`j_summary.json` は未生成）。
F と G の `common_stack_args` は protocol に含まれるため、`--` 以降の指定は不要。H・J は v3.6 の既定構成で、J の差分フラグも protocol 側にある。

### オフライン（画像集合の採点）

画像集合 T1/T2/開発セットは Gazebo で描画してある（`experiments/vlm_testset_t1`、`vlm_testset_t2`、`vlm_devset*`）。再描画する場合は他のスタックを止めて `build_testset_t1.py` / `build_image_set.py` を使う（`--spec-only` で仕様だけ作れる）。

| 研究 | 登録 | 実行コマンド | 出力 | 解析（要約 JSON） |
|---|---|---|---|---|
| T1（未使用 600 枚） | `PREREGISTRATION_T1.md`、`vlm_testset_t1/spec.json` | `X bash scripts/t1_eval_all.sh`（モデルごとにサーバを起動して `vlm_devset_eval.py` を実行） | `devset_t1_*.json`、`t1_eval_stdout.log` | `Y python3 scripts/t1_analysis.py` → `t1_summary.json` |
| T2（未使用 600 枚） | `PREREGISTRATION_T2.md`、`vlm_testset_t2/spec.json`（`build_image_set.py --set t2`）。構成の選定は開発データのみ（`i13_select.py` → `i13_selection.json`） | `X bash scripts/t2_eval.sh` | `devset_t2_*.json` | `t2_analysis.py`（`t2_eval.sh` の末尾で実行）→ `t2_summary.json` |
| Z（ゼロショット SigLIP/CLIP） | `PREREGISTRATION_Z.md` | `X python3 scripts/zeroshot_baseline.py`（しきい値は開発データのみで選択） | `z_scores_{siglip,clip}.json`、`z_thresholds.json`、`docs/paper/tab_z.tex` | 同スクリプトが `z_summary.json` を出力 |
| R（カメラ劣化 12 条件） | `PREREGISTRATION_R.md` | `X bash scripts/r_eval.sh`（再開可、停止は `scripts/stop_r.sh`） | `devset_r_<条件>.json`、`r_eval_stdout.log` | `Y python3 scripts/r_analysis.py` → `r_summary.json`、`docs/paper/tab_r.tex` |
| P（実写の火災画像） | `PREREGISTRATION_P.md` | pyarrow 入りの Python（例 `~/.cache/rescuemind/pqvenv/bin/python`）で `scripts/p_realphoto_eval.py --data ~/.cache/rescuemind/dfire --sample`、続けて VLM サーバ（Qwen3.5-9B、h36 + tiles、ポート 8765）を起動して `--run`。D-Fire（CC0、HF `badsaarow/d-fire` の test 分割）はリポジトリ外に置く | `p_sample.json`、`p_scores_qwen9b_h36_tiles.jsonl` | `p_realphoto_eval.py --analyse` → `p_summary.json` |
| P2（実写でのしきい値較正） | `PREREGISTRATION_P2.md` | ホストで `bash scripts/p2_eval.sh`（サーバは `rm-next` 内で起動。pyarrow 入りの Python は `P2_PYTHON` で指定） | `p2_sample.json`、`p2_server.log` | `p2_calibration.py --analyse` → `p2_summary.json`（実行完了後に生成） |

開発セット（I-11/I-13 の選定）は `scripts/i11_eval.sh`、`scripts/i11_select.py`（`i11_selection.json`）、`scripts/i13_select.py`（`i13_selection.json`）。held-out（T1/T2）はチューニングに使わない。

### 研究 L（配置のランダム化）

未マージ（実装は別ブランチのみ）。マージして事前登録・実行が済むまで本書の対象外とする。

## 4. 論文・報告書・README の数値の再生成

数値はすべて結果ファイルから生成する（手入力なし）。上の解析を先に実行してから行う。

```bash
Y python3 scripts/count_tests.py          # テスト件数 → experiments/results/test_count.json
python3 scripts/paper_numbers.py          # docs/paper/numbers.tex と tab_*.tex
bash scripts/build_paper.sh               # 図の生成 + LaTeX → docs/paper/main.pdf（rm-dev と rescuemind:latex が必要）
Y python3 scripts/make_figures.py
python3 scripts/update_readme_results.py  # README の結果ブロックを書き換え
Y python3 scripts/make_report.py --account tetsutetsu   # docs/report/ の説明資料 PDF
```

欠けている結果は論文中で `\TBD` と表示される。

## 5. 実行の証拠の確認

* **テスト**：`Y python3 -m unittest discover -s tests -q`。公開物の個人パス検査は `Y python3 -m unittest tests.test_no_personal_paths`。
* **1 試行の証拠**（`outputs/runs/<run_id>/` は Git 管理外。公開用の抜粋は `scripts/export_evidence.py` が `experiments/results/evidence/<run_id>/` に作る）：`stack_result.json`（最終状態）、`mission.json`（判断・各段階のイベント）、`checkpoint.jpg`（VLM が見た画像）、`rosbag2_metadata.yaml`、`ground_truth_xy.json`（Gazebo の真値軌跡）。
  * 画像の照合：`sha256sum experiments/results/evidence/<run_id>/checkpoint.jpg` が `mission.json` の `image_sha256` と一致すること。
  * rosbag（MCAP）は `--capture-rosbag` 付きの実行で `outputs/runs/<run_id>/` に残る。`ros2 bag info` で確認できる。
* **台帳の整合**：台帳の各行に `run_id`、`state`、`image_sha256`、`models`、`stack_args` がある。事前登録の記録（`PREREGISTRATION_*.md`）は結果より前の git コミットで固定してあり、論文付録「Registration audit」が `git merge-base --is-ancestor` で機械的に確認している。
* **安全側の単調性（H の記憶）**：記憶は確認を減らさないことを監査コードが再計算する（`rescuemind/mission_memory.py`、`tests/test_i15_memory.py`）。
* **リポジトリ全体の検査**：`scripts/public_release_audit.py`（秘密情報・メールアドレスの簡易検査。プライバシーの保証ではない）、`scripts/verify_all.sh`（オフライン一括検査）。
* 1 試行ずつの機械可読ログの簡易検査：`scripts/audit_robot_run.py <mission.json>`（進行の確認であり、物理的な真正性の証明ではない）。
