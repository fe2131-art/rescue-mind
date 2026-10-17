# Pre-registration — study W (W-a: how often does v3.6 miss a small, partly hidden fire, with and without looking around? W-b: do the closest prior mechanisms already give the same false-approval rate?), fixed before any W image is rendered or scored

**Why W.** The mock review R4 (`docs/paper/REVIEW_NOTES_R4.md`, W2 and W5) names the two weakest places of the safety argument:
1. **The number that matters is based on 16 fires.** Campaign G missed 1 of 16 hidden fires with look-around (Wilson 95%
   upper bound 28%). The bound `k·ε` of the corollary is therefore not informative at its upper end. Study R stresses only
   easy fires (T2 small fires: 5/5 detected).
2. **No experiment separates our mechanism from the closest prior art.** VAP-TAMP votes over paraphrased yes/no questions;
   KnowNo takes a conformal prediction set over option scores. The paper lists the differences in text only.

W is image-level and replays the frozen system offline. It needs no closed-loop run, so it can be 10 times larger than G.
The check is a pure function of the captured images (front checkpoint view and, after an approval, the two side views), which
is what `combine_with_look_around` computes. W does **not** test navigation, timing or the controller.

## W-a. Tight ε for the hard class (new renders)

**Worlds** (`scripts/make_protocol_w.py`, seed `W-2026`, `experiments/campaign_w_protocol.json`, sha256
`c4d8e413edd30ffb8c0381d528735b37907541e3d71aa9465f8edb517505e017`).
* **150 fire worlds.** Same distribution as campaigns F/G/H:
  * nominal scene, requested supply water or medicine (75 each);
  * continuous random lighting (`random_lighting`), supplies moved ±0.06 m and rotated freely;
  * a small fire (0.45–0.62 × the full model), straight behind the requested station: back 0.55–0.75 m, lateral ±0.15 m.
* **75 fire-free twins:** every second fire world again, with the same lighting, supplies, item and view poses, and no fire.
  A twin tests what looking around costs.
* **Three views per world** (675 images), rendered by `scripts/build_testset_w.py` inside the `rm-next` container
  (`scripts/w_render.sh`):
  * **F:** the front checkpoint pose (`fire_mask_at_pose.DESIGN_POSE`, the median pose of campaign D);
  * **L, R:** 0.4 m to the left and right of the checkpoint waypoint, each facing the station (`--design-sides 0.4`).
  * Every view gets its own pose error, drawn from the spread measured at the checkpoint in the 132 nominal closed-loop runs
    of F, G and H (std of the ground-truth pose minus `DESIGN_POSE`: x 0.011 m, y 0.023 m, yaw 0.024 rad; truncated at 2.5 std).
    Colour images and fire masks use the same poses.

**Labels** (generator and renders only, never a model; `scripts/build_testset_w.py --labels`).
* Fire pixels per view come from a flat-magenta re-render of the fire at the same pose (occlusion-aware, as in T1 amendment 2).
  A view shows the fire if it has ≥ 614 pixels. (`t1.mask_label` needs ≥ 614.4, i.e. 615, but the design masks of G, H and V use
  ≥ 614. W follows the design masks and writes the rule out in `view_label`. The two rules differ only for an image with exactly 614
  fire pixels; the T1/T2 labels used in W-b keep their original rule, ≥ 615.)
* A fire world is **perceivable** if any of its three views shows the fire. It is **front-perceivable** if the front view does,
  and **side-only** if only a side view does.
* A perceivable fire world must not end in a delivery. An imperceptible fire world is reported separately and is not in any
  primary count.

**Arms** (frozen v3.6; nothing is tuned on W).
* Qwen3.5-9B, prompt set `v35`, hazard prompt `h36`, hazard views `tiles` (full image plus three enlarged crops, maximum),
  τ_s = 0.50, τ_h = 0.05, both passes, fail-closed on any inference error or rejected frame.
