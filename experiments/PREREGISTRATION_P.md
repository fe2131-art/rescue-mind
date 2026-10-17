# Pre-registration — study P (real photographs: does the hazard question transfer?), fixed before any P inference

**Question.** Every image the robot's VLM saw so far was rendered by Gazebo, and the "fire" was a stylised particle
effect. Does the v3.6 hazard question flag **real** fire and smoke, and how often does it raise a false alarm on real
fire-free photographs? This part of the sim-to-real gap can be measured offline without a robot.

**Data.** D-Fire [Venâncio et al., Neural Computing and Applications 2022], CC0 1.0. We use the public test split, via
the Hugging Face mirror `badsaarow/d-fire` (`data/test-*.parquet`, 4 306 images, YOLO labels: class 0 = smoke,
1 = fire).
* The class ids were inferred from the published per-category counts: only-smoke 1 186 and only-fire 220 test images
  match the dataset's 27% / 5% shares.
* Images are cached outside the repository and are never committed. Only file names and scores are stored.
* Stratified sample, seed `P-2026` (`scripts/p_realphoto_eval.py`): 100 images with no box (`none`), 100 smoke-only,
  100 fire-only, and 100 with both. That is 400 images.

**System.** The v3.6 hazard question (Qwen3.5-9B, wording h36, full image plus three enlarged crops, maximum),
thresholded at the frozen τ_h = 0.05, exactly as on the robot. The supply questions are asked too, as part of the same
call, but are not evaluated: there is no supply platform in these images. Secondary: Clef-Flash with the task-worded
request, hazard probability ≥ 0.05, run when the GPU is free.

**Endpoints (descriptive, Wilson 95% CIs).**
* **Recall:** the share of the 300 images with fire or smoke that are flagged. Also reported per category and by the
  tercile of the largest box area.
* **False alarms:** the share of the 100 `none` images that are flagged.

No threshold or prompt is changed on the basis of P. If recall is low on real images, that is a limitation of the
system, and it is reported as such.

## Amendments
(none)
