# Reproducing RescueMind from a clean machine

**日本語要約。** 第三者が Ubuntu 22.04 + NVIDIA GPU のマシンで、この研究を3段階で再現するための手順書です。
**段階1（GPU 不要、数分）**：`make verify-quick`（命題2の z3 による機械検査、約20秒）、`make verify`（差分検査と変異テストを含む完全版、約9分）、
`make numbers && make check`（論文・README・説明資料・YouTube 概要欄の数値を、コミット済みの結果ファイルから再生成して整合を確認、数秒）。
**段階2（GPU、画像単位、数時間）**：Docker イメージのビルド、固定リビジョンのモデル重みの取得、T1/T2/W/XD/S/Q/P/P2 などの画像単位の評価。
**段階3（閉ループ、Gazebo）**：1回のミッション、`scripts/run_campaign.py` によるキャンペーン、事前登録が結果より前であることの確認方法。
各コマンドは `--help`・ソース・Makefile で確認したものだけを載せています。**実際に実行して確認した範囲**と**書いただけで未実行の範囲**は §9 に分けて書きました。
これは `docs/REPRODUCIBILITY.md`（日本語、研究ごとの詳細表）を補う、英語の入口です。第三者ライセンスは `docs/THIRD_PARTY.md`。

This guide is written for someone who has never seen the repository. Every command below was read from the script's argparse, header or the
`Makefile`; nothing is invented. Section 9 lists exactly what was executed while writing this guide and what is documented but untested.
`docs/REPRODUCIBILITY.md` (Japanese) holds the per-study detail table; this file is the English entry point and adds the third-party and
verification notes.

```
make reproduce-help      # prints the three tiers below
```

| Tier | Needs | Time | What it reproduces |
|---|---|---|---|
| 1. No GPU | any Linux with Python 3.10+, git | 20 s to 9 min (+ unit tests) | Prop. 2 machine check; every number in paper/README/report/YouTube text from committed results; summaries of the offline analyses |
| 2. GPU, image level | Docker, NVIDIA driver + container toolkit, V100-class GPU, model weights | hours per study (table in 5) | the held-out image studies T1, T2, R, Z, K, P, P2, W, S, XD, Q |
| 3. Closed loop | tier 2 + free CPU cores, Gazebo in Docker | about 100 s per mission; 1 to 7 h per campaign | one live mission, campaigns D, E, F, G, H, J, L, V (and A, B, X) |

## 0. Reference hardware and software

The results in the repository were produced on one machine; GPU times in this guide are measured on it.

| Item | Value |
|---|---|
| OS | Ubuntu 22.04 (host); the containers are Ubuntu 24.04 + ROS 2 Jazzy + Gazebo Harmonic |
| GPU | 1 x Tesla V100 PCIe 32 GB (FP16 only: V100 has no BF16). Study J peaks at 28.0 GiB; everything else fits in less |
| CPU | 4 cores. The host is CPU-saturated during campaigns (load about 3.9), so nothing heavy may run beside them |
| Docker | `docker` group membership only; no sudo anywhere. NVIDIA container toolkit for `--gpus all` |
| Images | `rescuemind:jazzy-next` (standard, `STACK=next`: torch 2.8.0+cu126, transformers 5.20.0), `rescuemind:jazzy` (`STACK=v33`: torch 2.5.1, transformers 4.53.3; used for figures, PDFs, tests), `rescuemind:latex` (paper) |
| Host Python for tier 1 | 3.10.12 with `z3-solver==5.3.1`, `hypothesis==6.168.5`, `pytest` (`requirements-verify.txt`) |

## 1. External assets

Nothing below is stored in the repository except metadata (`docs/THIRD_PARTY.md` is the authoritative list with licence texts and obligations;
`git ls-files` contains no weights, dataset photographs, fonts or audio). The repository's own code is MIT (`LICENSE`).

