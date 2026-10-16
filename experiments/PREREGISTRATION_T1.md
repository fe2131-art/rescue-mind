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
* Expected counts from the spec (as amended, see Amendment 1): allow 190, deny 396 (36 of them with the correct supply and the fire visible), ambiguous 14.
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
**Amendment 1 (2026-10-17, during the first render; no model had scored any T1 image).**
I inspected rendered images and found that box/crate distractors in nominal/swapped worlds stood at the platform
centre, intersecting the supply.
* Cause: `build_variant` decided "is this platform empty?" AFTER moving the supplies, so every platform with a moved supply looked empty.
* Fix: emptiness is decided from the scene definition before any prop is moved (regression test added).
* Placement change: a distractor beside a supply now stands ON the platform next to it, with the supply kept on the other half. This is the same layout as campaign E. A distractor on an empty platform stands at its centre.
* The partial render (15 worlds) was deleted, the spec regenerated, and the full set rendered again.
* New hashes: spec `e000fa18…`, generator `scripts/build_testset_t1.py` `d8a234fb…`, `rescuemind/robust_scenes.py` `51cc933a…`.
  The original hashes in the Data section above are superseded.

**Amendment 2 (2026-10-17, after the full render, before any model scored any T1 image).**
I inspected a contact sheet of the fire images and found that the geometric fire label ignores occlusion: some
"visible" fires were almost completely hidden behind the supply.
* The images given to the models are unchanged.
* The fire label is recomputed from a second render of every view of the 16 fire worlds, in which only the flames and smoke
  are drawn in flat emissive magenta without shadows. The burnt ground disk is not counted.
* Per view, `fire_pixels` is the number of magenta pixels:
  * ≥ 614 pixels (0.2% of the image) → `visible`;
  * ≤ 20 pixels → `hidden`;
  * in between → `ambiguous`.
* `expected` is derived as before from this label. The geometric label is kept as `hazard_visibility_geometric`.
* The thresholds were fixed before the masks were rendered.
* Code: `scripts/build_testset_t1.py --fire-masks` and then `--relabel` (sha256 `29c00fdb…`), with `rescuemind/robust_scenes.py` (`40a73e40…`).

**Amendment 3 (2026-10-17, before any model scored any T1 image).**
* Campaign E's mechanics pilot (development worlds, seed `E-pilot`) produced a missed hazard. The fire was mostly hidden
  behind the supply, and p(hazard) = 0.32 < τ_h = 0.50.
* On the development images, no image without fire exceeds p(hazard) = 0.0007, so a refusal threshold far below 0.5
  costs nothing there. The system for campaign E is therefore **v3.5 = v3.4 with τ_h = 0.05** (I-10).
* T1 reports both configurations:
  * the registered primary (v3.4, τ_h = 0.50), with the primary endpoints unchanged;
  * the pre-specified secondary (v3.5, τ_h = 0.05).
* Both are computed offline from the same stored probabilities. τ_h = 0.05 was fixed from development data and the pilot only, before T1 scoring.
