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
| C（v3.3、歴史的） | `PREREGISTRATION_v33.md`、`v23_locked_protocol.json`（`run_campaign.py` の既定） | 30 | `X python3 scripts/run_campaign.py --no-rosbag -- --model Qwen/Qwen2.5-VL-3B-Instruct --prompt-set v33 --intent-backend tfidf --no-recovery --no-explain`（`rescuemind:jazzy`＝`STACK=v33` のイメージ。台帳に `stack_args` が無いため、旧既定値に合わせて再構成した引数。`--no-rosbag` の有無は未確認） | 約 0.6 h | `campaign_ledger.jsonl` | 専用の要約 JSON なし。`paper_numbers.py` が `CN`、`CVlmCorrect` を台帳から集計、`make_figures.py` が `figure_stats.json` |
| D | `experiments/PREREGISTRATION_v34.md`、`experiments/v34_protocol.json` | 42 | `X python3 scripts/run_campaign.py --protocol experiments/v34_protocol.json --ledger experiments/results/campaign_D_ledger.jsonl -- <flags>` | 約 1.2 h | `campaign_D_ledger.jsonl`、`campaign_D_ledger_fire_visibility.json` | 専用の要約 JSON なし。`Y python3 scripts/export_evidence.py experiments/results/campaign_D_ledger.jsonl` → `make_figures.py`（`figure_stats.json`）、`paper_numbers.py` |
| E | `PREREGISTRATION_E.md`、`campaign_e_protocol.json`（`scripts/make_protocol_e.py`、seed `E-2026`） | 60 | `X python3 scripts/run_campaign.py --protocol experiments/campaign_e_protocol.json --ledger experiments/results/campaign_E_ledger.jsonl -- <flags> --hazard-threshold 0.05` | 約 1.7 h | `campaign_E_ledger.jsonl` | 専用の要約 JSON なし。`paper_numbers.py`、`update_readme_results.py` が台帳から直接集計。軌跡図用に `Y python3 scripts/export_evidence.py experiments/results/campaign_E_ledger.jsonl`（`evidence/<run_id>/ground_truth_xy.json`） |
| F | `PREREGISTRATION_F.md`、`campaign_f_protocol.json`（`make_protocol_f.py`、`F-2026`） | 48（対比較 A/B） | `X python3 scripts/run_campaign.py --protocol experiments/campaign_f_protocol.json --ledger experiments/results/campaign_F_ledger.jsonl` | 約 1.4 h | `campaign_F_ledger.jsonl`、`campaign_F_ledger_fire_masks.json` | `X python3 scripts/fire_mask_at_pose.py --protocol experiments/campaign_f_protocol.json --ledger experiments/results/campaign_F_ledger.jsonl`（Gazebo 起動、他のスタックなし。F だけは台帳の撮影姿勢でマスクを作る）→ `Y python3 scripts/f_analysis.py` → `f_summary.json` |
| G | `PREREGISTRATION_G.md`、`campaign_g_protocol.json`（`make_protocol_g.py`、`G-2026`） | 48（対比較 B/C） | `X python3 scripts/run_campaign.py --protocol experiments/campaign_g_protocol.json --ledger experiments/results/campaign_G_ledger.jsonl` | 約 1.4 h | `campaign_G_ledger.jsonl`。解析が使う設計時の火マスク `experiments/campaign_g_protocol_design_fire_masks.json`（正面と左右 0.4 m の 3 視点。コミット済み。再生成：`X python3 scripts/fire_mask_at_pose.py --protocol experiments/campaign_g_protocol.json --design --design-sides 0.4`） | `Y python3 scripts/g_analysis.py` → `g_summary.json` |
| H | `PREREGISTRATION_H.md`、`campaign_h_protocol.json`（`make_protocol_h.py`、`H-2026`）。設計時の火マスク `campaign_h_protocol_design_fire_masks.json` | 112（16 系列×3 出動、M0/M1/M2） | `X python3 scripts/run_campaign.py --protocol experiments/campaign_h_protocol.json --ledger experiments/results/campaign_H_ledger.jsonl` | 約 3–6 h | `campaign_H_ledger.jsonl`、`memory_H/`（系列ごとの記憶ファイル）。設計時の火マスクの再生成：`X python3 scripts/fire_mask_at_pose.py --protocol experiments/campaign_h_protocol.json --design --design-sides 0.4` | `Y python3 scripts/h_analysis.py` → `h_summary.json`；`Y python3 scripts/h_change_rate_model.py` → `h_change_rate.json`、`docs/paper/fig_h_change_rate.pdf` |
| J | `PREREGISTRATION_J.md`、`campaign_j_protocol.json`（`make_protocol_j.py`、`J-2026`）。2 モデル構成は protocol の `configs.J` | 48（24 世界の対比較 A/J） | `X python3 scripts/run_campaign.py --protocol experiments/campaign_j_protocol.json --ledger experiments/results/campaign_J_ledger.jsonl` | 約 1.5–2.5 h | `campaign_J_ledger.jsonl`、`campaign_J_vram.csv`（実行中に `nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -l 1` を記録したもの。`final_chain.sh` 参照）。設計時の火マスクは H と同じ要領で `campaign_j_protocol.json` に対して生成 | `Y python3 scripts/j_analysis.py` → `j_summary.json` |
| V（H のモデルの閉ループ検証） | `PREREGISTRATION_V.md`、`campaign_v_protocol.json`（`make_protocol_v.py`）、予備走行 `campaign_v_pilot_protocol.json`（4 run）、設計時の火マスク `campaign_v_protocol_design_fire_masks.json` | 160（10 系列×(1+5×3)） | `bash scripts/v_run.sh`（`rm-next` を操作するのでホストで実行。予備走行 → 火マスク → 予測を先にコミット → 本番 → 解析を順に実行し、予備走行が設計どおりでなければ `V_ABORT` で止まる）。個別に実行する場合：`X python3 scripts/run_campaign.py --protocol experiments/campaign_v_protocol.json --ledger experiments/results/campaign_V_ledger.jsonl` | 約 5 h（推定、§7） | `campaign_V_ledger.jsonl`、`campaign_V_pilot_ledger.jsonl`、`v_predictions.json`（本番の前にコミット） | `python3 scripts/v_predict.py`（予測）、`python3 scripts/v_analysis.py` → `v_summary.json`（未実行：L の後に連鎖で実行予定） |

