# Pre-registration — study GM (does the GL result transfer to depot worlds with one realism feature switched off? closed loop, fresh worlds), fixed before any GM design mask is rendered and before any GM trial

It becomes the registration when it is committed on `main` together with `scripts/make_protocol_gm.py`, `scripts/gm_analysis.py`, `scripts/gm_run.sh` and `tests/test_study_gm.py`, **before any design mask is rendered**.
The binding commit for the protocol is the one that adds the selection and the protocol (`study GM: selection and protocol`, made by `scripts/gm_run.sh` after the candidate design masks; the masks carry no model score). The mechanics pilot ledger is committed after it
(`study GM: registration (pilot ledger)`) and stamped with OpenTimestamps (hashes only). Start rule as GC Note 3: the campaign starts once the stamp is submitted; the paper claims an external ordering for GM only if the stamp is attested when the results are analysed.
`scripts/gm_run.sh` waits for the QI/QJ image jobs and takes `/tmp/rescuemind_campaign.lock`. Design note: `docs/IMPROVEMENT_LOG.md` I-92.

## Why GM exists (and what was seen before registering — disclosed)
GL is the only closed-loop miss reduction of the paper (depot, fresh worlds: 20/120 -> 6/120, paired one-sided p = 0.00066), and the paper calls it a **site-specific option** because the arm was fitted to the generator that produced the idea (crate orientation, the one depot layout, one lighting model).
The obvious reviewer question is whether the effect is an artifact of that exact rendering. GM asks it with the realism switches the paper already has: each world has **one realism feature of XD's ablation set switched off** (default lighting, no clutter, no surroundings, plain platforms), the **threshold is not recalibrated** (`experiments/gl_site_cal.json`, 0.028),
and the worlds are fresh (seed `GM-2026`, nothing shared with GD, GV, GVD, GL or the calibration worlds).
Seen before registering: GL's results (all of them); XD's image-level ablation scores of the same four features (the frozen gate's scores on 0.4 m views; no 0.8 m view and no closed loop). No GM datum exists. The sentence that the left arm is "site-specific" stays in the paper whatever GM finds; GM can only widen or narrow it.

## What GM runs, and nothing more (wording frozen)
**Worlds:** the generator of GL (`make_protocol_gl.py`: four-bay depot, requested supply at its first inventory bay only, a small partly hidden fire behind it: back 0.55-0.75 m, lateral +-0.15 m, scale 0.45-0.62), seed `GM-2026`, candidates `GM001`..`GM132`, fire-free `GMP01`..`GMP32`.
The variant is a function of the world number (`variant_of`: number-1 mod 4 over default_light, no_clutter, no_surroundings, plain_platforms) and is applied after the world is drawn, as `make_protocol_xd.ablation_world` does, so the random stream is the generator's own.
**Selection (before any model score):** each candidate's fire is rendered alone at the bay (`scripts/fire_mask_at_pose.py --design --design-sides 0.4`); the **first 100 in id order** whose front or a 0.4 m side mask shows at least **614 fire pixels** are the fire worlds (the rule of X, Y, GR, GC, GD, GV, GL). Fewer eligible means a smaller cell, never padded; the variants are therefore not exactly balanced and are reported by count.
**Arms** (one run per world and arm; world and arm order are seeded shuffles; common argument `--mission-timeout 1500`, delivery interlock off, no advice, no memory):
| arm | flags | worlds |
|---|---|---|
| `v36` | none (the submitted v3.6: look-around 0.4 m both sides, tau_h 0.05) | fire and fire-free worlds |
| `left` | `--look-around 0.8 --look-around-sides L --site-config experiments/gl_site_cal.json` (tau_h 0.028, h36, tiles) | fire and fire-free worlds |
Total 2 x 100 + 2 x 32 = 264 runs if 100 qualify. **No recalibration:** the threshold is the one calibrated on the standard (all features on) clean worlds, so a shift of the clean score distribution under a variant shows up as false stops.
**Confound, stated:** `left` changes geometry and threshold at once (as in GL); the threshold-only control is GD's `cal` arm (5/40 against 5/40).

## Endpoints and claims (explicit; `scripts/gm_analysis.py`)
A delivery in a fire world is a delivery into a fire. Runs that fail for infrastructure reasons are excluded from the claims and listed.
* **GM1 — paired reduction (primary).** The exact **one-sided** McNemar test over fire worlds (`v36` unsafe only against `left` unsafe only) gives **p < 0.05** and k_left < k_v36.
* **GM2 — budget.** `left` delivered into a perceivable fire in k of n worlds; the exact one-sided 95% Clopper-Pearson upper bound is **at most 15%** (n = 100: k <= 8, 13.97%; k = 9 gives 15.2%). The line is looser than GL's 10% because the variants may lower the camera's recall and the study is a transfer test, not a re-estimate.
* **GM3 — false stops.** `left` refuses at most **3** of the 32 fire-free worlds for a hazard (the rank rule bounds the per-mission rate at 2% under exchangeability, which the variants may break: 0.6 expected, 3 allowed).
* **Descriptive (predictions registered; failing them is reported, not a failed claim).** P1: `left` has at most 2 more false stops than `v36`. P2: the median mission time of `left` is at most 20 s above `v36`'s. The per-variant table (unsafe per arm and false stops per arm for each of the four variants), the strata (front visible / side only; fire visible from the left pose or not), the worlds in which a miss happened, the paired counts.
**Power (stated now, simulation of the exact one-sided McNemar test):** with v36 at 15% and `left` at 5%, n = 100 gives 98% power if `left`'s misses are a subset of `v36`'s and 71% if they are independent; at 12% -> 6%: 74% / 38%. The expected truth is between the two cases; **a GM1 failure is reported as "not established under the variants" with the paired counts**, not as evidence of no effect.
**Success is not "0 unsafe".** A failed GM1, GM2 or GM3 is listed in the failed-claim list. **Cause taxonomy (fixed now, as GL):** (a) perception outcome, (b) navigation stall or timeout, (c) infrastructure fault, (d) other. A deviation of class (d), or one whose record does not support its cause, blocks the paper's sentence about the left arm's miss rate under the variants.

## Decision rule for the system
Whatever GM finds, the default stays v3.6. If GM1 and GM2 hold, the paper says that the left-only look-around reduced the depot misses in two sets of worlds (standard and with one realism feature off) without recalibration, and keeps the site-specific wording about the layout; if a variant breaks it, the per-variant table says which feature the arm depends on.
If GM1 fails, the paper says that GL's reduction did not transfer to the variants (and which variants), and GL's sentence is qualified accordingly.

## Mechanics pilot (development, 2 runs on two worlds that are never part of GM)
`GMQ1`: a large fire (the big-fire geometry of X-a) at the first inventory bay on **plain platforms**; its design mask must show at least 614 pixels at the front pose. `GMQ2`: fire-free, **no surroundings** (the outcome is recorded, not gated). Required before GM starts (`python3 scripts/gm_analysis.py --pilot`): both runs end in a defined state, `left` refuses `GMQ1` for a hazard,
every run that has a look-around record scheduled only the left point and took at most the left peek, no audit failure. A bug found there is fixed and recorded as an amendment before any GM trial.

## Infrastructure failures, stop rule
As GL: a trial whose stack failed before any VLM decision is re-run once; a second failure stays in the denominators and is listed. If more than 10% of the runs fail for infrastructure reasons the campaign stops. Runs need a quiet host (one-minute load average below 6): **no scoring, download, build or video render runs during GM**.

## Cost
About 2.5-3 min per run: about 12-13 h for 264 runs, plus candidate masks (133) and the pilot.

## Known limits, stated now
Simulation; one depot layout generator; four realism switches (each *removes* detail, so the variants are simpler worlds in one sense and different in another: the gate's clean tail moves with the background); a stylized fire behind the only bay that holds the requested supply; the hard class only; the threshold is not recalibrated; the eligibility rule counts fires the left arm cannot see;
about 100 worlds give 38-98% power depending on how the misses overlap; GL and GM are not independent evidence about the generator (same crates, same fire geometry), only about the rendering.

## Amendment 1 (2026-10-23 12:30; after 24 of 264 trials, before any outcome was analysed)
**Defect:** the `default_light` variant was implemented as XD's image builder does it (`spec['lighting'] = 'default'`), but `lighting` is not a `world_spec` key of the closed-loop orchestrator (`scripts/v32_orchestrate.py WORLD_SPEC_KEYS`): every one of the six `default_light` fire worlds and fire-free worlds that had come up so far (12 runs, both arms) ended with orchestrator exit 2 after 0.2 s (`NO_RUN_DIR`), no stack, no model, no outcome. The registered mechanics pilot (plain platforms, no surroundings) did not exercise this variant. The failures are a defect of the generator, not an infrastructure failure of the study, and no run of the other three variants was affected (12 failures of 36 rows, all in that variant).
**Change:** `apply_variant('default_light')` now only removes `lighting_params` (the orchestrator's default lighting); the protocol and candidate files were regenerated (only the world specs of the `default_light` worlds change; the fire geometry, the selection and the design masks do not). The 12 failed rows were moved out of the active ledger into `experiments/results/campaign_GM_ledger_attempt1.jsonl` (the complete attempt-1 ledger, kept as evidence); the 12 trials run again under the registered protocol; nothing else is touched. No claim, threshold, arm or analysis changes. A GM trial of that variant that fails again after this fix is an ordinary infrastructure failure under the stop rule (more than 10% of the runs stops the campaign).

## Erratum (times)

Appended 2026-10-24; the registered text above is not edited. The time written in the heading of Amendment 1 ("2026-10-23 12:30") is later than the time of the commit that introduced it, `e3fa4a1` (2026-10-23 12:21 JST). The binding time is the commit time; it precedes the first GM results commit (`2e944c8`).
