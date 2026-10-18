# Third-party components, licences and obligations

Checked 2026-10-17 against the sources named in each row (URLs are the pages actually read). The repository's own code is MIT (`LICENSE`);
that licence covers only code and text written for this project. Nothing below is re-licensed by it.

Short version (日本語要約)：リポジトリには第三者のモデル重み・データセット画像・Commons 画像・音声・フォントを**同梱していない**
（すべて取得スクリプトまたは各自のインストールで入手）。同梱している画像はすべて Gazebo の描画（AWS の MIT-0 モデルを含む）か自作の図。
義務があるのは **VOICEVOX のクレジット表記**（動画の概要欄と最終カードに記載済み）、**Commons 画像（CC BY / BY-SA）の帰属表示**
（画像を図に載せる場合のみ。現在は載せていない）、**Qwen2.5-VL-3B は非商用限定**（Qwen Research License）の3点。

Usage categories: **runtime** = needed to run the system; **eval** = used only to produce reported results;
**fetched** = downloaded by a script or the Docker build, not stored in this repository; **redistributed** = a copy is stored in this repository.
No third-party model weight, dataset image, font file, audio file or video is redistributed (verified: `git ls-files` contains no
`.safetensors/.onnx/.pt/.parquet/.ttf/.ttc/.otf/.wav/.mp3/.mp4`; images under `experiments/` and `docs/` are Gazebo renders or our own figures).

## 1. Models