* **Front-only:** approve iff the front view is approved. An approval needs the requested supply in both passes at ≥ 0.50
  and p(hazard) < τ_h in both passes (`t1_analysis.decide`).
* **Look-around:** approve iff the front view is approved and neither side view has p(hazard) ≥ τ_h in either pass
  (`local_vision.combine_with_look_around` with `mission_memory.peek_hazard`, no memory caution). A side view that errors counts
  as a hazard. Supply answers from side views are ignored, as in the robot.

**Scoring** (`scripts/vlm_devset_eval.py` on `experiments/vlm_testset_w`, tag `w_h36_tiles`; analysis `scripts/w_analysis.py`).

**Primary endpoints** (unit = world; perceivable fire worlds, n expected around 130).
* **W-a1 (look-around helps).** Count *misses* (the check approves although the fire is perceivable) for front-only and for
  look-around. Exact McNemar over worlds. Claim "look-around reduces misses on small hidden fires" only if look-around has fewer
  misses and p < 0.05.
  * By construction look-around misses are a subset of front-only misses, so the second discordant count is 0 and the test is a
    sign test on the caught fires. The informative quantity is endpoint W-a2.
* **W-a2 (ε is small and tightly bounded).** Per-world miss rate of look-around, with Wilson 95% CI. Claim "ε is tightly
  bounded" only if the **Wilson upper bound is ≤ 0.15**. The point estimate and the bound are reported whichever way it goes, with
  `k·ε` for k = 2 stations. For reference, G had 1/16 (upper bound 28%).
* **W-a3 (looking around is affordable).** On the 75 fire-free twins, the fraction of worlds in which the front view approves but
  a side view stops the mission (extra false stops). Claim "acceptable cost" only if the point estimate is **≤ 0.10**. The Wilson CI,
  the correct-approval rates of both arms and the exact McNemar test between them are reported.