| Asset | Used by | Licence | How to fetch | Where it goes |
|---|---|---|---|---|
| AWS RoboMaker Small Warehouse World (git `ee0af73...`, branch `ros2`) | depot worlds: studies XD, X (and I-21 previews) | **MIT-0** | `make assets` = `bash scripts/fetch_depot_assets.sh` (shallow clone, copies textures next to meshes, rewrites Windows texture paths) | `worlds/assets/aws-wh` (git-ignored); the commit is written to `worlds/assets/aws-wh/COMMIT` |
| D-Fire (Venancio et al., Neural Comput. Appl. 2022), test split via the HF mirror `badsaarow/d-fire` rev `27f81e6f7d32fe3b29d366da9573b6150a3d148f` | studies P, P2 | **CC0** (dataset authors' statement; individual web photographs are not separately cleared, so no D-Fire image is committed) | see 5.2 | `~/.cache/rescuemind/dfire/test-{0,1,2}.parquet` |
| Wikimedia Commons photographs (405 listed in `experiments/q_sample_final.json`) | study Q | CC0, CC BY, CC BY-SA, public domain (per-image licence, author and sha256 in the JSON; NC/ND/GFDL-only excluded) | `python3 scripts/q_fetch.py --all` (standard library only; 960 px thumbnails) | `~/.cache/rescuemind/q/images`. CC BY / BY-SA need attribution if you show an image anywhere |
| Warehouse negatives for XD-R (optional) | study XD stage `r` | per image, recorded by you in `manifest.jsonl` | collect your own fire-free photographs; format in the header of `scripts/xd_realphoto.py` | `~/.cache/rescuemind/warehouse_negatives/` |
| Model weights (Hugging Face) | all VLM studies | see below | 5.1 | `$HF_HOME` (default `~/.cache/huggingface`), mounted at `/hf`; runs use `HF_HUB_OFFLINE=1` |
| VOICEVOX engine + 四国めたん voice (narration of the video only) | `make video` | LGPL-3 engine; voice terms require the credit `VOICEVOX:四国めたん` | `docker run -d --name rm-voicevox -p 127.0.0.1:50021:50021 voicevox/voicevox_engine:cpu-latest` | not needed for any result in the paper |

Model weights (revisions are the Hugging Face commit hashes; the first four are enforced in code by `PINNED_REVISIONS` in
`rescuemind/local_vision.py`, the server refuses a different snapshot):

| Model id | Revision | Licence | Role |
|---|---|---|---|
| `Qwen/Qwen3.5-9B` | `c202236235762e1c871ad0ccb60c8ee5ba337b9a` | Apache-2.0 | submitted VLM (v3.6); every closed-loop study |
| `Qwen/Qwen3.5-4B` | `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` | Apache-2.0 | T1/T2 comparisons, second model in study J |
| `Qwen/Qwen3-VL-8B-Instruct` | `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b` | Apache-2.0 | T1 comparison, dev sets |
| `Qwen/Qwen2.5-VL-3B-Instruct` | `66285546d2b821cf421d4f5eb2576359d3770cd3` | **Qwen Research License (non-commercial)** | v3.3 stack and comparisons only |
| `Cloudflare/clef-flash` | `8b2e5fd17c09fd49bc2880b805d5323ec7ff4ff3` | Apache-2.0 | "Jev role" in J and T2 (`scripts/clef_server.py`) |
| `HuggingFaceTB/SmolVLM2-2.2B-Instruct` | `482adb537c021c86670beed01cd58990d01e72e4` | Apache-2.0 | v3.3 dual mode |
| `google/siglip-so400m-patch14-384` | `9fdffc58afc957d1a03a25b10dba0329ab15c2a3` | Apache-2.0 | study Z, Q baselines |
| `openai/clip-vit-large-patch14` | `32bd64288804d66eefd0ccbe215aa642df71cc41` | MIT (code/weights release; the HF card has no licence field) | study Z, Q baselines |

Study S also uses RapidOCR 1.4.4 (Apache-2.0) in a separate venv (`~/.cache/rescuemind/venv-ocr`, CPU only; `scripts/s_ocr_mask.py`).

## 2. Clone and orient

```bash
git clone <repository-url> rescue-mind && cd rescue-mind
make help                 # one line per target
make doctor               # reports missing docker / containers / images (safe, changes nothing)
```

The registered studies are `experiments/PREREGISTRATION_<ID>.md`; result files are in `experiments/results/`; the paper numbers are generated, never typed
(`docs/paper/numbers.tex`, `tab_*.tex`). `make study-<ID>` only **prints** the registered command sequence.

## 3. Tier 1: no GPU, minutes

```bash
python3 -m venv ~/rm-verify && . ~/rm-verify/bin/activate
pip install -r requirements-verify.txt          # z3-solver, hypothesis, pytest (about 10 s)
make verify-quick      # 114 z3 queries only, compared with experiments/results/smt_advice_proof.json
make verify            # + 9,000 model-vs-code differential cases, 11 code mutants, and 90 tests
```

Notes for a clean clone (found by the third-party-style run in `docs/REPRODUCTION_RECORD.md`):

* The Makefile calls plain `python3`, so the venv must be **activated** in the shell that runs `make` (otherwise the system `python3`, which normally lacks z3, is used).
* `NICE` is a Make variable that prefixes every command (default `nice -n 19`). To pin the run to one core on a busy host use
  `make verify NICE="nice -n 19 taskset -c 3"` (a single core gives about 9 min 13 s).
* The fresh result files go to `/tmp/rescuemind_smt_fresh.json` and `/tmp/rescuemind_smt_quick.json`; on a shared host, or if such a file is owned by another user, run `make verify SMT_TMP=$HOME/tmp` (the directory must exist).
* The checkout is left unmodified (`git status` was clean after the run).

```bash
make numbers           # scripts/paper_numbers.py -> docs/paper/numbers.tex, tab_*.tex
make check             # scripts/check_consistency.py: README, YouTube text, paper macros, report agree with experiments/results
make test              # python3 -m unittest discover -s tests -q (on the host if rm-dev is not running)
```

Measured on the reference host while another GPU job was running (`nice -n 19` is the Makefile default; load average 1.5 to 2.4):

| Command | Result | Wall time |
|---|---|---|
| `pip install -r requirements-verify.txt` into a fresh venv | z3-solver 5.3.1.0, hypothesis 6.168.5, pytest 9.1.1 | 11 s |
| `make verify-quick` | `queries 114 (committed 114), unsat 99, solver 18.0 s, z3 5.3.1`; `VERIFY_OK: every verdict equals the committed record` | 18 s |
| `make verify` | `114/114 checks as expected; mutants (model): plan=6/6, station=5/5, loop=2/2; 218.8 s`; differential `{'plan','station','p2','p2_noassert','credit','loop'}` x 1,500 = 9,000 cases; 11 code mutants all caught; `queries 114 ... unsat 99`; `VERIFY_OK`; pytest `90 passed in 305.97s` | 8 min 46 s |
| `make numbers` | `macros 393 tables [tab_dev_models.tex ... tab_z.tex]`; `git status` is clean afterwards (committed numbers are exactly regenerated) | 2.0 s |
| `nice -n 19 python3 scripts/check_consistency.py` (`make check`) | `0 mismatch(es), 0 skipped -- consistent` (a table of 20 facts across README, YouTube, macros and report; the report text needs `pdftotext`, else use `--no-report`) | 3.5 s |
| `python3 -m unittest discover -s tests -q` on the host | `Ran 1258 tests`, `FAILED (failures=2, skipped=2)` on the host (details below the table) | 6 min 2 s |

Unit tests on the host (no ROS, no GPU): 1,256 of 1,258 pass, 2 are skipped, 2 fail. The two failures, reported here rather than hidden:
`tests/test_no_personal_paths.py::test_tracked_text_files` fails because the tracked log `experiments/results/i22_gazebo_check.log` contains the original author's home directory
(4 occurrences; it came in with commit `1c04256`; the privacy test catches it, so it should be fixed in the repository before publication);
`tests/test_i23_smt_refinement.py::Mutants::test_differential_harness_kills_each_mutant` reported `caution_boundary_le survived the differential harness` in the full discovery run,
but the same class passes when run alone (`python3 -m unittest tests.test_i23_smt_refinement.Mutants`: 6 tests OK, 69 s) and inside `make verify`'s pytest (90 passed), i.e. it is order- or sampling-dependent (not investigated here).
Inside `rm-dev` (`make test`) the ROS-dependent tests run too; the figures above are for the host.

What `make verify` establishes: Proposition 2 (advice can only add checks and never removes one; the delivery interlock) is encoded in z3 (`unsat` = no
counterexample), the encoding is tied to the real code by differential testing, and 11 deliberately broken variants of the code are each caught
(they are `sat`, i.e. have a counterexample). The z3 version is recorded in the result file; a different solver version can change timings but not verdicts.

Re-running the offline analyses on the committed raw results (no GPU, each under 3 s): `k_conformal.py`, `t1_analysis.py`, `t2_analysis.py`,
`r_analysis.py`, `f_analysis.py`, `g_analysis.py`, `h_analysis.py`, `j_analysis.py`, `l_analysis.py`, `v_analysis.py`, `p2_calibration.py --analyse`.
Checked on the reference host: `k`, `t2`, `f`, `g`, `h`, `l`, `v`, `p2` rewrite byte-identical summaries. Three differences, none affecting a reported number:
`t1_analysis.py` changes one latency median in `t1_summary.json` in the last digit (0.828 vs 0.827 s, rounding); `r_analysis.py` writes `tab_r.tex` without the
one-line header comment that `make numbers` adds (run `make numbers` afterwards); `j_analysis.py` fills per-trial fields (`qwen_reason`, `jev_hazard`,
`jev_supply`) from `outputs/runs/<run_id>/`, which is git-ignored, so on a fresh clone those three per-trial fields become `null` (all counts and tests are unchanged).
If you try these, `git diff` shows it; `git checkout -- <file>` restores the committed version.

The registered protocols are regenerable from their seeds: `python3 scripts/make_protocol_{e,g,h,j}.py` rewrote the committed protocol JSON byte for byte
(checked; `make_protocol_f.py` needs arguments, see its `--help`).

## 4. Docker images and containers (needed for tiers 2 and 3)

```bash
# standard stack (ROS 2 Jazzy + Gazebo Harmonic + torch 2.8.0+cu126 + transformers 5.20.0)
RESCUEMIND_IMAGE=rescuemind:jazzy-next bash docker/build.sh        # = docker build -t ... docker  (STACK=next is the default build arg)
# old v3.3 stack: used for figures, PDFs and the tests in rm-dev
docker build --build-arg STACK=v33 -t rescuemind:jazzy docker
# paper (LaTeX): only for `make paper`
docker build -t rescuemind:latex docker/latex

# long-lived containers; the repo is mounted at the SAME absolute path, HF cache at /hf, host network, --cap-add SYS_NICE
RESCUEMIND_IMAGE=rescuemind:jazzy-next RESCUEMIND_CONTAINER=rm-next bash docker/run.sh sleep infinity   # GPU studies
RESCUEMIND_CONTAINER=rm-dev bash docker/run.sh sleep infinity                                          # tests, figures, analysis
docker exec rm-next rescuemind-entrypoint <command>     # the entrypoint sources ROS and the venv; always use it
```

`docker/run.sh` sets `ROS_DOMAIN_ID` (default 73), `GZ_PARTITION` (default `rescuemind_<uid>`), `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`, `GZ_IP=127.0.0.1`,
`HF_HUB_OFFLINE=1`. The build is several GB and about 15 to 30 min depending on bandwidth (not measured here). Build time is mostly apt and the torch wheel.
Do not publish the resulting image without adding the notices listed in `docs/THIRD_PARTY.md` section 6, item 7.

## 5. Tier 2: GPU, image level

### 5.1 Fetch the model weights once (needs the network, then offline)

```bash
# one model; repeat for each id and revision in the table of section 1
HF_HUB_OFFLINE=0 bash docker/run.sh python3 -c "from huggingface_hub import snapshot_download as s; s('Qwen/Qwen3.5-9B', revision='c202236235762e1c871ad0ccb60c8ee5ba337b9a')"
```

Minimum for the headline results: `Qwen/Qwen3.5-9B`. T1 needs also the 4B, Qwen3-VL-8B and Qwen2.5-VL-3B; J and T2 need Clef-Flash and the 4B; Z and Q need SigLIP and CLIP.
Check that your cache holds exactly the pinned snapshots (no GPU, runs in a second):

```bash
PYTHONPATH=. python3 - <<'E'
from pathlib import Path
from rescuemind.local_vision import PINNED_REVISIONS
for m, r in PINNED_REVISIONS.items():
    print(m, 'ok' if (Path.home()/'.cache/huggingface/hub'/('models--'+m.replace('/','--'))/'snapshots'/r).is_dir() else 'MISSING')
E
```

(On the reference host all four pinned and the four unpinned snapshots of section 1 are present at the revisions listed. The server also reports the snapshot it loaded
as `weights_revision` in every response; a mismatch for a pinned model raises `LocalInferenceError`.)

### 5.2 D-Fire for P and P2

Test split only (about 0.6 GB). The scripts glob `test-*.parquet` and the committed sample lists (`p_sample.json`, `p2_sample.json`) name the files `test-0/1/2.parquet`,
so the three mirror files are renamed in order. Their sizes match the files used here (322,659,305 / 152,327,072 / 140,802,920 bytes).

```bash
HF_HUB_OFFLINE=0 bash docker/run.sh python3 -c "from huggingface_hub import snapshot_download as s; s('badsaarow/d-fire', repo_type='dataset', revision='27f81e6f7d32fe3b29d366da9573b6150a3d148f', allow_patterns=['data/test-*'], local_dir='/tmp/dfire_dl')"
mkdir -p ~/.cache/rescuemind/dfire
i=0; for f in /tmp/dfire_dl/data/test-0000?-of-00003.parquet; do mv "$f" ~/.cache/rescuemind/dfire/test-$i.parquet; i=$((i+1)); done
python3 -m venv ~/.cache/rescuemind/pqvenv && ~/.cache/rescuemind/pqvenv/bin/pip install pyarrow Pillow   # the client needs pyarrow; the container lacks it
```

### 5.3 The studies

All of these are resumable (a finished result file is skipped) and re-run a stage once if an inference error occurs. Every GPU script first checks that its
`experiments/PREREGISTRATION_<ID>.md` is committed and unchanged (the W, XD, S, Q, A, B, X scripts abort otherwise). Nothing else may use port 8765 or the GPU.
**Warning:** `t1_eval_all.sh` and `t2_eval.sh` run `pkill -f local_vlm_server` (and `clef_server`) on entry, which kills any other VLM server on the host.

| Study | What | Command (from the repo root; `X` = `docker exec rm-next rescuemind-entrypoint`) | Expected GPU time | Output -> analysis |
|---|---|---|---|---|
| T1 | 600 unused images, 6 model/method configurations (images are committed in `experiments/vlm_testset_t1`) | `X bash scripts/t1_eval_all.sh` | 4.5 to 5 h (estimate from file times) | `devset_t1_*.json` -> `python3 scripts/t1_analysis.py` -> `t1_summary.json` |
| T2 | 600 unused images (`vlm_testset_t2`), Clef-Flash + 4B + four 9B variants | `X bash scripts/t2_eval.sh` | about 2.5 h (estimate) | `devset_t2_*.json`; the script ends with `t2_analysis.py` -> `t2_summary.json` |
| R | 12 camera degradations x 300 images | `X bash scripts/r_eval.sh` (stop: `scripts/stop_r.sh`) | about 3.2 h (estimate) | `devset_r_<cond>.json` -> `python3 scripts/r_analysis.py` -> `r_summary.json` |
| Z | zero-shot SigLIP/CLIP on T1+T2 | `X python3 scripts/zeroshot_baseline.py` | under 0.2 h | `z_scores_*.json`, `z_summary.json` |
| K | conformal thresholds from stored scores (no GPU) | `python3 scripts/k_conformal.py` | seconds | `k_summary.json` |
| P | v3.6 hazard question on 400 D-Fire photographs | start `scripts/local_vlm_server.py --model Qwen/Qwen3.5-9B --prompt-set v35 --hazard-prompt h36 --hazard-views tiles --hazard-threshold 0.05 --port 8765` in `rm-next`; then `~/.cache/rescuemind/pqvenv/bin/python scripts/p_realphoto_eval.py --data ~/.cache/rescuemind/dfire --sample` / `--run`; `python3 scripts/p_realphoto_eval.py --analyse` | about 0.35 h (measured from file times) | `p_scores_*.jsonl` -> `p_summary.json` |
| P2 | threshold calibration, 800 photographs, two wordings | `bash scripts/p2_eval.sh` (host; server in `rm-next`; `P2_PYTHON` = python with pyarrow) | about 1.4 h (extrapolated) | `p2_scores_{h35,h36}.jsonl` -> `p2_summary.json` |
| W | 675 hidden-fire images (225 worlds x 3 views) + comparison with the earlier method | render: `X bash scripts/w_render.sh`; score + analyse: `bash scripts/w_eval.sh` (`W_STAGES="a"` or `"b"`) | render about 2 h (Gazebo, GPU for rendering); score a 0.8 h, b 2.15 h | `w_summary.json` (not yet committed) |
| S | 276 text-in-image attack images, four server configurations | `X bash scripts/s_render.sh`; `bash scripts/s_eval.sh` (`S_STAGES="a".."d"`) | render about 1.2 h (Gazebo), score about 1.15 h GPU + 0.12 h CPU (OCR) | `s_summary.json` (not yet committed) |
| XD | 1,932 depot images (needs `make assets`) | `X bash scripts/xd_render.sh`, a person inspects `experiments/vlm_testset_xd/smoke/smoke_sheet.jpg` and creates `experiments/results/xd_smoke_ok`; `bash scripts/xd_eval.sh` (`XD_STAGES="a"` depot, `"r"` real photographs) | render about 4.1 h, score a 1.6 h, r 0.1 h | `xd_summary.json` (not yet committed) |
| Q | 405 Commons photographs: supply check, SigLIP/CLIP baselines | `python3 scripts/q_fetch.py --all`; `python3 scripts/q_contact_sheet.py` (a person audits labels, writes `q_exclusions.json`); `python3 scripts/q_eval.py --sample`; `bash scripts/q_run.sh` (server, `--run`, `--zeroshot`, `q_analysis.py`) | about 0.5 h | `q_summary.json` (not yet committed) |
| IF | intent-flip set, about 2 min | `bash scripts/if_run.sh` | 0.03 h | `if_summary.json` (not yet committed) |

`make study-T1`, `study-T2`, `study-R`, `study-P2`, `study-K`, `study-W`, `study-S`, `study-XD` print the same commands. Times marked "estimate" come from file modification
times or script headers, see `docs/REPRODUCIBILITY.md` section 7. The T1/T2 image sets, dev sets, labels and fire masks are committed, so no Gazebo render is needed for them;
W, S and XD images are rendered with Gazebo and are not in the repository.

## 6. Tier 3: closed loop in Gazebo

One stack at a time per ROS domain and Gazebo partition. A mission starts Gazebo headless, the ROS bridge, a velocity guard, the local VLM server (port 8765) and the mission
node, and writes `outputs/runs/<run_id>/` (git-ignored). Stop everything else first.

**Plan without side effects** (verified, prints the services and commands, starts nothing): add `--plan` instead of `--run`.

**One live mission** (the command of `docs/HANDOFF.md` section 3; about 100 s of wall time):

```bash
docker exec rm-next rescuemind-entrypoint python3 scripts/v32_orchestrate.py --run --scenario live --scene swapped \
  --model Qwen/Qwen3.5-9B --prompt-set v35 --intent-backend llm --intent-prompt i35 --recovery --explain --capture-rosbag \
  --instruction 'Bの避難所にペットボトルの水を運んで'
# optional: --hazard-at medicine | --lighting dim_evening | --distractor-at water | --film | --scene nominal|empty
```

The configuration `--model Qwen/Qwen3.5-9B --prompt-set v35 --intent-backend llm --intent-prompt i35 --recovery --explain` is v3.6; the other defaults
(hazard threshold 0.05, `h36` + `tiles`, look-around 0.4 m, asynchronous DDS) are in `v32_orchestrate.py --help`. To reproduce an older study use the
`stack_args` recorded in that study's ledger.

**A campaign** = a frozen protocol (JSON: trial list, seeds, worlds) + an append-only ledger (JSONL) + the command line `scripts/run_campaign.py --protocol P --ledger L [--only IDS] [--retries N] [--no-rosbag] -- <orchestrator flags>`.
Re-running the same command resumes at the first trial not yet in the ledger. Scene truth is used only for scoring, never passed to the mission or the VLM.
Example (study D, 42 trials, about 1.2 h):

```bash
docker exec rm-next rescuemind-entrypoint python3 scripts/run_campaign.py --protocol experiments/v34_protocol.json \
  --ledger experiments/results/campaign_D_ledger.jsonl -- \
  --model Qwen/Qwen3.5-9B --prompt-set v35 --intent-backend llm --intent-prompt i35 --recovery --explain
docker exec rm-next rescuemind-entrypoint python3 scripts/export_evidence.py experiments/results/campaign_D_ledger.jsonl   # per-run evidence incl. image hashes
```

| Study | Trials | Command (registered; also `make study-<ID>`) | Time | Analysis -> summary |
|---|---|---|---|---|
| D | 42 | as above | 1.2 h | ledger counts (no summary file) |
| E | 60 | `run_campaign.py --protocol experiments/campaign_e_protocol.json --ledger experiments/results/campaign_E_ledger.jsonl -- <v3.6 flags> --hazard-threshold 0.05` | 1.7 h | ledger counts |
| F | 48 paired | `run_campaign.py --protocol experiments/campaign_f_protocol.json --ledger .../campaign_F_ledger.jsonl`; `fire_mask_at_pose.py --protocol ... --ledger ...` | 1.4 h | `python3 scripts/f_analysis.py` -> `f_summary.json` |
| G | 48 paired | `run_campaign.py --protocol experiments/campaign_g_protocol.json --ledger .../campaign_G_ledger.jsonl` | 1.4 h | `g_analysis.py` -> `g_summary.json` |
| H | 112 | `run_campaign.py --protocol experiments/campaign_h_protocol.json --ledger .../campaign_H_ledger.jsonl` | 3.5 h | `h_analysis.py`, `h_change_rate_model.py` -> `h_summary.json`, `h_change_rate.json` |
| J | 48 paired, two models (28 GiB) | `run_campaign.py --protocol experiments/campaign_j_protocol.json --ledger .../campaign_J_ledger.jsonl`; log VRAM with `nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -l 1 > experiments/results/campaign_J_vram.csv` | 2 to 2.5 h | `j_analysis.py` -> `j_summary.json` |
| V | 160 (+4 pilot) | `bash scripts/v_run.sh` (pilot, design masks, **predictions committed and pushed before the first trial; the script stops for it**, campaign, analysis). It runs `git commit` and `git push` itself: on a clone without push rights, commit the predictions locally and edit the `git push` step | 5 h | `v_analysis.py` -> `v_summary.json` |
| L | 24 (+3 smoke) | `bash scripts/l_run.sh` | 0.8 h | `l_analysis.py` -> `l_summary.json` |
| A / B / X | 226 / 48 / 80 | `bash scripts/a_run.sh` / `b_run.sh` / `x_run.sh` (X needs `make assets`; `X_PARTS="a m"` for the core 44) | A about 11.5 h, B 1.3 h, X about 5.5 h | results not committed at this revision |

Each of the `*_run.sh` scripts is a full registered sequence (mechanics pilot that stops the script unless it behaves as designed, design-time fire masks, campaign, analysis) and
prints `*_DONE` or `*_ABORT`.

**Audit of a campaign.** Ledger rows carry `run_id`, `state`, `image_sha256`, `models`, `stack_args` (and `advice_audit`, `interlock_audit` where relevant); the analysis scripts
recompute every reported count from the ledger, never from a hand-typed number. To check a run's evidence image:
`sha256sum experiments/results/evidence/<run_id>/checkpoint.jpg` must equal `image_sha256` in the same directory's `mission.json` (checked for one run: equal).
`scripts/audit_robot_run.py` (needs `PYTHONPATH=.`) is a log-completeness check for the v3.2 mission record; it does **not** apply to current v3.6 records and is not a physical-motion proof.
Safety monotonicity of mission memory and advice is recomputed by the audit code in `rescuemind/mission_memory.py` / `rescuemind/advice*.py` (tests `tests/test_i15_memory.py`, `tests/test_i23_smt_refinement.py`).

### Does a registration predate its results?

Registrations are git-committed Markdown files; the first result file of the same study is committed later. Three ways to check:

```bash
# 1. the paper's audit table, regenerated from git history (also: make numbers)
python3 scripts/paper_numbers.py && cat docs/paper/tab_prereg.tex     # columns: registration commit, first-results commit, amendments, order
grep -E 'NStudies|PreregOrderOK|PreregDrafts' docs/paper/numbers.tex   # 23 studies; 15 checked; order "holds"; drafts listed
# 2. by hand for one study (G): original registration vs first results
R=$(git log --diff-filter=A --format=%h -- experiments/PREREGISTRATION_G.md | tail -1)
L=$(git log --diff-filter=A --format=%h -- experiments/results/campaign_G_ledger.jsonl | tail -1)
git merge-base --is-ancestor $R $L && echo "registration predates results"
# 3. the amendments after registration are inside the Markdown ("**Amendment n**") and in git log -- experiments/PREREGISTRATION_G.md
```

Run on the reference clone: G was registered at `edb26a1` (2026-10-17 06:14 +0900), first results at `f6160fb` (09:31), `merge-base --is-ancestor` true and the reverse false.
The paper's table uses the registration text in force when the first results were committed (including amendments, e.g. `0816e36` for G), and reports 15 of 23 studies as checked;
the others are drafts or without results yet (`A, S, X, XD, Q, B, IF` at this revision), and study C (the first evaluation) was registered and run in one commit, so its order is unverifiable.
Limits: git history proves order only if you trust the history. To rule out a rewritten history, timestamp the commit hash externally (for example with OpenTimestamps).
For study V, the model predictions were committed before the first trial (`experiments/results/v_predictions.json`, committed by `v_run.sh`'s gate).

## 7. Known pitfalls (from `docs/HANDOFF.md` section 4, plus ones found while writing this)

* **`nice` and `LD_LIBRARY_PATH`.** `nice` carries a file capability in the image, so its child runs in glibc secure mode and loses `LD_LIBRARY_PATH`. Put `nice` outside the shell that sources ROS
  (`nice -n 19 bash -c 'source /opt/ros/jazzy/setup.bash; ...'`, never `bash -c 'source ...; nice ...'`); in shell scripts use `renice -n N -p $$`. The Makefile therefore uses `nice` only on host commands, not inside containers (test: `tests/test_v34_priority_wrapping.py`).
* **Image topics use Reliable QoS** (`rescuemind/ros_qos.py`). Best Effort drops most 0.9 MB camera frames.
* **One stack per ROS domain and Gazebo partition.** Two stacks with the same `ROS_DOMAIN_ID`/`GZ_PARTITION` (defaults 73 / `rescuemind_<uid>`) and port 8765 interfere. To run two independent stacks give each its own
  `ROS_DOMAIN_ID=<n> GZ_PARTITION=<name> RESCUEMIND_CONTAINER=<name>` when starting its container (`docker/run.sh` forwards both) and its own VLM port; do not share an output ledger.
  They also share the single GPU and 4 cores, so concurrent campaigns slow each other and invalidate wall-time comparisons.
* **Quiet host.** The 4 cores are saturated by one stack. No video rendering, speech synthesis or builds during a campaign, and no edits to `rescuemind/` or `scripts/` (every trial re-reads the files).
* **`pkill -f <pattern>` inside `bash -c '...<pattern>...'` kills its own shell** (exit 143); put it in a script file. `t1_eval_all.sh`/`t2_eval.sh` kill every `local_vlm_server` on the host.
* **After restarting the server an old one may still answer**: wait for `curl -s http://127.0.0.1:8765/health` to fail before starting the next.
* **ROS `setup.bash` and `set -u`**: use `set +u; source ...; set -u`.
* **Qwen3.5 thinks by default**; the server sets `enable_thinking=False`. FP16 non-finite logits are treated as refusal to decide.
* **Offline weights**: runs use `HF_HUB_OFFLINE=1`; fetch with `HF_HUB_OFFLINE=0` once.
* **`python3 scripts/paper_numbers.py --help` and other scripts without argparse run the script** (it rewrote nothing here because the output was already current). Use `make numbers` deliberately, and `git status` afterwards.
* Gazebo needs a display or headless rendering (`--gz-mode auto` picks headless without `DISPLAY`); sign textures (study S) need the Noto CJK fonts of the container and absolute SDF paths, so render and load in the same container.
* The video is under 3 minutes by design; it is not needed for any result.

## 8. Claim -> command -> result file

Values are those printed by `make check` at this revision. "Offline" means it runs without GPU on the committed files; "Regenerate" is the expensive command that produces the raw result.

| Claim | Value | Offline command (committed raw -> summary) | Regenerate from scratch | Result file(s) |
|---|---|---|---|---|
| Prop. 2 holds on the implementation | 99 unsat of 114 queries, 9,000 differential cases, 11 mutants caught | `make verify` (or `verify-quick`) | same | `experiments/results/smt_advice_proof.json` |
| D: 42/42 correct | 42/42 | `make numbers` (macros `D*`) | study D (section 6) | `campaign_D_ledger.jsonl` |
| E: unseen random worlds | 60/60, 0 wrong deliveries | `make numbers` | study E | `campaign_E_ledger.jsonl` |
| T1: false approvals of the v3.4 rule | 5/408 (registered "<2%" claim fails) | `t1_analysis.py` | `t1_eval_all.sh` | `t1_summary.json`, `devset_t1_*.json` |
| T2: v3.5 false approvals | 0/407 (ceiling; improvement not measurable) | `t2_analysis.py` | `t2_eval.sh` | `t2_summary.json`, `devset_t2_*.json` |
| R: 12 camera degradations | pooled false approvals 0/2304 | `r_analysis.py` | `r_eval.sh` | `r_summary.json`, `docs/paper/tab_r.tex` |
| Z: zero-shot baselines are worse | SigLIP 44/408 false approvals on T1 | `zeroshot_baseline.py` (scores stored) | same (GPU) | `z_summary.json`, `docs/paper/tab_z.tex` |
| K: tau_h = 0.05 within the conformal guarantee on T2 | | `k_conformal.py` | same | `k_summary.json` |
| G: side views | deliveries despite visible fire 11/16 -> 1/16 (p=0.002), 0/8 false stops | `g_analysis.py` | study G | `g_summary.json`, `campaign_G_ledger.jsonl` |
| H: verified mission memory | unsafe deliveries 20/32 naive, 0/32 verified, 1/32 no memory; median 114 -> 79 s | `h_analysis.py`, `h_change_rate_model.py` | study H | `h_summary.json`, `h_change_rate.json` |
| V: H's model predicts closed-loop behaviour | prediction holds (time saving 14.9 s inside the registered 11.3 to 20.1 s); the memory-safety claim **fails** (V4, McNemar p=0.0625) | `v_analysis.py` | `v_run.sh` | `v_summary.json`, `v_predictions.json` |
| L: unseen station layouts | 24/24, 0 unsafe | `l_analysis.py` | `l_run.sh` | `l_summary.json` |
| J: two-model check | 23/24 as expected; v3.6 alone 24/24; claim not supported, second checker not adopted; peak 28.0 GiB | `j_analysis.py` (per-trial detail fields need `outputs/runs`) | study J | `j_summary.json`, `campaign_J_vram.csv` |
| P: real photographs | recall 298/300, false alarms 64/100 | `p_realphoto_eval.py --analyse` | section 5.3 P | `p_summary.json`, `p_scores_*.jsonl` |
| P2: calibrated threshold | recall 282/300, false alarms 18/100 | `p2_calibration.py --analyse` | `p2_eval.sh` | `p2_summary.json` |
| I-24: advice credit (descriptive model, k=4) | liar 1533 -> 59 s; flooding 33 -> 5 | `advice_credit_horizon.py` | same | `advice_credit_horizon.json`, `advice_curve.json` |
| Study A protocol size | 226 closed-loop runs | `make numbers` | `a_run.sh` | `experiments/campaign_a_protocol.json`; results not committed |
| Test functions | 1258 (static AST count) | `python3 scripts/count_tests.py` | same | `test_count.json` |
| W, S, X, XD, Q, B, IF | registered; no results at this revision | none | section 5.3 / 6 | (absent; the README says "running" or "awaiting") |
| README / YouTube / paper / report agree | 0 mismatches | `make check` | `make all-docs` (needs rm-dev, rescuemind:latex) | `README.md`, `docs/YOUTUBE_DESCRIPTION.md`, `docs/paper/`, `docs/report/` |

Full file-to-script-to-paper map: `docs/REPRODUCIBILITY.md` section 6. Compute budget of the whole project: section 7 there (closed loop about 19.5 h; offline scoring T1, T2, R, P, P2, Z about 12.4 h; W about 5 h; on one V100).

## 9. What was verified, and what was not

Executed on the reference host (CPU only, `nice -n 19`, while other GPU jobs were running; no Docker build, no Gazebo, no GPU):

* tier 1 in full: fresh-venv install of `requirements-verify.txt`, `make verify` (all three steps), `make verify-quick`, `make numbers`, `check_consistency.py`, the unit tests on the host (1,258 run; 2 failures, see section 3);
* the offline analyses `k, t1, t2, r, f, g, h, j, l, v, p2` on committed results and the `make_protocol_{e,g,h,j}.py` regeneration (differences listed in section 3);
* `v32_orchestrate.py --plan` for the live-mission command (argument names accepted; prints the process list; starts nothing);
* the registration-order check for G (`git merge-base --is-ancestor`) and the regeneration of `tab_prereg.tex`;
* the SHA-256 check of one committed evidence image;
* that the eight model snapshots in the reference cache equal the revisions in section 1, and that the D-Fire mirror's file sizes equal the cached files (so the rename in 5.2 is right);
* the `make reproduce-help` and `make verify-quick` targets.

Documented but **not run** here (the host was busy with GPU evaluation; each command was taken from the script's argparse or header, or from `docs/HANDOFF.md`):

* the Docker builds, container start-up and `docker exec` forms (the container and image names follow `docker/run.sh` and the Makefile);
* every GPU image study of section 5.3 and every live mission or campaign of section 6, including their times (times are the project's measured or estimated figures, labelled as such);
* `make assets`, the `snapshot_download` of D-Fire and of the models with pinned revisions (offline loading of a revision-pinned download was not exercised; if a loader cannot resolve `main` offline, set
  `$HF_HOME/hub/models--<org>--<name>/refs/main` to the pinned hash), `q_fetch.py` (network), the OCR venv of study S;
* `make test` in `rm-dev`, `make figures`, `make paper`, `make report`, `make video` (need the containers, LaTeX image, VOICEVOX).

If something in a tier does not reproduce, the first suspects are: a different solver or library version (tier 1), a snapshot that differs from the pinned revision (tier 2), and a second stack sharing the ROS domain, the GPU or the CPU (tier 3).

## 公開していない生成データ（作り直し方、I-168）

容量が大きく、公開した手順から作り直せるデータは Git に入れていない（`.gitignore`）。結果ファイル（`experiments/results/*_summary.json`、全試行の台帳、各モデルの採点結果）はすべて公開している。

| 公開していないもの | 大きさ | 作り直し方 |
|---|---|---|
| `experiments/results/ij_features.npz`（IJ の隠れ層の特徴量） | 46 MB | `bash scripts/ij_run.sh` の中の `scripts/ij_extract.py`（GPU、約 10 分） |
| `experiments/vlm_testset_{ji,s,s_ocrmask,w,xd}/`、`worlds/testset_{ji,s,xd}/`（画像レベルの評価用の画像とワールド） | 約 400 MB | 各研究の登録文書 `experiments/PREREGISTRATION_<研究>.md` に書いた生成スクリプト（ワールドはシードから決定的に作られる） |
| `outputs/qi/`、`outputs/qj/`（画像生成モデルで作った画像） | 約 100 MB | `scripts/qi_run.sh`、`scripts/qj_run.sh`（画像ごとの採点結果は公開済み） |
| `outputs/runs/`、`outputs/video/`（各走行の記録と動画） | 数十 GB | 台帳の各行の設定でその走行を再実行する（`scripts/run_campaign.py`） |