H と J の本番は `scripts/final_chain.sh` が連鎖実行していた（J の前に試運転で VRAM を確認。`final_chain.sh` の第 1 引数は「`R_DONE` を含む出力ファイル」で、再現には不要）。`h_summary.json` は生成済み。`j_summary.json`、`v_summary.json`、`p2_summary.json` は、それぞれの実行が完了するまで存在しない（本書の更新時点で J は 48 run 中 41 行まで、V と P2 は未実行）。
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
| K（適合予測によるしきい値の較正） | `PREREGISTRATION_K.md` | なし（保存済みスコアだけを使う。GPU 不要） | `k_summary.json` | `python3 scripts/k_conformal.py` → `k_summary.json` |
| 補助（事前登録外・記述的） | — | なし | `jev_overlap.json`、`h_k_scaling.json`、`h_change_rate.json` | `python3 scripts/jev_overlap.py`（開発セット DH+DH2 で Qwen と Clef の見逃しの重なり）、`python3 scripts/h_k_scaling.py`（拠点数 k に対する記憶の効果。`h_change_rate.json` が必要） |

開発セット（I-11/I-13 の選定）は `scripts/i11_eval.sh`、`scripts/i11_select.py`（`i11_selection.json`）、`scripts/i13_select.py`（`i13_selection.json`）。held-out（T1/T2）はチューニングに使わない。

### 研究 L・W（ブランチ上。マージ後に再現可能）

どちらも `main` には未マージ。マージして事前登録をコミットするまで、結果ファイルは存在しない。マージ後の手順（各ブランチのスクリプトの引数を確認済み）：

| 研究 | ブランチ | 登録 | 実行 | 出力・解析 |
|---|---|---|---|---|
| L（拠点配置のランダム化、24 世界） | `worktree-agent-ac85b5ba081cc1f61` | `PREREGISTRATION_L.md`、`campaign_l_protocol.json`、試運転 `campaign_l_smoke_protocol.json`（`make_protocol_l.py [--smoke]`） | `bash scripts/l_run.sh`（ホストで実行。設計時火マスク → `l_smoke.sh`（`rm-next` 内で実行される）→ 本番 → 解析。試運転が全 run 完了でなければ `L_ABORT`） | `campaign_L_smoke_ledger.jsonl`、`campaign_L_ledger.jsonl`、`python3 scripts/l_analysis.py` → `l_summary.json` |
| W-a（小さく隠れた火の画像 675 枚）・W-b（先行手法との比較） | `worktree-agent-a065158341fac6202` | `PREREGISTRATION_W.md`、`campaign_w_protocol.json`（`make_protocol_w.py`） | `X bash scripts/w_render.sh`（約 2 h：画像 → 火マスク → ラベル。登録のコミットを確認してから描画）→ `bash scripts/w_eval.sh`（`W_STAGES=a|b|ab`、再開可。VLM サーバを自動起動） | `devset_w_*.json`、`devset_t1_i11_h36_{tiles,full}.json`、`w_analysis_stdout.log`、`python3 scripts/w_analysis.py [--part a|b|all]` → `w_summary.json` |