| Component | Version / revision (HF commit) | Licence | Source checked | Use | Obligations |
|---|---|---|---|---|---|
| Qwen3.5-9B | `c202236235762e1c871ad0ccb60c8ee5ba337b9a` (2026-03-02) | Apache-2.0 | https://huggingface.co/Qwen/Qwen3.5-9B (card + API `license: apache-2.0`) | runtime (submitted VLM, local vLLM, V100 FP16); fetched | Keep the Apache-2.0 notice if weights are redistributed (they are not). Citation requested by the card ("Qwen3.5: Towards Native Multimodal Agents", Qwen Team 2026) |
| Qwen3.5-4B | `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` | Apache-2.0 | https://huggingface.co/Qwen/Qwen3.5-4B | eval (studies E/F/J, model comparison); fetched | as above |
| Qwen2.5-VL-3B-Instruct | `66285546d2b821cf421d4f5eb2576359d3770cd3` | **Qwen RESEARCH LICENSE AGREEMENT** (`license_name: qwen-research`, release 2024-09-19) | https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct/blob/main/LICENSE | eval only (v3.3 stack, comparison tables); the v3.3 orchestrator (`scripts/v32_orchestrate.py`) still names it as its default; fetched | **Non-commercial (research/evaluation) use only**; commercial use needs a licence from Alibaba Cloud (§2). If weights or derivatives are redistributed: ship the agreement, mark changes, keep the notice "Qwen is licensed under the Qwen RESEARCH LICENSE AGREEMENT, Copyright (c) Alibaba Cloud. All Rights Reserved." (§3). §4b: display "Built with Qwen" / "Improved using Qwen" if outputs are used to train a distributed model (not done). Chinese law, Hangzhou courts (§8) |
| Qwen3-VL-8B-Instruct | `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b` | Apache-2.0 | https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct | eval (model comparison, devsets); fetched | Apache-2.0 notice on redistribution (none) |
| SmolVLM2-2.2B-Instruct | `482adb537c021c86670beed01cd58990d01e72e4` | Apache-2.0 (built on SmolLM2 + SigLIP encoder) | https://huggingface.co/HuggingFaceTB/SmolVLM2-2.2B-Instruct | eval / v3.3 "dual" mode; fetched | Apache-2.0 notice on redistribution (none). Card says "not intended for high-stakes scenarios or critical decision-making" (an intended-use statement, not a licence term; this project is a simulation study) |
| Cloudflare Clef-Flash | `8b2e5fd17c09fd49bc2880b805d5323ec7ff4ff3` (2026-10-09); fine-tune of Qwen3.5-9B | Apache-2.0 (card `license: apache-2.0`, `base_model: Qwen/Qwen3.5-9B`, `base_model_relation: finetune`; repo has a `LICENSE` file) | https://huggingface.co/Cloudflare/clef-flash | eval only (the "Jev role" / two-AI configuration, studies J and the Clef rows); fetched; custom code (`joint_schema_model.py`) is run locally with `trust_remote_code`-style loading, so review it before running | Apache-2.0 notice on redistribution (none). Not an endorsement by Cloudflare: do not use the name beyond naming the model |
| SigLIP so400m-patch14-384 | `9fdffc58afc957d1a03a25b10dba0329ab15c2a3` | Apache-2.0 | https://huggingface.co/google/siglip-so400m-patch14-384 | eval only (study Z, zero-shot baseline); fetched | Apache-2.0 notice on redistribution (none) |
| CLIP ViT-L/14 | `32bd64288804d66eefd0ccbe215aa642df71cc41` | MIT for the OpenAI CLIP code and weights release (https://github.com/openai/CLIP/blob/main/LICENSE); the Hugging Face card carries **no licence field** | https://huggingface.co/openai/clip-vit-large-patch14 (+ GitHub LICENSE) | eval only (study Z); fetched | MIT notice on redistribution (none). The card states "any deployed use case of the model - whether commercial or not - is currently out of scope" and restricts surveillance / face recognition: we use it only as a research baseline |
| RapidOCR 1.4.4 + PP-OCRv4 text-detection model (`ch_PP-OCRv4_det_infer.onnx`, 4.7 MB) | `rapidocr-onnxruntime==1.4.4` (PyPI) in a venv outside the repo | Apache-2.0 (RapidOCR; models are ONNX conversions of PaddleOCR's Apache-2.0 PP-OCRv4) | https://github.com/RapidAI/RapidOCR/blob/main/LICENSE ; https://github.com/PaddlePaddle/PaddleOCR (Apache-2.0) | eval only (study S defence arm OCR-MASK, `scripts/s_ocr_mask.py`); fetched via pip; no weights in the repo | Apache-2.0 notice on redistribution (none) |
| Qwen3.8-Omni-Flash / Jev (TypeSafe) cloud API clients | n/a (code only: `rescuemind/qwen35.py` optional branch, `rescuemind/jev.py`) | external service terms (DashScope / TypeSafe System One) | n/a | legacy path from the earlier course stage, not used by the submitted v3.6 results; requires the user's own API key (none in the repo, checked with a secret-pattern grep) | Service terms apply only if someone runs those paths |

vLLM (Apache-2.0, https://github.com/vllm-project/vllm) serves Qwen3.5 locally; it is installed by the user and not pinned in the repo.

## 2. Software stack

| Component | Version | Licence | Source checked | Use | Obligations |
|---|---|---|---|---|---|
| ROS 2 Jazzy (`ros:jazzy-ros-base`, `rclpy`, rosbag2, mcap storage) | Jazzy Jalisco, apt | Apache-2.0 | https://github.com/ros2/rclpy (LICENSE: Apache-2.0) | runtime; fetched (Docker base image) | None for use. A published Docker image would redistribute it: keep its notices |
| Gazebo Harmonic (`gz-sim` 8, `ros-jazzy-ros-gz`) | Harmonic / gz-sim8 | Apache-2.0 | https://github.com/gazebosim/gz-sim ; https://github.com/gazebosim/ros_gz | runtime; fetched (apt) | as above |
| PyTorch + torchvision | 2.8.0 / 0.23.0 (cu126 wheels; v3.3 stack: 2.5.1 / 0.20.1) | BSD-3-Clause-style (`LICENSE` "From PyTorch: Copyright ... Facebook"); PyPI metadata of recent wheels lists a composite SPDX expression | https://github.com/pytorch/pytorch/blob/main/LICENSE ; https://pypi.org/project/torch/ | runtime; fetched (Docker build) | The CUDA wheels pull NVIDIA runtime libraries under NVIDIA's own licence; fetched at build time, not redistributed |
| Transformers / accelerate / huggingface_hub / safetensors | 5.20.0 (v3.3: 4.53.3) / >=1.10 (1.9.0) / >=1.31 (0.33.4) / >=0.4 | Apache-2.0 | https://github.com/huggingface/transformers ; PyPI pages | runtime / eval; fetched | None for use |
| scikit-learn, Pillow, PyYAML, matplotlib, opencv-python-headless, sentence-transformers | scikit-learn>=1.3,<2 (BSD-3-Clause); Pillow>=9 (MIT-CMU/HPND); PyYAML>=6,<7 (MIT); matplotlib>=3.8 (PSF-based matplotlib licence); opencv-python-headless>=4.9 (Apache-2.0); sentence-transformers (Apache-2.0) | as listed | PyPI metadata, checked 2026-10-17 | runtime / eval / figures; fetched | None for use |
| num2words | >=0.5 | **LGPL** | https://pypi.org/project/num2words/ | runtime (Qwen 3.x processor dependency); fetched by pip, not vendored | Using it as an installed library imposes nothing on this repo; do not copy its source into the repo |
| reportlab | >=4.0 (PyPI latest 5.0.1) | BSD | https://pypi.org/project/reportlab/ (`License :: OSI Approved :: BSD License`) | builds the explanatory PDF (`scripts/make_report.py`); fetched | None for use |
| FFmpeg (apt, 4.4.2 on the build host), Xvfb, Mesa | distro packages | LGPL/GPL (FFmpeg build configuration dependent) | distro package metadata | video assembly and headless rendering; fetched | We run them as tools and do not redistribute them or link them into our code |
| TeX Live (`texlive/texlive:latest-medium`), IEEEtran class | Docker image | LPPL (IEEEtran) / TeX Live licences | `docker/latex/Dockerfile` | paper build only; fetched | None for the paper PDF. The IEEEtran template is IEEE's; do not alter its formatting |
| AWS RoboMaker Small Warehouse World | git `ee0af733315e78432408c3cd98d378ecee5f767c` (branch `ros2`) | **MIT-0** (MIT No Attribution; `LICENSE` read in the checkout) | https://github.com/aws-robotics/aws-robomaker-small-warehouse-world ; `scripts/fetch_depot_assets.sh` | runtime for the depot worlds (studies XD, X, I-21); **fetched** into the git-ignored `worlds/assets/aws-wh`, not committed. The fetch script edits DAE texture paths and the loader drops an invalid inertia value in the copy only | No attribution or notice required. Renders containing its meshes (`docs/figures/depot_preview_*.jpg`, depot frames in the video) are redistributable |
| Generated fire / smoke assets (`worlds/assets/generated/flame_*.obj`, `flame_sprite_*.png`, `smoke_particle.png`) | produced by `rescuemind/depot.py` from a seed | project's own (MIT), no third-party texture or mesh | `rescuemind/depot.py` | runtime; git-ignored | None |

## 3. Fonts

| Component | Licence | Source checked | Use | Obligations |
|---|---|---|---|---|
| Noto Sans CJK (`fonts-noto-cjk`, `/usr/share/fonts/opentype/noto/NotoSansCJK-{Regular,Bold}.ttc`) | SIL Open Font License 1.1 | https://github.com/googlefonts/noto-cjk (`Sans/LICENSE`) | burned into the video overlay and figures by `scripts/make_demo_video.py`; fetched (apt) | Fonts may be embedded in documents and rendered video; the font files themselves are not in the repo. If ever redistributed, ship the OFL text and do not sell the font alone |
| IPAex Gothic / Mincho (`fonts-ipaexfont`, `ipaexg.ttf`, `ipaexm.ttf`) | IPA Font License v1.0 | https://moji.or.jp/ipafont/license/ | subset-embedded in the explanatory PDF by reportlab (`scripts/make_report.py`); fetched (apt) | Redistribution of an unmodified font requires the original name and a copy of the licence; modified fonts must not use the name. Embedding glyph subsets in a PDF is the ordinary document use; the font files are not in the repo |

## 4. Datasets and images

### D-Fire (study P and P2) — fetched, not redistributed
* Source: D-Fire, Venâncio, Lisboa, Barbosa, *Neural Computing and Applications* 2022 (cite if you use it). Original repository https://github.com/gaiasd/DFireDataset (commit `4bf9c31b18fadcd44d5f0b6d66f82bc56fa5e328`, 2025-12-31).
* Licence as stated by the authors in that repository's `LICENSE`: "a collection of images in the public domain which we do not have copyrights over ... the image collection is the result of our work and will be made available to the public domain under the Creative Commons Zero v1.0 Universal license". **So CC0 applies to the collection; the authors give no warranty about rights in individual web-scraped photographs.** GitHub's licence detector reports "NOASSERTION".
* We used the public test split through the Hugging Face mirror `badsaarow/d-fire` (revision `27f81e6f7d32fe3b29d366da9573b6150a3d148f`). The mirror's card has **no licence field**; cite the original repository, not the mirror, for the licence.
* In this repository: only sample lists (file names, parquet row numbers, categories: `experiments/results/p_sample.json`, `p2_sample.json`) and per-image scores/summaries. **No D-Fire image, crop, or thumbnail is committed** (the only scripts that read the cache are `scripts/p_realphoto_eval.py` and `scripts/p2_calibration.py`; neither writes images). Images stay in `~/.cache/rescuemind/dfire`.
* Obligation: citation; do not add photographs to figures or the repo without checking each image's origin.

### Wikimedia Commons photographs (study Q; branch `worktree-agent-ac893207bdda069d9`, not yet on this branch) — fetched, not redistributed
* `experiments/q_sample_final.json` lists 405 photographs with title, file-page URL, thumbnail URL, licence, author/credit string, sha256, byte size and class. Licence policy fixed before download (`scripts/q_fetch.py`): CC0, CC BY, CC BY-SA, public-domain marks; NC / ND / GFDL-only / unknown excluded.
* Counts by licence (405 total; 335 distinct author strings; 381 have a licence URL, the 24 public-domain entries have none):

  | Licence | n | | Licence | n |
  |---|---|---|---|---|
  | CC BY-SA 4.0 | 153 | | CC BY 2.0 | 42 |
  | CC BY-SA 3.0 | 78 | | CC0 | 40 |
  | CC BY 4.0 | 46 | | Public domain | 24 |
  | CC BY-SA 2.0 | 12 | | CC BY 3.0 | 4 |
  | CC BY 2.5 | 3 | | CC BY-SA 2.5 | 2 |
  | CC BY-SA 2.0 de | 1 | | | |

  Grouped: CC BY-SA 246, CC BY 95, CC0 40, public domain 24. Classes: water 139, medicine 116, neither 150.
* **The images are not redistributed**: the repository holds only the metadata/URLs above (and scores). Images and contact sheets live in `~/.cache/rescuemind/q` outside the repository.
* Obligations: CC BY / CC BY-SA require attribution (title, author, licence, link: already in the JSON) *if an image is shown*; CC BY-SA also requires the same licence for adaptations (a cropped/annotated thumbnail in a figure would be an adaptation). Committing the metadata file satisfies the attribution record; **before putting any Commons image into a paper figure, README or video, add the credit line per image and keep BY-SA figures separable from the MIT code**. Metadata itself (titles, author names) is factual and kept as published on Commons.

### Wikimedia Commons photographs (study XD-R, fire-free warehouse photographs) — fetched, not redistributed
* Purpose: false-alarm test of the deployed hazard question on real photographs of warehouses, shelves, stock rooms, loading docks and pallets with no fire, smoke or flame (`scripts/xd_realphoto.py`, `experiments/PREREGISTRATION_XD.md` part XD-R). Collected by `scripts/xd_fetch.py` through the Wikimedia Commons API (descriptive User-Agent, polite rate limit) with the study-Q licence policy: CC0, CC BY, CC BY-SA and public-domain marks only, restricted further to the versions `xd_realphoto.py` registers (CC BY / BY-SA 3.0 and 4.0, unported); NC / ND / GFDL-only / unknown excluded. Images are the 960-px Commons thumbnails, as in study Q.
* `experiments/xd_real_candidates.json` (394 candidates, title, file-page URL, thumbnail URL, licence, author/credit string, sha256, byte size, kind), `experiments/xd_real_exclusions.json` (136 excluded with reason) and `experiments/xd_real_manifest.jsonl` (258 kept; the manifest that `xd_realphoto.py` reads) hold the attribution record. One kept file has no author string on its Commons page (attribution by file-page URL).
* Counts of the 258 kept by licence: CC BY-SA 4.0 127, CC BY-SA 3.0 51, public domain 40, CC0 17, CC BY 4.0 13, CC BY 3.0 10 (grouped: CC BY-SA 178, CC BY 23, public domain 40, CC0 17); 193 distinct author strings.
* **The images are not redistributed**: they live in `~/.cache/rescuemind/warehouse_negatives` (kept) and `~/.cache/rescuemind/xd_real` (candidates, contact sheets, excluded), outside the repository. Obligations as for study Q: the metadata above is the attribution record; add a per-image credit line (title, author, licence, link) before showing any of them in a figure, README or video, and keep BY-SA material separable from the MIT code.

### Rendered and self-made images
`experiments/vlm_devset*`, `vlm_testset_t1/t2`, evidence runs, `docs/figures/*`, `docs/report/figures/*`, `fixtures/*.jpg`, `docs/paper/fig_*.pdf` are Gazebo renders (some contain the MIT-0 AWS models) or plots/schematics written for this project. They contain no third-party photograph. `fixtures/*_schematic.jpg` are our schematics.

## 5. Narration: VOICEVOX and 四国めたん (video)

* Engine: VOICEVOX ENGINE, Docker image `voicevox/voicevox_engine:cpu-latest` (container `rm-voicevox`, local only, `scripts/tts_voicevox.py`). Licence: LGPL v3 or a separate closed-source licence (https://github.com/VOICEVOX/voicevox_engine/blob/master/LICENSE). Used as an external tool; not redistributed, not linked into our code. Software terms (https://voicevox.hiroshiba.jp/term/): a credit showing that VOICEVOX was used is required; redistributing the software and reverse engineering are prohibited; each voice library's own terms apply.
* Voice: 四国めたん (speaker id 2). Voice terms (https://zunko.jp/con_ongen_kiyaku.html, VOICEVOX section): commercial and non-commercial use allowed; **credit required in the form `VOICEVOX:四国めたん`**; on video sites put it where viewers see it, **in the description or in on-screen credits**; common prohibitions apply (illegal/immoral purposes, political or religious activity, information-product promotion, deliberate misinformation, adult-entertainment businesses, anti-social groups); use without credit is a paid licence (400,000 JPY per character plus tax). The page shows the example `VOICEVOX:四国めたん` verbatim.
* Where the credit is: `docs/YOUTUBE_DESCRIPTION.md` line 36, `ナレーション：VOICEVOX:四国めたん` (matches the required notation) and the last card of the video (`docs/video_plan.json`, "ナレーション：VOICEVOX:四国めたん"). Both satisfy the "description or on-screen" rule. Keep both if the video is re-rendered; the check `tests/test_youtube_description.py` covers the description text.
* Generated audio (`outputs/narration/*.wav`) and the video (`outputs/video/*.mp4`) are git-ignored and not in the repository. Anyone who reuses the narration audio must give the same credit.
* Repo-level credit: this file and the README "Licences" section repeat the credit line.

## 6. Issues found while compiling this list

1. **No blocking redistribution problem found.** No committed file derives from D-Fire or Commons images, and no weights, fonts or audio are committed.
2. **Study Q is not on this branch.** When branch `worktree-agent-ac893207bdda069d9` is merged, `q_sample_final.json` (405 records, 246 of them CC BY-SA) will come with it. That is metadata only. Do not add Commons thumbnails or contact sheets to figures without per-image credits (see 4).
3. **README licence section** listed only some models; it now links this file and carries the VOICEVOX credit.
4. **Qwen2.5-VL-3B is non-commercial.** The MIT licence on this repository does not extend to anyone running the v3.3 stack commercially; that user needs Alibaba Cloud's licence. The submitted v3.6 path uses Qwen3.5-9B (Apache-2.0).
5. **`scripts/q_fetch.py` (Q branch) sends a User-Agent naming `github.com/tetsutetsu/rescue-mind`**, while the remote is `fe2131-art/rescue-mind`. Cosmetic, but fix the URL before publication so the contact address is correct.
6. **D-Fire provenance caveat**: the CC0 statement comes from the dataset authors for the collection; the web-scraped originals are not individually cleared. We do not redistribute them, so no action beyond not committing any D-Fire image.
7. A public Docker image of `docker/Dockerfile` is not published. If one is, it redistributes ROS/Gazebo (Apache-2.0), Ubuntu packages, FFmpeg (LGPL/GPL) and NVIDIA CUDA libraries (NVIDIA licence); add their notices then.
