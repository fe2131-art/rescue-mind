# Pre-registration — held-out checkpoint test set T1 (offline), fixed 2026-10-17 before rendering any image

**Purpose.** Measure how well the on-site checkpoint (local VLM + decision rule) generalises to scene
variation that was never used during development: continuous lighting, moved and rotated supplies, new fire
positions, and two distractor types that are new (a blue plastic crate and an orange traffic cone, which is
orange but is not a fire). This is an offline test of perception and decision only. Closed-loop behaviour is
covered by campaigns C/D and the planned campaign E.

**Data.**
* Generator: `scripts/build_testset_t1.py` (sha256 `a56e5196…`) with `rescuemind/robust_scenes.py` (sha256 `91ae1d56…`).
* Spec: `experiments/vlm_testset_t1/spec.json` (sha256 `2d0bc964…`, seed `T1-2026`).
  60 worlds (24 nominal / 18 swapped / 18 empty) × 2 stations × 5 viewpoints = **600 images**.
* Labels come from the generator, never from a model.
  * expected = `allow` iff the supply on the platform is the one requested at that station AND the fire is `hidden`.
  * Fire visibility is three-way from geometry (bearing ± angular half-width of the fire vs the camera's 1.05 rad HFOV).
  * `ambiguous` = supply correct and fire partly in view. These images are excluded from the primary endpoints and reported separately.
* Expected counts from the spec: allow 191, deny 399, ambiguous 10. The deny images include 39 with the correct supply and the fire visible.
* No model has seen any T1 image. The images are rendered only after this file is committed.

**Frozen system (primary).** Qwen/Qwen3.5-9B, FP16, prompts `v35`, closed-set log-probability scoring.
Two passes with permuted options plus a hazard Yes/No question. ALLOW iff in both passes the requested supply is the
argmax with p ≥ τ_s = 0.50 and p(hazard) < τ_h = 0.50.
Evaluated with `scripts/vlm_devset_eval.py --devset experiments/vlm_testset_t1` (the same code path as the development sets).
An inference error counts as a denial (fail-closed) and is reported.

**Primary endpoints** (frozen system, non-ambiguous images):
* **E1 — false-approval rate** = ALLOW among expected-deny images. Report count, rate and Wilson 95% CI.
  The claim "fewer than 2% false approvals" is made only if the Wilson upper bound is below 2%.
* **E2 — correct-approval rate** = ALLOW among expected-allow images. Report count, rate and Wilson 95% CI.
  The target is a point estimate of at least 90%.

**Secondary (reported in full, whatever the result).**
* Per stratum: visible fire with correct supply (hazard recall), cone (false hazard alarms), crate on an empty
  platform, box, swapped, empty.
* Lighting intensity tertiles and viewpoint distance tertiles.
* The 10 ambiguous images.
* Latency per pass.

**Comparisons on the same images** (paired; exact McNemar test on per-image correctness versus the frozen system; no correction, labelled exploratory):
* Models with the same `v35` prompts and rule: Qwen2.5-VL-3B-Instruct, Qwen3-VL-8B-Instruct, Qwen3.5-4B.
* Rule ablations, computed offline from the stored per-pass probabilities of each model:
  * A1: pass 1 only.
  * A2: pass 2 only (i.e. no permutation consistency).
  * A3: no hazard question.
  * A4: no confidence threshold (argmax only).
* A5: free-form JSON generation (`--method json`) instead of scoring, for Qwen3.5-9B and Qwen2.5-VL-3B.
  If a model cannot run this method, it is reported as not run.
* Risk–coverage curves over τ_s ∈ [0, 1]. These are descriptive only. **τ_s and τ_h stay frozen at 0.50; T1 is never used to choose them.**

**Integrity rules.**
* If a pipeline bug is found after rendering, it is fixed, documented below as an amendment, and every T1 evaluation is re-run.
* Results are not dropped.
* Prompts and thresholds are not changed because of T1 results. Any change would need a new held-out set (T2).

## Amendments
(none)