L のマージで `paper_numbers.py`、`main.tex`、`tab_prereg.tex` も更新される（L の数値マクロと登録一覧の行）。W にはまだ論文への配線がない（`w_summary.json` を読む `paper_numbers.py` の節は未実装）。

## 4. 論文・報告書・README の数値の再生成

数値はすべて結果ファイルから生成する（手入力なし）。上の解析を先に実行してから行う。

```bash
Y python3 scripts/count_tests.py          # テスト件数 → experiments/results/test_count.json
python3 scripts/paper_numbers.py          # docs/paper/numbers.tex と tab_*.tex
bash scripts/build_paper.sh               # 図の生成 + LaTeX → docs/paper/main.pdf（rm-dev と rescuemind:latex が必要）
Y python3 scripts/make_figures.py        # 旧来の図 docs/figures/*.png（D/E 台帳と図用の統計 figure_stats.json）
Y python3 scripts/make_memory_case_figure.py   # fig_h_case.pdf（H の記憶の事例。下の注意を参照）
python3 scripts/update_readme_results.py  # README の結果ブロックを書き換え
Y python3 scripts/make_report.py --account tetsutetsu   # docs/report/ の説明資料 PDF
```

欠けている結果は論文中で `\TBD` と表示される。`python3 scripts/paper_numbers.py --final` は未了の結果があると失敗する。

注意（`outputs/runs/` は Git 管理外）：`fig_lookaround.pdf`、`fig_h_case.pdf`、`tab_timing.tex`（と `operator_report_*.png` の例）が読む試行の記録のうち、必要な最小部分は `experiments/evidence/runs/<run_id>/`（`mission.json`、`stack_result.json`、チェック画像 `*.jpg` のみ。rosbag・ログ・動画は含まない。合計約 0.7 MB）にコミットしてある。スクリプトは `outputs/runs/<run_id>/` を先に見て、無ければこのコピーを読む（`scripts/run_paths.py`。環境変数 `RESCUEMIND_RUNS_DIR` で前者の場所を変えられる）。対応する run は次の通り。`fig_lookaround.pdf` は `9d73663832c94f16`、`fig_h_case.pdf` は `4e5461e9e58542c4`（M0）と `54c52d274181424a`（M2）、`operator_report_hidden_fire`／`_recover`／`_memory_case` はそれぞれ `9d73663832c94f16`／`b4fcd9d164444db7`／`54c52d274181424a`。`tab_timing.tex` と `TimDrive` などは、台帳 D・E の配達した試行 34 件の段階別の経過時間を持つ `experiments/results/timing_runs.json` から再計算される（`outputs/runs` があればそちらが優先）。コピーは `python3 scripts/export_run_evidence.py` が作る（絶対パスは相対に置換）。図を作り直すと別の run_id で近い図になる点は変わらないが、コミット済みの記録からは同じ図が再生成できる（`operator_report_*` の再描画には CJK フォントが要る）。

## 5. 実行の証拠の確認

* **テスト**：`Y python3 -m unittest discover -s tests -q`。公開物の個人パス検査は `Y python3 -m unittest tests.test_no_personal_paths`。
* **1 試行の証拠**（`outputs/runs/<run_id>/` は Git 管理外。図が読む最小部分は `experiments/evidence/runs/<run_id>/` にコミット済み（`scripts/export_run_evidence.py`）。公開用の抜粋は `scripts/export_evidence.py` が `experiments/results/evidence/<run_id>/` に作る）：`stack_result.json`（最終状態）、`mission.json`（判断・各段階のイベント）、`checkpoint.jpg`（VLM が見た画像）、`rosbag2_metadata.yaml`、`ground_truth_xy.json`（Gazebo の真値軌跡）。
  * 画像の照合：`sha256sum experiments/results/evidence/<run_id>/checkpoint.jpg` が `mission.json` の `image_sha256` と一致すること。
  * rosbag（MCAP）は `--capture-rosbag` 付きの実行で `outputs/runs/<run_id>/` に残る。`ros2 bag info` で確認できる。
