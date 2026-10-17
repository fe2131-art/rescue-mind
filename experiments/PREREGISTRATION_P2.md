# Pre-registration — study P2 (site calibration of the hazard threshold on real photographs), fixed before any P2 inference

**Motivation (from study P).** On 400 real D-Fire photographs, the frozen v3.6 hazard question (h36 wording, crops,
τ_h = 0.05) flagged 298/300 fire or smoke images, but also 64/100 fire-free ones. The fire-free ones are mostly hard
negatives: haze, low cloud, a lens smudge, red sunset clouds, glowing tents. A deployment would calibrate the threshold on
local fire-free images. P2 tests whether that procedure works **on images it was not calibrated on**.

**Data** (D-Fire, CC0, the Hugging Face mirror used in P).
* **Calibration set:** 200 fire-free and 200 fire/smoke images (smoke-only, fire-only and both, ~67 each) from the
  **train** split, seed `P2-cal`.
* **Test set:** 400 images from the **test** split, stratified like P (100 per category), seed `P2-test`. They are
  disjoint from P's sample.

**Arms.** Qwen3.5-9B with crops (max over the full image and three crops), two wordings:
* **W36:** v3.6's `h36` ("... smoke (a grey or black cloud), even if it is small ...");
* **W35:** v3.5's `h35`, which does not mention clouds.

**Calibration rule (calibration set only).**
1. For each wording, choose the **largest** τ_h in {0.01, 0.02, 0.05, 0.1, 0.15, …, 0.95} whose calibration recall on
   fire/smoke images is ≥ 0.95. The safety constraint comes first.
2. Then choose the wording with the lower calibration false-alarm rate at its τ_h. Ties go to W36, the deployed wording.

**Endpoints on the test set (Wilson 95% CIs).**
* False-alarm rate on the 100 fire-free images, and recall on the 300 fire/smoke images, for the chosen configuration.
* Also both wordings at their own calibrated τ_h, and at the frozen τ_h = 0.05.

**Claim.** "Site calibration makes the hazard question usable on real photographs" is supported if the chosen
configuration's test recall is ≥ 0.90 (point estimate) **and** its test false-alarm rate is ≤ 0.20 (point estimate).
Otherwise we report which constraint failed.

**Scope.** The simulator system and all closed-loop results are unchanged. P2 measures a deployment procedure, not the
evaluated robot.

## Amendments
(none)
