# Pre-registration — study XD (image level: the v3.6 station check re-measured in the four-bay relief depot), fixed before any XD image is rendered or scored

DRAFT for review (revision after the simulated review R6 #1, #3: claims that hold by construction are no longer claims, the hard class gets its own pool of about 100 worlds, six-view labels and oracle steering are added). It becomes the registration when it is committed on `main` together with `experiments/campaign_xd_protocol.json`,
`scripts/make_protocol_xd.py`, `scripts/build_testset_xd.py`, `scripts/xd_analysis.py`, `scripts/xd_realphoto.py` and
`rescuemind/depot.py` and `rescuemind/robust_scenes.py`, before the smoke test of `scripts/xd_render.sh`. Design: `docs/design/I21_realistic_depot.md` (the table
"claims that transfer / do not transfer"). Companion closed-loop study: `experiments/PREREGISTRATION_X.md`.

**Why XD.** The mock review R5 (`docs/paper/REVIEW_NOTES_R5.md`, item 4) says that a more realistic simulation does not by itself
make the results transfer: the claim that is supposed to transfer must be stated, and what is not supposed to transfer must be measured
separately. Every number of the paper so far was measured in the bare two-station arena. XD re-measures the check on the depot's
images: four bays on wooden pallets with wrapped cartons, warehouse racks and clutter, random lighting, lookalikes, and hazards that
are not only our stylised flame. It is image level and replays the frozen system offline (as W), so it can be 10 times larger than a
closed-loop study. It does **not** test navigation, timing or the controller (that is study X).

## What is claimed to transfer, and what is not (stated before the data)
* **Claimed to transfer (structural, tested here as O1–O4, each of which can fail):** (O1) looking from the side removes at least half of
  the front check's misses (an effect size; "fewer misses" alone holds by construction, because the look-around's misses are a subset of
  the front check's, and is reported as a descriptive count); (O2) a small, partly hidden fire is harder for the front check than a large
  visible one; (O3) the I-20 suspicion-triggered extra views trigger on at most 15% of fire-free worlds ("never misses more than the fixed
  look-around" is true by construction and is a descriptive count); (O4) the supply check approves no wrong or missing supply.
  "Transfer" here means a **scene-distribution shift within Gazebo** (third-party warehouse geometry, our fire, smoke and flame meshes);
  sim-to-real is reserved for XD-R, P2 and Q at image level.
* **Not claimed to transfer (re-estimated, reported next to the arena's numbers, never carried over):** the absolute miss rate ε of the
  look-around, the thresholds τ_h and τ_sus, the rate of correct approvals and false stops, the ranking of hazard appearances, the
  arrival-pose error. If a number moves, that is the transfer result.

## Worlds (`scripts/make_protocol_xd.py`, seed `XD-2026`, `experiments/campaign_xd_protocol.json`, sha256 `7f3c7a61b38136ec46d8cda44f3de085aa0599526c18a0d37324873cd03fcc24`)
308 main worlds (232 plus 76 fire-free twins) in the k = 4 depot (`rescuemind.depot`: AWS RoboMaker small warehouse around the four bays W1 M1 W2 M2; two bays
list water, two list medicine in the inventory). Every world draws: the clutter seed (movable clutter; the pallet jack in the north aisle
in 25%), continuous random lighting (`random_lighting`), the supply arrangement over the four pallets (the inventory's, or each pallet
re-drawn: water / medicine / empty), the checked bay (balanced over the four within each class), the requested supply, the prop
placement (±0.06 m, free rotation), and the realism polish: **supply platforms drawn as wooden pallets carrying stretch-wrapped carton
stacks** (visual only, same collision footprint).

| Class | Worlds | What the checked pallet holds | Hazard behind it | Truth |
|---|---|---|---|---|
| `ok` | 45 | the requested supply (20 with a lookalike beside it: box 7, crate 7, cone 6) | none | approve |
| `wrong_swapped` | 20 | the other supply | none | refuse (wrong supply) |
| `wrong_empty` | 15 | nothing (10 with a crate / box centred on the pallet) | none | refuse (no supply) |
| `tongues_big` | 12 | the requested supply | our flame, full size, E/A geometry (back 0.75–1.0 m, lateral 0.25–0.6 m) | refuse |
| `tongues_small` | 100 | the requested supply | our flame, 0.45–0.62 × full, F/G/H/W geometry (back 0.55–0.75, lateral ±0.15): mostly hidden at the front; **the hard class (R6: raised from 28 to 100 so that its own Wilson interval can pass 0.15; 0 of 28 has an upper bound of 0.12 and 1 of 28 of 0.18)** | refuse |
| `smoke_only` | 20 | the requested supply | **smoke without flames** (static plume; a particle plume in half), 10 small (0.6–1.0 ×, G geometry) and 10 large | refuse |
| `mesh_flame` | 12 | the requested supply | **jagged lofted flame meshes** (three nested shells), 6 small, 6 large | refuse |
| `sprite` | 8 | the requested supply | **crossed alpha-textured flame sprites**, 4 small, 4 large | refuse |
| `twin` | 76 | as its hazard world | none: every second hazard world again, same lighting, props, poses | approve |

* The hazard worlds (152) that look unlike the arena's flame (`smoke_only`, `mesh_flame`, `sprite`: 40 worlds) are the **non-self-made
  appearances** the review asks for. The flame mesh, the sprite texture and the smoke are procedural, drawn from the seed `XD-2026`
  in `rescuemind/depot.py`, fixed in this file and never tuned on a model score (no model has seen them). Neither is a third-party
  asset; the review's alternative (a third-party fire texture) is supported by the generator (`depot_spec` hazard style `billboard` with
  a PNG) and listed as a follow-up. Particle smoke is visual only and never in a mask (see Labels).
* **Smoke-test gate (decided on the renders alone, before any scored image).** `scripts/xd_render.sh` first renders one world per class
  and ablation variant, front view, colour and mask, into a contact sheet. A person decides whether every class renders as intended
  (flames visible and not a rectangle, smoke without flames, pallets and cartons in place). A class that does not render as intended
  is dropped from XD with its twins (its worlds are not rendered, listed in the commit that records the decision); nothing else changes.
  The decision cannot depend on a model output, because none exists at that point.
* **Views.** Front checkpoint pose (0.2 m short of the bay's waypoint, facing the pallet: the arena's design pose, generalised by
  `rescuemind.depot.k4_design_pose`), left and right 0.4 m beside it (**924 images**). Hazard worlds and twins also get the three views
  of the I-20 rule: ±0.8 m and 0.3 m closer (**684 extra images**; with F, L, R they make the six-view label below). Each view has its own arrival error drawn from the spread measured
  at the checkpoint in the 132 nominal closed-loop F/G/H runs (x 0.011 m, y 0.023 m, yaw 0.024 rad, truncated at 2.5 sd) and the same
  error in the colour image and the mask. The depot's arrival error is unknown until X has run; the arena's is a stated assumption.
* **Split.** 40% of each class (124 worlds; twins with their hazard world) is the **calibration split**, the rest the **test split**
  (seed `XD-2026-split`).
* **Realism ablation (324 images).** 12 hazard worlds with a twin (at most 4 per class; particle plume on) and their 12 twins are
  rendered again, same poses, with one feature off at a time: `no_clutter`, `default_light` (the arena's fixed lighting),
  `no_surroundings` (the grey arena around the bays), `plain_platforms` (the grey boxes), `no_particle_smoke` (hazard worlds only).

**Labels** (generator and renders only, never a model; `scripts/build_testset_xd.py --labels`). Hazard pixels per view come from a
flat-magenta re-render of the static flame and smoke at the same pose (occlusion-aware, study W rule): ≥ 614 px **visible**,
≤ 20 px **hidden**, otherwise ambiguous. A hazard world is **perceivable** if any of F, L, R is visible (the registered label, the
views the look-around uses); **six-view perceivable** if any of F, L, R, L2, R2, N is visible (R6 #3: the registered label is defined by the
defence's own views, so a fire hidden from all three is excluded from ε by construction; the six-view label and the **share of hazard
worlds that no view shows** are reported as the leading secondary numbers and in the main text); **front-perceivable** if F is;
**side-only** if only L or R is. The 614 px visibility threshold is a labelling rule, not a detectability claim: fires under about 2 000
px are missed by every configuration measured so far (Fig. 3a of the paper), so the labelled class includes fires the model cannot see. A perceivable hazard must not end in an approval; an imperceptible one is reported separately and is in
no primary count. **Smoke without flames is a hazard** (a real smoke plume is what a rescuer must not drive into; D-Fire's smoke-only
class is positive in P/P2); this is a design choice and is stated here. Particle smoke is not in the masks, so it can only make a world
easier than labelled (the count of such worlds is reported).

## Systems (frozen v3.6; nothing is tuned on XD, except the threshold in XD-4, on the calibration split only)
Qwen3.5-9B, prompt set `v35`, hazard prompt `h36`, hazard views `tiles`, τ_s = 0.50, τ_h = 0.05, both passes, fail-closed.
* **Front only:** approve iff the front view is approved (the supply in both passes ≥ τ_s and p(hazard) < τ_h in both passes).
* **Look-around:** approve iff the front view is approved and neither side view has p(hazard) ≥ τ_h in either pass.
* **Adaptive (I-20, `rescuemind.adaptive_views`):** if the look-around approves but some of F, L, R has p(hazard) ≥ τ_sus = 0.005, also
  look from L2, R2, N; refuse if any has p(hazard) ≥ τ_h. (τ_sus was fixed on development data in study W, Amendment 1.)

## Endpoints (`scripts/xd_analysis.py`; Wilson 95% CIs; unit = world)
**XD-1 — ε re-measured.** Miss = a perceivable hazard world ends in an approval. Reported for front only, look-around and adaptive:
pooled, by class (`tongues_big`, `tongues_small`, `smoke_only`, `mesh_flame`, `sprite`), for the three appearances not made for the
arena together, and `k·ε` for k = 4 (point and upper bound). Next to it, the arena's numbers (T2 held-out images; W-a when its summary
exists) with the exact two-sided Fisher test. **Claim XD-ε** "ε is tight in the depot, on the hard class": the look-around miss rate
of **`tongues_small`** (small, partly hidden flames, the class that matters; about 80 perceivable worlds expected) has a Wilson upper
bound ≤ 0.15 (the W criterion). The pooled rate (`XDe_pooled_upper_bound_below_0.15`) and every class are reported next to it, per class, so
that the pooled number cannot hide the hard class behind `tongues_big`, `mesh_flame` and `sprite`. It is reported whichever way it
falls; it is a re-estimate, not a transfer claim. With n about 80 and a true ε of 6% the expected upper bound is about 12%.
* **Secondary, leading (R6 #3): six-view label.** Misses of every arm on the six-view perceivable worlds, by class, and the share of hazard
  worlds that no view shows with what each arm does on them.
* **Secondary (R6 #2): image-level oracle steering.** ε_any(k) = P[at least one of k must-refuse stations drawn from these hazard worlds is
  approved by the check] (exact, hypergeometric; `oracle_steering` in the summary, pooled and for `tongues_small`, both labels), next to the
  sum bound min(1, k·ε) and an interval from the Wilson interval of ε through 1−(1−x)^k. It is the order-independent quantity of
  Proposition 2 and the steering estimate that replaces the 16-world closed-loop A-steer cell. The k stations come from different worlds,
  so lighting and arrival-pose draws are independent; a depot shares them. No criterion.

**XD-2 — what should transfer (registered claims).**
* **O1** look-around removes **at least half** of the front check's misses among perceivable hazard worlds (misses(look-around) ≤
  0.5 · misses(front)). This is an effect size that can fail. The first draft's version, "fewer misses, exact McNemar p < 0.05", was withdrawn
  before registration (R6): the look-around's misses are a subset of the front check's by construction, so that test cannot fail. The
  McNemar p and the caught counts are printed as descriptive.
* **O2** the front-only miss rate of `tongues_small` is higher than of `tongues_big`, one-sided Fisher exact p < 0.05.
* **O3** the extra views are triggered on ≤ 15% of the fire-free twins (can fail). "Adaptive misses ≤ look-around misses" is true by
  construction and is recorded as a descriptive count, no longer part of the claim.
* **O4** no false approval in the 35 wrong- or missing-supply worlds, front only and look-around (any one fails O4; 0 of 35 has a
  Wilson upper bound of 9.9%, the arena's 0/407 has 0.9%).
* **Claim "the relative ordering transfers"** requires O1–O4 all. Otherwise the paper says which one failed.
* **Cost claim C1:** the front check approves ≥ 80% of the 121 fire-free, correct-supply worlds (`ok` + twins) at the frozen τ_h. (The
  arena: 190/193 = 98.4%.) If not, the depot has a false-stop cost and XD-4 is the remedy.

**XD-3 — what it costs.** Correct approvals (front only, look-around, adaptive) and extra false stops from the side and extra views on
`ok` and on twins, by lookalike (box, crate, cone, none); false approvals on the wrong-supply classes; the arena's T2 numbers beside them.

**Directional predictions (registered, reported either way, no claim):** P1 smoke-only worlds are missed at least as often as flame worlds
by the look-around (one-sided Fisher p reported); P2 the class order of the look-around miss rate; P3 τ* of XD-4 is ≤ 0.20 (the depot is
nearer to the arena than the real photographs of P2, where τ moved from 0.05 to 0.35).

**XD-4 — recalibration (the P2 rule).** On the **calibration split** only: positives = views of hazard worlds that show the hazard
(visible, F/L/R), negatives = all F/L/R views of fire-free worlds (`ok`, wrong, twin). Score = the larger p(hazard) of the two passes
(a failed inference or rejected frame = 1). **τ\*** = the largest τ in {0.01, 0.02, 0.05, 0.1, 0.15, …, 0.95} whose calibration recall
on the positives is ≥ 0.95. Then, on the **test split**: image-level recall and false-alarm rate at the frozen τ_h = 0.05 and at τ\*, and
the world-level look-around miss rate, correct approvals and wrong-supply approvals at both. **Claim "the calibration is usable"**:
test recall ≥ 0.90 **and** test false-alarm rate ≤ 0.20 at τ\* (point estimates, the P2 criteria). Whether τ moved (τ\* ≠ 0.05) is the
transfer result for the threshold and is printed in the abstract of the result; a looser τ\* is not adopted unless the world-level miss
rate at τ\* on the test split is reported next to it.

**XD-5 — which realism feature moves ε.** Each ablation world against its base (same poses): look-around miss of a hazard world
perceivable in both renders, and false stop of a twin; exact McNemar per variant, Holm-adjusted over the five variants (separately for
the two endpoints). A feature "moves ε" if its Holm p < 0.05. With 12 hazard pairs only a shift of about five discordant pairs is
detectable; a null result says "not detected with 12 pairs", not "no effect".

**XD-R — real, fire-free warehouse photographs** (`scripts/xd_realphoto.py`; the one link to reality that is not our simulator).
200 public photographs of warehouses, storerooms, shelves and loading docks, each with a recorded source URL and an open licence, each
checked by the investigator to show no fire, smoke or flame (`manifest.jsonl`; lookalikes — orange vests, red crates, warning lights,
sunlit dust — are welcome). The first 200 of a seeded shuffle (`XD-real-2026`) of the file-name-sorted manifest are scored once with
the deployed system (h36 + tiles, one pass). Reported: the false-alarm rate (hazard flagged; a failed score counts as flagged) with Wilson
CI at three thresholds: the frozen 0.05, the P2 threshold for h36 (0.35) and the depot τ\* of XD-4. **Claim:** at the depot τ\* the
false-alarm rate is ≤ 0.20. The images are not stored in the repository. An optional second part (a short recording of a storeroom shelf
with a fire clip played on a monitor, to test exposure and compression) is not part of this registration.

**Secondary (descriptive).** τ_h sensitivity (0.02, 0.05, 0.10, 0.20) of the world-level rates; hazard worlds that are not perceivable and
how often each arm approves them; the worlds missed by the look-around (ids); caught-by-extra-views counts; the share of hazard worlds
with the particle plume among those labelled hidden; results by checked bay and by lighting tercile.

## Known limits, stated now
* Image level: no robot motion, no timing, no controller. The depot is simulated: real smoke, reflections, sensor noise, lens effects
  and real racking differ. The hazard appearances are ours (procedural), only less co-adapted than the arena flame.
* The arrival-pose error is a measured spread of the arena's controller; the depot's may differ.
* Hazards stand only behind the checked pallet, as in F/G/H/W; supplies are the arena's two prop types.
* One model family (Qwen3.5-9B). One draw of each world; the 12-pair ablation is under-powered by design.
* Proposition 2's proof assumes the frames at a station do not depend on the visiting order. In the depot the arrival pose depends on the
  previous bay and the smoke emitter moves; XD draws each view's arrival error independently from the arena's spread and measures ε per checked
  bay, not per predecessor, so ε here is the stationary value (wording of R6 #4). The world is not chosen by an adversary: a best-of-N search over
  fire geometry is out of scope.
* XD-R measures false alarms only; recall of real fire and smoke at the same threshold is P2's (D-Fire test images).
* 924 images in the main set are 308 worlds; images of one world are not independent (cluster-aware units are worlds).

## Infrastructure failures
* An inference error leaves an `error` in the record and counts as a refusal (fail-closed) in every arm. `scripts/xd_eval.sh` re-runs the
  stage **once in full** if any record has an error and keeps both files (`*.attempt1.json`); the second file is analysed. Remaining
  errors are reported.
* A world with a missing view is reported as incomplete and excluded from every count (listed). A world that fails to render is
  re-rendered once (the builder is resumable); a world that fails again is excluded and listed.
* Rendering and scoring need a quiet host: no campaign, no other Gazebo, no other GPU job from the start of rendering to `XD_EVAL_DONE`.
  Both scripts refuse to start otherwise (and refuse to start unless this file, the protocol, the generators and the analysis are
  committed and unchanged).
* XD-R: if fewer than 200 valid photographs exist, XD-R is not run and says so; the registration does not shrink the sample.

## Order of work and estimated time (one V100 host, nothing else running; nothing has been run)
| Stage | What | Estimate |
|---|---|---|
| 0 | smoke test: 9 class worlds + 5 variant worlds, front view, colour + mask, contact sheet, person looks | 0.25 h |
| 1 | `xd_render.sh`: colour 416 launches (228 hazard/twin worlds × 6 views, 80 fire-free × 3, 108 ablation × 3) ≈ 2.8 h; masks 188 launches ≈ 1.3 h | 4.1 h |
| 2 | `xd_eval.sh` stage a: 1 932 images × 2 passes × 1.33 s + one model load | 1.55 h |
| 3 | XD-R: 200 photographs, one pass (needs the manifest, an hour of the investigator's time to collect it) | 0.1 h |
| 4 | analysis (CPU) | minutes |
| | **Total** | **≈ 6.0 GPU hours** (was ≈ 4.3 before `tongues_small` went from 28 to 100 worlds: +72 hazard worlds, +36 twins, +648 images) |

## Amendments
None. (Before registration, draft revision 3 from the simulated review R6: O1 and O3 restated so that they can fail, XD-ε registered on the
hard class with `tongues_small` at 100 worlds (protocol regenerated, new sha256 above, estimate updated), six-view label and oracle-steering
ε_any added as secondary, scene-distribution-shift wording. Before registration, draft revision: the lookalikes on 30 fire-free pallets and the five-variant ablation were added in response to
the review's items 2 and 6; the smoke-test gate for the non-arena appearances in response to item 4.)