* **台帳の整合**：台帳の各行に `run_id`、`state`、`image_sha256`、`models`、`stack_args` がある。事前登録の記録（`PREREGISTRATION_*.md`）は結果より前の git コミットで固定してあり、論文付録「Registration audit」が `git merge-base --is-ancestor` で機械的に確認している。
* **安全側の単調性（H の記憶）**：記憶は確認を減らさないことを監査コードが再計算する（`rescuemind/mission_memory.py`、`tests/test_i15_memory.py`）。
* **リポジトリ全体の検査**：`scripts/public_release_audit.py`（秘密情報・メールアドレスの簡易検査。プライバシーの保証ではない）、`scripts/verify_all.sh`（旧来のオフライン一括検査。`python` を直接呼ぶので `Y bash scripts/verify_all.sh` のようにコンテナ内で実行）。
* 1 試行ずつの機械可読ログの簡易検査：`scripts/audit_robot_run.py --record outputs/runs/<run_id>/mission.json [--out ...]`（進行の確認であり、物理的な真正性の証明ではない）。

## 6. 結果ファイル → 生成スクリプト → 研究 → 論文での使用先（一覧）

`experiments/results/` の相対パス。「論文」は `docs/paper/main.tex`（本文）と `supplement.tex`（補足）。数値は `numbers.tex` のマクロ（`paper_numbers.py` が生成。括弧内はマクロ名の接頭辞）、表は `tab_*.tex`、図は `\fig{...}` で読み込む PDF。「実行場所」の X/Y は §2 の定義、無印はホストの `python3`。