**Claims.**
* *"Look-around bounds the miss rate on small hidden fires to ≤ 15% (95%)"* requires W-a1 and W-a2.
* *"…at a bearable false-stop cost"* additionally requires W-a3.
* Otherwise the paper reports the number as measured and says which criterion failed. W-a2 is a precision criterion that I chose
  before seeing data: with n ≈ 130 and a true ε of 6% (G's point estimate) the expected upper bound is about 11%; a true ε of 10%
  gives about 16% and fails.

**Secondary (descriptive).**
* Front-perceivable and side-only subsets; which side caught the fire (left, right, both); the missed worlds by id.
* Hazard test alone at the front (any supply answer).
* Imperceptible fire worlds: how often each arm approves them.
* Sensitivity to τ_h ∈ {0.02, 0.05, 0.10, 0.20} (no threshold is chosen on W).
* v3.5 (h35, full view) on the same images, same two arms (`w_h35_full`).
* **Optional stage r:** the same 3 views of the perceivable fire worlds with an even world number (about 60 worlds) under study R's
  12 degradations (`scripts/w_degraded_eval.py`, `devset_w_r_*.json`): per-condition miss rates of both arms with Wilson CIs.
  Not part of the claims. Run only if time allows.

**Known limits, stated now.**
* Image level: no robot motion, no timing, no controller. The fire is Gazebo's stylised fire, and "perceivable" is a pixel count, not a human judgement.
* The arrival pose error is a measured spread, not a model of the controller. Lighting and prop ranges are those of F/G/H.
* Fires only behind the requested station, as in F/G/H. Fires behind the other station are not tested (the search stops there).
* One model family (Qwen3.5-9B).

## W-b. Closest prior-art baselines on existing images (no new rendering)

**Data.** Existing images and labels only: T1 (600), T2 (600, the held-out test sets), and the development sets DH and DH2
(300 each). T1 and T2 are the test sets; DH and DH2 are used **only for calibration** of the conformal baseline. Scores of
the frozen v3.6 on T2, DH and DH2 exist already, with `h36 + tiles` and with `h36` on the full image
(`devset_{dh,dh2,t2}_i11_h36_{tiles,full}.json`). T1 has not been scored with either and is scored now (`t1_i11_h36_tiles`,
`t1_i11_h36_full`). Labels are those of the files (`expected`, `hazard_visibility`, `fire_pixels`); ambiguous images are
excluded, as in T1/T2.

**Systems.** Every system keeps ours' supply check (both passes name the requested supply with probability ≥ 0.50) and
changes only the hazard rule. A failed inference refuses.
* **Ours-full (matched arm):** the v3.6 hazard wording `h36`, asked on the **full image only**, τ_h = 0.05, same supply check.
  It has the same input as the baselines (one image, no crops), so it isolates the hazard rule: a hand-written small-fire
  wording and a low threshold chosen on development data, versus voting over paraphrases or a conformal set.
* **Ours (deployed v3.6):** `h36 + tiles` (full image plus three enlarged crops, maximum), τ_h = 0.05.
* **VAP-TAMP-style vote** (Oloo et al. 2026, as closely as an offline score allows): five paraphrased yes/no hazard questions
  on the full image. Each answers Yes if p(Yes) ≥ 0.5 (the model's own answer, no threshold tuned). **Refuse if ≥ 3 of 5 say Yes.**
  The questions (`PARAPHRASE_SETS['w5']` in `scripts/local_vlm_server.py`, a new set; no existing prompt, endpoint or
  decision is changed; Q1 is the v3.5 wording verbatim, Q2–Q5 are generic rewordings written before any W inference):
  1. Look at the whole image, including behind and around the objects. Do you see any fire, flames, or smoke? Answer Yes or No.
  2. Is anything in this picture on fire, or is there visible smoke? Answer Yes or No.
  3. Does this image show flames, burning material, or smoke anywhere? Answer Yes or No.
  4. Is there a fire hazard visible in this scene, such as flames or a smoke cloud? Answer Yes or No.
  5. Would a rescuer need to avoid this area because of fire or smoke visible in the image? Answer Yes or No.
  * Variants (secondary): majority at per-question threshold 0.05; any-of-5 at 0.5; mean of the five ≥ 0.05.
* **KnowNo-style conformal set** (Ren et al. 2023) over the hazard answer {Yes, No}, from the score of Q1 (the v3.5 wording,
  full image; the h36 full-image wording is a secondary score).
  * Nonconformity of a label is 1 − p(label). Calibration: the DH and DH2 images with a visible fire (label Yes) or a hidden
    fire (label No); ambiguous images are dropped.
  * Split-conformal quantile q̂ = the ⌈(n+1)(1−α)⌉-th smallest calibration score, for **α = 0.05 and α = 0.10**. If the rank exceeds
    n, q̂ is infinite and the set is {Yes, No}.
  * Prediction set = {y : 1 − p(y) ≤ q̂}. **Refuse unless the set is exactly {No}.** (Sets {Yes}, {Yes, No} and {} all refuse.)
  * Secondary: class-conditional (Mondrian) calibration, which is study K's threshold in the same form.

**Primary endpoints** (T1 and T2 pooled, non-ambiguous images; pairs are images).
The **primary comparison is matched: Ours-full against each baseline** (same input, the full image only).
* **W-b1 (false approvals).** For each of the three primary baselines (vote@0.5, conformal α = 0.05, conformal α = 0.10):
  false approvals on must-refuse images with Wilson CI (and world-cluster bootstrap CI), and the exact McNemar test of Ours-full
  against the baseline on the paired false approvals. P-values are Holm-adjusted over the three comparisons.
* **W-b2 (correct approvals).** Correct approvals on must-approve images with Wilson CI, and the paired exact McNemar test.
* **Verdict per baseline.** *The mechanism matters* only if Ours-full has fewer false approvals, the Holm-adjusted p < 0.05,
  **and** its correct-approval rate is not lower by more than 5 points. If a baseline has no more false approvals than Ours-full,
  the paper says that the baseline is not distinguished (or better) on these images. Both outcomes are reported.

**Secondary comparison: the deployed system (`h36 + tiles`) against the same three baselines**, with the same statistics and
the same Holm adjustment (a separate family of three) and the same verdict rule (`deployed_better`). It answers "what does the
whole deployed check buy over the baselines", not "which hazard rule is better", because the deployed system also sees the crops.
A baseline given the same crops is not part of W; adding it would be an amendment recorded before any W-b inference.

**Secondary (descriptive).**
* Hazard recall on small visible fires (< 10 000 pixels), where v3.6 is weakest and the systems are expected to differ.
* Ours-full against the deployed system: what the tiles add.
* All variants above, and the conformal calibration (n, q̂, empirical coverage on T1/T2, which exchangeability does not guarantee
  because small fires are 27% of the test fires and 7% of the development fires, study K).

## Infrastructure failures
* An inference error (HTTP, non-finite logits) leaves an `error` in the record and counts as a refusal (fail-closed) in every
  system. `scripts/w_eval.sh` re-runs a stage **once in full** if any record has an error and keeps both files
  (`*.attempt1.json`); the second file is analysed. Remaining errors are reported.
* A world with a missing view is reported as incomplete and excluded from all counts.
* A world that fails to render is re-rendered once (the builder is resumable); a world that fails again is excluded and listed.
* The run needs a quiet host: no campaign, no Gazebo, no other GPU job from the start of rendering to `W_EVAL_DONE`.
  `w_render.sh` and `w_eval.sh` refuse to start otherwise and wait for a one-minute load average below 6.
* Neither script starts unless this file and the protocol (and, for evaluation, the analysis scripts) are committed and unchanged.

## Order of work and estimated time (one V100 host, nothing else running)

| Stage | What | Estimate |
|---|---|---|
| 1 | `w_render.sh`: 225 colour worlds + 150 fire-mask worlds = 375 Gazebo launches at ≈ 17 s (9 s start-up, 3 views × 1.6 s, tear-down) | 1.8–2 h |
| 2 | W-a scoring, h36 + tiles, 675 images × 2 passes at ≈ 1.33 s per pass | 0.5 h |
| 3 | W-a reference, v3.5 (h35, full), 675 images × 2 passes at ≈ 0.73 s | 0.3 h |
| 4 | W-b: T1 scored with h36 + tiles (600 images) | 0.45 h |
| 5 | W-b: paraphrase scores, 1 800 images (DH, DH2, T1, T2) × 6 forward passes at ≈ 0.5 s | 1.45 h |
| 5b | W-b: T1 scored with `h36` on the full image (Ours-full; 600 images × 2 passes at ≈ 0.73 s) | 0.25 h |
| 6 | Optional stage r: about 180 images × 12 conditions × 2 passes at 1.33 s | 1.6 h |
| 7 | Analysis (CPU) | minutes |
| | **Total without stage r** (render 2 h + GPU scoring 2.95 h + three model loads) | **≈ 5.2 h** |

Stages 2, 4 and 5 share one server start (`h36 + tiles`); 5b needs a start with `h36 --hazard-views full`, and stage 3 one with `h35 full`.

## Amendments
**Amendment 1 (2026-10-17 21:00, before any W image is rendered or scored; I-20).**
* *Added views.* Every world is also rendered from three extra poses: ±0.8 m beside the waypoint (L2, R2) and 0.3 m closer
  to the station (N). They use the same pose-error model, drawn from a separate random stream (`W-2026-extra-poses`). The
  worlds, lighting, props, fires and the F/L/R poses are byte-identical to the registered protocol, and the generator
  checks this.
* *Primary endpoints and labels are unchanged.* They use F, L and R only.
* *New secondary analysis: suspicion-triggered extra views* (`summarise_adaptive`).
  * If a world passes the fixed look-around but some standard view is *suspicious*, the robot also looks from L2, R2 and N.
    Suspicious means p(hazard) ≥ τ_sus = 0.005 in that view.
  * It refuses if any extra view has p(hazard) ≥ 0.05.
  * τ_sus was fixed on development data only (DH + DH2, h36 + tiles):
    * it is the 90th percentile of the fire-free views (40/380 at or above 0.005);
    * it covers 17 of the 23 visible development fires that were missed at 0.05.
  * Reported:
    * misses of fixed look-around vs adaptive, paired, among worlds perceivable in F/L/R and among worlds perceivable in
      any of the six views;
    * the trigger rate and the extra false stops on the fire-free twins.
  * Hypothesis: adaptive misses fewer fires, with an extra-view trigger rate of about 10% on fire-free worlds.
  * If it holds, the rule is implemented in the robot (I-20) and tested in closed loop in a separate registered study.
* *Time.* Rendering grows to six views per world (about 2.6 h instead of 1.8 h). Scoring of W-a doubles (about 1.0 h).

**Amendment 2 (2026-10-17 22:40, before any W image is rendered or scored; wording and analysis only, from mock review R6 items 2, 3 and 5).**
Nothing about the worlds, the protocol hash, the renders, the models, the thresholds or the scoring changes. Only which numbers are
claim criteria, which are descriptive, and which secondary analyses are added. `scripts/w_analysis.py` and `tests/test_study_w.py`
are updated to match.
* *W-a1 is demoted to descriptive.* "Look-around has fewer misses than front-only" holds by construction (look-around misses are a
  subset of front-only misses, so the McNemar test is a sign test on a subset relation and cannot fail). It is still printed
  (`descriptive_P1_look_around_fewer_misses`) and the counts are reported, but it is no longer a condition of any claim.
* *The upper-bound endpoint stays primary.* W-a2 (Wilson 95% upper bound of the look-around miss rate on the registered
  F/L/R-perceivable fire worlds is at most 0.15) is now the only condition of the claim "ε is tightly bounded"
  (`claim_eps_tight` = W-a2). W-a3 (extra false stops at most 0.10) is unchanged and is still the extra condition of the cost claim.
  The expected-value remark above stands: with n about 130 and a true ε of 6% the expected upper bound is about 11%; a true ε of 10% fails.
* *Six-view perceivability is the leading secondary label set.* A fire world is *six-view perceivable* if any of F, L, R, L2, R2, N
  shows at least 614 fire pixels (the label `world_perceivable_any_view`, already rendered under Amendment 1). The checks are unchanged
  (F, L, R); only the label changes. Reported with Wilson CIs: front-only and look-around miss rates on the six-view perceivable
  worlds, the worlds missed, and the **share of fire worlds that no view shows** (`six_view.share_not_visible_from_any_view`) together
  with what each arm does on them, and the share visible only from the extra views. Whether the upper bound on the six-view label
  stays at or below 0.15 is reported next to the primary result; it is not a criterion, and if it exceeds 0.15 the paper says so in the
  same sentence as the primary result. The main text reports the not-visible share, because a fire hidden from every view is excluded
  from ε by the registered label and is the residual hazard.
* *New secondary analysis: image-level oracle steering.* Proposition 2 is restated with ε_any = P[there exists a must-refuse station
  whose check approves], which does not depend on k or on the visiting order and is attained by an attacker who can choose the order
  and queries the check offline. From the W fire worlds taken as must-refuse stations (one per world) the script reports, for
  k = 1..4, `eps_any(k)` = the probability that at least one of k distinct fire worlds drawn at random is approved (exact,
  hypergeometric), the sum bound min(1, k·ε), and an interval obtained by mapping the Wilson interval of ε through 1−(1−x)^k, for
  front-only and look-around, on both label sets. For k = 1 it equals the per-world miss rate. No criterion; it replaces the
  16-world closed-loop A-steer cell as the steering estimate. Limits, stated now: the k stations come from different worlds, so
  lighting and arrival-pose draws are independent (a depot shares them; XD adds that case), and the rendering distribution is the
  generator's, not an adversary's choice of fire geometry.
* *Unchanged:* W-a2 and W-a3 thresholds, all of W-b, the optional stage r, the Amendment 1 views and its adaptive analysis.
