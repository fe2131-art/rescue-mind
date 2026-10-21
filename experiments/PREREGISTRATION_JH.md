# Pre-registration — study JH ("Jev": does a judge from a different model family miss different fires?), fixed before any non-Qwen score of the XD images or of the depot closed-loop views is computed

Committed on `main` together with `scripts/jev_score.py`, `scripts/jh_analysis.py` and `tests/test_jh_analysis.py`, **before** InternVL3-8B, Idefics3-8B, Qwen3-VL-8B or SmolVLM2 score any XD image or closed-loop view (the one smoke test of `jev_score.py`
with SmolVLM2 on 4 GVK views, run to check the code, is disclosed and not analysed). Idea and design: `docs/JEV_DESIGN.md` (the idea is the user's). Design note: `docs/IMPROVEMENT_LOG.md` I-73.

## Question
The gate has one VLM. A second judge of a *different family* that may only veto (conjunction: refuse if either flags) lowers the missed-fire rate by exactly as much as its misses are *not* shared with the first. Clef-Flash could not test this (a fine-tune of Qwen3.5-9B, study J).
JH measures the overlap of the misses across families, at image level (XD) and on the saved closed-loop views of the depot.

## Data and judges (nothing else)
* **Judges:** primary `Qwen/Qwen3.5-9B` (the gate; its XD scores are the stored `devset_xd_h36_tiles.json`, its closed-loop scores the stored `gv_dev_prompts.jsonl` h36 column); candidates `OpenGVLab/InternVL3-8B-hf`, `HuggingFaceM4/Idefics3-8B-Llama3`, `Qwen/Qwen3-VL-8B-Instruct`, `HuggingFaceTB/SmolVLM2-2.2B-Instruct`. Same question (h36 wording), full image + the three enlarged crops, per-image score = maximum, next-token Yes/No rule (`scripts/jev_score.py`), fp16, no prompt tuning per judge.
* **XD (image level):** `experiments/vlm_testset_xd`, views F, L, R at 0.4 m (no extra views). Per-world score = maximum over the world's three views. Fire worlds = `world_kind = hazard` and `world_perceivable_any_view`; clean worlds = `world_kind` in {`twin`, `ok`}. Split as labelled (`cal` / `test`).
* **Closed loop (secondary, descriptive):** the saved views of GVK (clean, 0.8 m), GDK (clean, 0.4 m), GD (fire and fire-free worlds, 0.4 m) and GVD (GD's fire worlds, 0.8 m, development pass I-70), per-run score = maximum over the three views.

## Threshold rule and judge selection (fixed now)
* Each judge's threshold = the rank rule at alpha = 2% (`scripts/calibration_sites.py`) over the per-world scores of the clean **cal** worlds of XD (closed loop: of GDK for GD, of GVK for GVD), rounded up to the next thousandth. A world is *flagged* if its score is at least its judge's threshold.
* **The Jev judge is the candidate with the highest ROC AUC on the XD `cal` split** (perceivable fire worlds against clean worlds, per-world maximum). Ties go to the order InternVL3, Idefics3, Qwen3-VL, SmolVLM2. The `test` split is not used for the choice. The conjunction is "Qwen flags or Jev flags".

## Endpoints (`scripts/jh_analysis.py` -> `experiments/results/jh_summary.json`)
On the XD `test` split (n_fire perceivable fire worlds, n_clean clean worlds): misses of Qwen alone (m_Q), of the Jev judge alone (m_J), joint misses (neither flags; m_QJ), the number expected if the misses were independent (n_fire x (m_Q/n_fire) x (m_J/n_fire)),
the phi coefficient and the exact Fisher test of the 2 x 2 table (missed by Q, missed by J), the false stops of each judge and of the conjunction on the clean test worlds, and the same for every candidate (descriptive).
* **JH1 (primary).** m_QJ is **at most two thirds of m_Q** (integer: m_QJ <= floor(2 m_Q / 3)), and the conjunction's false stops on the clean test worlds are **at most 5%** (exact one-sided 95% Clopper-Pearson upper bound reported).
* **Descriptive predictions (failing them is reported, not a failed claim).** P2: m_QJ < m_Q (the conjunction misses strictly fewer worlds than Qwen alone), with the Fisher test of independence reported. P3: the two candidates from families other than Qwen's (InternVL3, Idefics3) overlap less with Qwen3.5 (phi) than Qwen3-VL does.
**Success is not a lower m_QJ alone.** A failed JH1 is added to the failed-claim list; a judge whose union false stops exceed 5% is reported as an availability cost, not selected afterwards.

## Decision rule for the system
Whatever JH finds, the submitted default stays v3.6 (one judge). If JH1 holds at image level the next steps (registered separately, each before its run) are the closed-loop conjunction at the station (two VLMs do not fit one V100 at the same time in fp16 for the 9B pair: sequential loading or an 8-bit judge is part of that design) and the driving judge (`docs/JEV_DESIGN.md`, items 2 and 3).
If it fails, the paper says that a heterogeneous judge shares the misses of small hidden fires (a perception limit, not a model limit) and keeps the result as a negative finding.

## Known limits, stated now
Simulation and rendered images (XD); one question wording for all judges (a judge-specific wording could change the result); fp16, one seed (no sampling: deterministic scores); the closed-loop part inherits the 40-world limits of GD and GVD and is descriptive; judges are chosen on XD `cal` (65 clean worlds), so the rank rule gives about 1.5% per judge.
* Disclosed before the commit: running `scripts/jh_analysis.py` on the stored Qwen scores printed only Qwen's own XD threshold (0.088 at alpha = 2% over the clean `cal` worlds) and its `cal` AUC (0.988); no `test`-split miss count of Qwen and no score of any candidate had been looked at.