| 結果ファイル／図 | 生成スクリプト（実行場所） | 研究 | 論文での使用先 |
|---|---|---|---|
| `campaign_ledger.jsonl` | `run_campaign.py`（X、v33 イメージ） | C | マクロ `CN`、`CVlmCorrect`、`tab_prereg` |
| `campaign_D_ledger.jsonl`、`campaign_D_ledger_fire_visibility.json` | `run_campaign.py`（X）、`fire_visibility_check.py` | D | マクロ `D*`、`tab_timing`（`timing_runs.json`）、`tab_prereg` |
| `campaign_E_ledger.jsonl`、`evidence/<run_id>/ground_truth_xy.json` | `run_campaign.py`（X）、`export_evidence.py`（Y） | E | マクロ `E*`、`tab_e_strata`、`tab_timing`、`fig_e_trajectories.pdf`（補足） |
| `devset_t1_*.json`（6 構成）、`t1_summary.json` | `t1_eval_all.sh`（X）、`t1_analysis.py`（Y） | T1 | マクロ `T*`・`Stat*`、`tab_t1_models`、`tab_t1_ablation`、`fig_t1_examples.pdf`・`fig_risk_coverage.pdf`（補足） |
| `devset_t1_i11_h36_{tiles,full}.json`（W-b が必要とする T1 の v3.6 採点） | `w_eval.sh`（W のマージ後） | W-b | 未配線（W は論文に未接続） |
| `devset_t2_*.json`、`t2_summary.json` | `t2_eval.sh`（X）、`t2_analysis.py` | T2 | マクロ `TT*`・`StatTtwo`、`fig_fire_size.pdf`・`fig_r_examples.pdf` の入力 |
| `devset_dh*_*.json`、`devset_v1_*`、`devset_v2_*`、`i11_selection.json`、`i13_selection.json`、`i08_model_selection.json` | `i11_eval.sh`、`model_comparison_v35.sh`、`i11_select.py`、`i13_select.py`、`model_selection_table.py` | 開発（I-08/I-11/I-13） | `tab_i13_dev`、`tab_dev_models`、マクロ `DevFire*`、`fig_fire_size.pdf` |
| `intent_*.json` | `intent_eval.py`（X） | I-04（指示理解） | マクロ `Int*` |
| `f_summary.json`、`campaign_F_ledger_fire_masks.json` | `fire_mask_at_pose.py --ledger`（X）→ `f_analysis.py`（Y） | F | マクロ `F*`（`FMc` など） |
| `g_summary.json`（入力：`experiments/campaign_g_protocol_design_fire_masks.json`） | `fire_mask_at_pose.py --design --design-sides 0.4`（X）→ `g_analysis.py`（Y） | G | マクロ `G*`、`fig_fire_size.pdf` の (b)、`fig_lookaround.pdf`（run を読む） |
| `devset_r_<条件>.json` ×12、`r_summary.json`、`tab_r.tex` | `r_eval.sh`（X）→ `r_analysis.py`（Y） | R | マクロ `R*`、`tab_r`（補足）、`fig_r_examples.pdf` |
| `z_scores_{siglip,clip}.json`、`z_thresholds.json`、`z_summary.json`、`tab_z.tex` | `zeroshot_baseline.py`（X） | Z | マクロ `Z*`、`tab_z`（本文） |
| `campaign_H_ledger.jsonl`、`memory_H/`、`experiments/campaign_h_protocol_design_fire_masks.json` | `run_campaign.py`、`fire_mask_at_pose.py --design --design-sides 0.4`（X） | H | （解析の入力） |
| `h_summary.json` | `h_analysis.py`（Y） | H | マクロ `H*`、`tab_h_arms`（本文）、`tab_h_sequences`（補足）、`fig_h_outcomes.pdf`・`fig_h_case.pdf`（補足） |
| `h_change_rate.json`、`fig_h_change_rate.pdf` | `h_change_rate_model.py`（Y） | H（モデル） | マクロ `HModel*`、`fig_h_change_rate.pdf`（本文） |
| `h_k_scaling.json` | `h_k_scaling.py`（記述的・事前登録外） | H（拡張） | マクロ `HK*` |
| `jev_overlap.json` | `jev_overlap.py`（開発セットのみ） | J（付随） | マクロ `JevOv*` |
| `campaign_J_ledger.jsonl`、`campaign_J_vram.csv`、`j_smoke_*`、`experiments/campaign_j_protocol_design_fire_masks.json` | `run_campaign.py`（X）、`final_chain.sh`、`fire_mask_at_pose.py --design` | J | （解析の入力。VRAM は §1 の 28.7 GB） |
| `j_summary.json`（J 完了後） | `j_analysis.py` | J | マクロ `J*` |
| `k_summary.json` | `k_conformal.py` | K | マクロ `K*`・`StatK` |
| `p_sample.json`、`p_scores_qwen9b_h36_tiles.jsonl`、`p_summary.json` | `p_realphoto_eval.py`（`--sample`/`--run`/`--analyse`） | P | マクロ `P*`（`PRecall`、`PAuroc` など） |
| `p2_sample.json`、`p2_scores_{h36,h35}.jsonl`、`p2_summary.json`（P2 完了後） | `p2_eval.sh`、`p2_calibration.py --analyse` | P2 | マクロ `PTwo*` |
| `campaign_V_ledger.jsonl`、`v_predictions.json`、`campaign_v_protocol_design_fire_masks.json`、`v_summary.json`（V 完了後） | `v_run.sh`（`run_campaign.py`、`v_predict.py`、`v_analysis.py`） | V | マクロ `V*`・`StatV`、`tab_prereg` |
| `l_summary.json`（L のマージと実行後） | `l_run.sh`（`l_analysis.py`） | L | マージ後に `paper_numbers.py`・`main.tex` に配線される（ブランチ上で確認済み） |
| `w_summary.json`（W のマージと実行後） | `w_render.sh`、`w_eval.sh`（`w_analysis.py`） | W | 未配線 |
| `test_count.json` | `count_tests.py`（Y） | — | マクロ `NTests` |
| `docs/paper/numbers.tex`、`tab_*.tex`（上記以外の `tab_prereg`、`tab_timing`） | `paper_numbers.py`（ホスト） | 全研究 | 本文・補足 |
| `fig_system.pdf`、`fig_lookaround.pdf`（`experiments/evidence/runs/`）、`fig_h_outcomes.pdf` ほか | `make_paper_figures.py`（Y。`build_paper.sh` が呼ぶ） | — | 本文・補足の図（`fig_h_case.pdf` は `make_memory_case_figure.py`、`fig_h_change_rate.pdf` は `h_change_rate_model.py`） |
| `figure_stats.json`、`docs/figures/*.png`（旧来の図） | `make_figures.py`（Y） | C/D ほか | README・説明資料 |
| README の結果ブロック／`docs/report/` の PDF | `update_readme_results.py`、`make_report.py --account tetsutetsu`（Y） | 全研究 | README・説明資料 |

