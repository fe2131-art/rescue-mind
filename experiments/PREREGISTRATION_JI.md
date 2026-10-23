# Pre-registration — study JI (do more views, and a second judge on top of them, remove the hard class's last misses? fresh images), fixed before any JI image is rendered

It becomes the registration when it is committed on `main` together with `scripts/make_protocol_ji.py`, `scripts/build_testset_ji.py`, `scripts/ji_analysis.py`, `scripts/ji_run.sh`, `experiments/campaign_ji_protocol.json`, `experiments/ji_thresholds.json` and `tests/test_study_ji.py`, **before the smoke test or any render**.
The commit is stamped with OpenTimestamps (hashes only); the run starts once the stamp is submitted (start rule as GC Note 3). `scripts/ji_run.sh` waits for study GM, takes `/tmp/rescuemind_campaign.lock` and needs a quiet host. Design note: `docs/IMPROVEMENT_LOG.md` I-93 (the findings) and I-94 (this study).

## Why JI exists (and what was seen before registering — disclosed)
The factor analysis of study JH (I-93, post hoc) found on XD's test split: (1) the 126 test fires are 91 base worlds and 35 ablation copies, the gate's 14 misses are 11 base worlds and a second judge rescues 1-3 of them; (2) 8 base worlds are missed by all four judges far below their thresholds (a perception limit); (3) **the same scorers on more views miss much less**: the gate alone 14 (three views F, L, R at 0.4 m) -> 10 (F + left 0.8 m, the GL arm) -> 6 (F + both 0.8 m) -> 5 (all six views incl. a view 0.3 m closer) with no false stop, and with InternVL3 as a veto on the six views 2 misses at 2 false stops of 104.
Those numbers are on the set that produced the questions, with view sets and the judge chosen after seeing them, so they are a hypothesis. JI tests it on **fresh worlds**: seed `JI-2026`, nothing shared with XD or any study world. Thresholds are **frozen from XD's clean calibration worlds** (`experiments/ji_thresholds.json`, from `experiments/results/jh_views.json`) and nothing is fitted on JI.

## What JI runs, and nothing more (wording frozen)
**Worlds** (`scripts/make_protocol_ji.py`, the XD generator with another seed and one class): 120 depot worlds with a small partly hidden fire behind the checked bay ('tongues_small': back 0.55-0.75 m, lateral +-0.15 m, scale 0.45-0.62; random lighting, clutter, supply arrangement, particle smoke in about half) and, for each, its **fire-free twin** (same world without the fire) = 120 clean worlds; **no ablation copies**, no lookalikes, no other class.
**Images:** six views per world (F, L, R at 0.4 m as in the submitted system; L2, R2 at 0.8 m; N 0.3 m closer), poses with the arrival error of the closed-loop runs (the XD generator's), rendered with the XD pipeline (`scripts/build_testset_ji.py`): 240 x 6 = 1440 images; labels from the fire masks (a fire is *perceivable* in a view when its design mask shows at least 614 pixels), never from a model.
**Scorers:** the frozen gate (Qwen3.5-9B, v3.6 = h36 + tiles, both passes, fail-closed) on every image; the four judges of study JH (InternVL3-8B, Idefics3-8B, Qwen3-VL-8B, SmolVLM2) on every image with their JH protocol. Per-world score = maximum over the views of a view set; thresholds as frozen.
**View sets:** `v36_FLR` (F, L, R), `GL_F+L2` (F, L2), `wide_F+L2+R2`, `all_six`.
**Selection of fire worlds:** all 120 are analysed as generated; a world whose fire is perceivable in **no** view (fewer than 614 pixels in every one of the six) is not excluded but counted and listed (such a fire cannot be missed by perception).

## Endpoints and claims (explicit; `scripts/ji_analysis.py`)
A miss is a fire world whose score is below the frozen threshold in every view of the set; a false stop is a twin with a score at or above it in some view.
* **JI1 — the six-view gate.** The gate alone on the six views misses **at most 8 of the 120** fire worlds (exact one-sided 95% Clopper-Pearson upper bound reported; XD: 5/126).
* **JI2 — views, paired.** The six views miss fewer fires than the submitted three views: the exact **one-sided McNemar** test over the 120 fire worlds gives **p < 0.05** and fewer (XD: 14 -> 5 on copies of worlds).
* **JI3 — false stops.** The six-view gate stops **at most 5 of the 120** twins (XD: 0/104).
* **JI4 — the veto on top.** Gate + InternVL3 on the six views: **at most 3 of 120** fire worlds missed by both and **at most 6 of 120** twins stopped by either (the judge and its threshold were chosen on XD, as JH's registered rule would have chosen them).
* **Descriptive (predictions registered; failing them is reported, not a failed claim).** P1: the 0.8 m views alone (`GL_F+L2`, `wide`) miss fewer than the three views. P2: the union of all four judges with the gate on the six views misses at most 2 at at most 8% false stops. The other view sets and judges, the view that catches each fire, the fires with no perceivable view.
**Power (stated now, not simulated):** if the XD rates hold (three views 11%, six views 4%) n = 120 gives about 13 against 5 misses, which the paired test separates easily; JI1 allows 8 (6.7%), JI4's limit of 3 (2.5%) is the tight one: XD's 2/126 leaves little margin.
**Success is not "no miss".** A failed JI1-JI4 goes into the failed-claim list. A deviation whose record does not support its cause blocks the paper's sentence about it. Infrastructure failures (a render or a scoring that fails) are re-run once; a second failure stays listed.

## Decision rule for the system
Whatever JI finds, the submitted system keeps its three views until a registered closed-loop study of the extra views is run (a 0.3 m closer peek is not implemented in the mission code; the 0.8 m peeks are, `--look-around 0.8`). If JI1-JI3 hold, the paper states that the image-level evidence for "more views, not more judges" replicated on fresh worlds and names the closed loop as the next study; if JI4 holds, the second judge is reported as a useful last layer *behind* the views, not instead of them. If JI2 fails, the post hoc finding of I-93 is withdrawn as not replicated.

## Mechanics pilot
The smoke test of the XD pipeline (one fire world and one twin, front view, colour and mask, contact sheet) is looked at by a person before the render (`experiments/results/ji_smoke_ok`); a render bug found there is fixed and recorded as an amendment before any JI image is scored.

## Cost
Render about 3 h (Gazebo, the GPU only for rendering), the gate about 1.3 h, the four judges about 1 h each: about 8-9 h after GM ends. Needs a quiet host.

## Known limits, stated now
Simulation; the same depot and fire generator as XD (the hard class only), so JI tests the replication on fresh worlds, not another renderer; thresholds borrowed from XD (the six-view and 0.8 m view sets were seen on XD); the near view N has no mission-code implementation, so the six-view result is image-level; judges and view sets were chosen after XD; one image per view (no look-around dynamics, no navigation error beyond the arrival jitter).
