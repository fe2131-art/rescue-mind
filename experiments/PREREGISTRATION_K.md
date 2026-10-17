# Pre-registration — study K (conformal calibration of the hazard threshold), fixed before any K result is computed

**Question.** The frozen hazard threshold τ_h = 0.05 was set by hand and carries no statistical guarantee. A KnowNo-style
conformal calibration can choose τ_h from stored scores so that the *miss rate on visible fires* is bounded. Does such a
threshold, calibrated on development data, keep its bound on the held-out set, and what does it cost in false alarms?

**Offline only.** Study K uses stored per-image scores. No GPU, no new inference, no new images.

## Data (all already scored; no K-specific scoring)
* **Score.** p_h = `passes["1"].scores.hazard_prob` of the v3.6 configuration `Q9B[h36_tiles]` (Qwen3.5-9B, hazard wording
  `h36`, full frame plus three enlarged crops). This is the maximum of the four view probabilities; pass 2 reuses the same
  value. The frozen rule flags a hazard iff p_h ≥ τ_h (`scripts/i13_select.py: q_allows`).
* **Calibration set (development).** Images with `hazard_visibility == "visible"` in `devset_dh_i11_h36_tiles.json` and
  `devset_dh2_i11_h36_tiles.json` (v1 and v2 contain no fire). Expected n = 99 + 112 = 211. "Visible" is the per-image
  label (≥ 614 fire pixels in that view, the mask rule of the T1 registration).
* **Held-out evaluation set.** `devset_t2_i11_h36_tiles.json` only. A v3.6 (`h36_tiles`) run of T1 does not exist (T1 was
  scored with the h35 wording), and T1 has already been used for analysis, so K does not use it.
  * **E-fire:** T2 images with `hazard_visibility == "visible"` (expected 76).
  * **E-free:** T2 fire-free must-approve images: `hazard_visibility == "hidden"` and `expected == "allow"` (expected 193).
* Ambiguous-visibility images are excluded everywhere. T2 is not used to choose anything.

## Method (split conformal, one-sided)
Let s_(1) ≤ … ≤ s_(n) be the sorted calibration fire scores. A fire is **missed** at threshold τ iff p_h < τ (not flagged).
For an exchangeable new fire score, its rank among the n+1 scores is uniform, so for τ = s_(k):

  P(miss) = P(s_new < s_(k)) ≤ (k − 1)/(n + 1)   (ties only lower this).

Two threshold rules, each for α ∈ {0.05, 0.10}:
* **K-marginal (finite-sample split conformal).** k = ⌊α(n+1)⌋ + 1 and τ = s_(k). Then P(miss) ≤ ⌊α(n+1)⌋/(n+1) ≤ α,
  marginally over calibration and test draws. This is the tightest valid k of the standard rule. (A conservative variant
  with k = ⌊α(n+1)⌋ is also reported, as K-marginal-1; it is not used for claims.)
* **K-PAC (training-conditional, δ = 0.10).** Given the calibration set, the miss probability F(τ) at τ = s_(k) satisfies
  F(s_(k)) ~ Beta(k, n+1−k) for continuous scores. Take the largest k ≥ 1 with BetaCDF(α; k, n+1−k) ≥ 1 − δ, and
  τ = s_(k). If no such k exists, τ = 0 (flag everything). Then, with probability ≥ 1 − δ over the calibration set,
  P(miss) ≤ α.

K-PAC is the primary rule (it states the "≥ 1 − δ" guarantee); K-marginal is secondary. Both are reported in full.
The flag rule is always "hazard iff p_h ≥ τ", the same direction as the frozen τ_h.

## Evaluation (per α, per rule, and for the frozen τ_h = 0.05)
* **Miss rate** on E-fire: fires with p_h < τ, with Wilson 95% CI (same `wilson` as `scripts/t1_analysis.py`).
* **False-alarm rate** on E-free: fire-free must-approve images with p_h ≥ τ, with Wilson 95% CI. Because a lost approval
  can also come from the supply check, we additionally report the **correct-approval rate** on all T2 must-approve images
  (`expected == "allow"`, n = 193) when τ_h in `q_allows` is replaced by τ.
* **Also reported:** the in-sample (calibration) miss rate, and the number of T2 fire-free must-refuse images approved
  (false approvals over all T2 must-refuse images, `expected == "deny"`) at each τ, as context. For descriptive
  context on exchangeability we report the fraction of fires below 10 000 fire pixels in the calibration set and in E-fire.

## Pre-specified interpretation
* **The guarantee holds on held-out data** for a given τ iff the held-out miss rate on E-fire (point estimate) is ≤ α.
  The Wilson upper bound is reported but not used for the rule.
* **Exchangeability is violated by design.** The calibration fires come from the DH and DH2 development sets, DH2 being
  deliberately enriched for small early-stage fires; T2 is a fresh draw from the T1 distribution, with a different
  small-fire mix. A held-out miss rate above α is therefore *informative about the distribution shift*, not a failure of
  the conformal argument, and is reported as such. Conversely a held-out miss rate ≤ α is reported as "holds on this
  shift", not as a general guarantee.
* **Comparison with the frozen τ_h = 0.05** is descriptive: the claim "calibrated threshold dominates" is made only if it
  has a lower or equal held-out miss rate and a false-alarm rate that is not higher; otherwise the trade-off is reported
  as is. No threshold in the system is changed by this study; K does not alter any registered configuration.

## Integrity
Results are not dropped. A bug found after the first K run is documented as an amendment and all K outputs are re-run.
The analysis code is `scripts/k_conformal.py`, written after this file is committed; output `experiments/results/k_summary.json`.