論文が使う `\fig{}` は、本文が `fig_fire_size`、`fig_r_examples`、`fig_system`、`fig_lookaround`、`fig_h_change_rate`、補足が `fig_e_trajectories`、`fig_h_case`、`fig_h_outcomes`、`fig_risk_coverage`、`fig_t1_examples`（すべて `.pdf`）。`\input{tab_*}` は本文が `tab_h_arms`、`tab_t1_models`、`tab_z`、補足が `tab_dev_models`、`tab_e_strata`、`tab_h_sequences`、`tab_i13_dev`、`tab_prereg`、`tab_r`、`tab_t1_ablation`、`tab_timing`。

## 7. 計算量（Compute budget）

GPU は Tesla V100 32GB の 1 枚だけで、全研究が同じ 1 枚を専有して順に走った（並行実行なし）。閉ループの試行は VLM サーバを常駐させるため、**GPU 時間は実時間にほぼ等しい**（GPU 稼働率の測定値は無い）。以下の「実測」は台帳の `wall_s`（再試行を含む全試行の合計）、「推定」は結果ファイルの更新時刻や各スクリプトの見積りから求めた概算で、±30% 程度の誤差を見込む。

| 研究 | 内容 | 実時間・GPU 時間 | 区分 |
|---|---|---|---|
| C | 30 試行（v3.3） | 0.60 h（中央値 66 s／試行） | 実測 |
| D | 42 試行 | 1.19 h（102 s） | 実測 |
| E | 60 試行 | 1.74 h（104 s） | 実測 |
| F | 48 試行 | 1.32 h（99 s） | 実測 |
| G | 48 試行 | 1.39 h（103 s） | 実測 |
| H | 112 試行 | 3.53 h（111 s） | 実測 |
| J | 48 試行（2 モデル構成） | 41 行時点で 1.97 h。中央値は J001–006 が 137 s、以降 164 s（他処理による負荷あり。J の事前登録に注記）。完了後の合計は約 2.3 h | 41 行までは実測、残りは推定 |
| V | 予備走行 4 + 本番 160 試行 | 約 5 h（164 × 約 110 s ≈ 5.0 h）。設計時の火マスク描画は別 | 推定 |
| L（マージ後） | 試運転 3 + 本番 24 試行 | 約 0.8 h（27 × 約 105 s）。設計時の火マスク描画は別 | 推定 |
| 開発・予備走行・中止した台帳 | A/B（中止）、E/H の予備走行、F の試運転、I-14 の予備走行、回帰 | 合計 1.60 h | 実測 |
| 閉ループ合計（上記のうち実測分） | C〜H、J（41 行）、開発・予備走行 | 13.3 h | 実測 |
| T1 | 600 枚 × 6 構成のオフライン採点 | 約 4.5–5 h（`devset_t1_*` の更新時刻 21:34→01:49 に最初の構成の所要時間を足した値） | 推定 |
| T2 | 600 枚 × 7 構成（Clef 2 通り、4B、9B の 4 通り） | 約 2.5 h（更新時刻 05:58→08:07） | 推定 |
| R | 12 条件 × 300 枚 | 約 3.2 h（1 条件あたり約 14–15 分） | 推定 |
| P | 実写 400 枚 | 約 0.35 h（`p_sample.json` 11:32→`p_scores` 11:53） | 推定 |
| P2 | 800 枚 × 2 つの危険の問い方 | 約 1.4 h（P のスループットから外挿） | 推定 |
| Z | SigLIP・CLIP を T1・T2 の 1,200 枚で採点 | 0.2 h 未満 | 推定 |
| K | 保存済みスコアの解析（GPU なし） | 数分 | 推定 |
| W（マージ後） | 画像 675 枚の描画 約 2 h（`w_render.sh` のヘッダ）、採点 W-a 0.8 h + W-b 2.15 h（`w_eval.sh` のヘッダ）、任意の劣化段 1.6 h | 約 5 h（任意段を除く） | 推定（スクリプトの見積り） |

画像集合の Gazebo 描画（T1・T2・DH・DH2）と、各研究の設計時の火マスク描画は、開始時刻が記録されていないため所要時間を示さない。論文の全研究を最初から再現する場合の目安は、閉ループが約 19.5 h（C〜H、J、V、L の合計 17.9 h に開発・予備走行 1.6 h を加えた値）、オフライン採点が約 12.4 h（T1、T2、R、P、P2、Z）、W が約 5 h で、描画と解析を除いて合計約 37 h（約 1.5 日）。
