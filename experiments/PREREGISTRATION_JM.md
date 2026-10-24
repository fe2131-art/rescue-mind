# Pre-registration — study JM: a paired smoke-plume ablation (is the residual miss concentrated in worlds with a smoke plume?)

Status: REGISTERED 2026-10-24 (this commit, before any JM world is selected or rendered). Design note: `docs/IMPROVEMENT_LOG.md` I-121.

## Why
Post hoc, on the 100 fire worlds of GM and JK, every residual miss of the two best arms lies in a world with a smoke plume: v3.6 10/54 with a plume against 4/46 without, the left-only arm 5/54 against 0/46, the extra views 3/54 against 0/46 (`smoke_strata.json`; Fisher p = 0.25, 0.06, 0.25). The plume was drawn at random per world, so plume and geometry are not separated and the counts are small. The literature scouts (SmokeBench: smoke volume matters more than contrast; the hazard question may react to haze-like texture) named smoke density as the environment factor not yet varied on purpose. JM varies it on purpose, in twin pairs.
**Read before registering (disclosed):** the post hoc counts above; no JM world exists yet.

## What is run, and nothing more
GM's generator and realism variants with the seed `JM-2026` (72 candidates `JM001..`; no earlier world is reused). The **first 60 in id order whose design fire masks show at least 614 pixels** (front or a 0.4 m side pose; no model score; the masks are fire-only, so the plume does not enter the selection) are the fire worlds. Each selected world is run as a **twin pair that differs only in the smoke plume**: `<id>S` (`depot.particle_smoke` true) and `<id>N` (false); every other key of the world specification is identical (checked by a test). Two arms per twin, interleaved in one seeded shuffled order: **`v36`** (the submitted look-around) and **`adapt`** (`--adaptive-views 0.8 --adaptive-near 0`: JK's final arm). 60 × 2 × 2 = 240 runs (about 11 h), `--mission-timeout 1500`. No new pilot (the mechanics are JK's; `jm_run.sh` refuses to start if the mission, orchestrator, audit, runner, or the JK/JL code and JK results differ from HEAD). The binding commit is `study JM: selection and protocol` (made by `jm_run.sh` after the candidate design masks), stamped with OpenTimestamps (hashes only); the campaign starts once the stamp is submitted.

## Claims (explicit; `scripts/jm_analysis.py`)
A delivery in a fire world is a delivery into a fire.
* **JM1 (primary):** the plume increases the submitted look-around's misses: over the 60 twin pairs, `v36` delivered into the fire in the S twin but not the N twin more often than the reverse; exact one-sided McNemar p < 0.05. (Prediction: about 8 against 2.)
* **JM2:** among the S worlds the extra views reduce the misses of `v36`: exact one-sided McNemar p < 0.05 and fewer for `adapt`.
* **JM3 (budget in the hardest stratum):** `adapt`'s delivery into the fire in the S worlds is at most **4 of 60** (exact one-sided 95% upper bound 13.6%). JK measured 3 of 54 in the plume worlds.
* **Descriptive (predictions registered now; failing them is reported, not a failed claim):** P1 `adapt` delivers into the fire in at most 1 of the 60 N worlds; P2 the extra views are triggered in a larger share of the missions that reach them in S worlds than in N worlds (the plume raises the standard views' scores); P3 the median mission time of `adapt` exceeds `v36`'s by at most 30 s. Also reported: the paired smoke effect for `adapt`, and `adapt` against `v36` in the N worlds.
* A failed JM claim goes to the failed-claim list. Infrastructure failures (before any VLM decision) are rerun once; a second failure stays in the denominators and is listed; more than 10% failures stops the campaign.

## Decision rule
If JM1 holds the paper says that a smoke plume is a hard factor for the submitted look-around and states the size; if JM2 and JM3 hold the extra views are shown to carry the plume stratum; if JM1 fails the post hoc concentration is reported as chance. Whatever happens the submitted default stays v3.6 until integrated.

## Known limits, stated now
One plume model (a particle emitter above the fire) and one fire geometry; only plume present or absent, not density (a density ablation needs a plume parameter the generator does not vary); the arm is JK's configuration fixed after its pilot; 60 pairs give low power for a difference of a few worlds; simulation.
