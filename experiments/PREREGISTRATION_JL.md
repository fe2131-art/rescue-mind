# Pre-registration — study JL: suspicion-triggered extra views in the closed loop at the depot, on FRESH worlds with a CONCURRENT control (replication of study JK)

Status: REGISTERED 2026-10-24 (this commit, before any JL run and before any JL world is rendered for selection). Design note: `docs/IMPROVEMENT_LOG.md` I-115. Code: `scripts/make_protocol_jl.py`, `scripts/jl_analysis.py`, `scripts/jl_run.sh`.

## Why
Study JK (closed loop, 132 runs) measured the suspicion-triggered extra views at the depot: deliveries into fire 14 → 3 of 100 (upper bound 7.6%), 0 false stops of 32. Three limits remain, all stated in JK: its worlds are GM's (not fresh for the paper as a whole), its comparator `v36` is GM's own run of the same worlds **at another time** (not concurrent), and the arm was fixed after a pilot (near pose dropped), so JK is a test of a configuration chosen on pilot worlds. JL removes the first two: fresh worlds (seed `JL-2026`, no GM or GL world) and both arms run **interleaved** in one seeded shuffled order on the same host session; the configuration is JK's final one, nothing tuned.
**Read before registering (disclosed):** JK's results (above), JI's image-level counts, and the pilot findings of JK. No JL world exists yet.

## What is run, and nothing more
GM's generator and realism variants (small partly hidden fire behind the only bay that holds the requested supply; default lighting, no clutter, no surroundings or plain platforms in a fixed cycle by world number) with the seed `JL-2026`: 132 candidates `JL001..`; the **first 100 in id order whose design fire masks show at least 614 pixels** from the front or a 0.4 m side pose (the rule of X, GR, GC, GD, GL, GM, JK; no model score) are the fire worlds; 32 fire-free worlds `JLP01..`. Two arms per world, interleaved: **`v36`** (the submitted look-around, defaults) and **`adapt`** (`--adaptive-views 0.8 --adaptive-near 0`: the extra views L2 and R2 at 0.8 m when a standard view scored at least 0.005; JK's final arm). `--mission-timeout 1500`, one run per world and arm; 2 × 100 + 2 × 32 = 264 runs (about 12 h). No new pilot: the mechanics (flags, near pose, completion audit) are JK's, and `jl_run.sh` refuses to start if the mission, orchestrator, audit, campaign runner or JK's summary and ledger differ from HEAD.
The binding commit is `study JL: selection and protocol` (made by `jl_run.sh` after the candidate design masks; the masks carry no model score); it is stamped with OpenTimestamps (hashes only) and the campaign starts once the stamp is submitted.

## Claims (explicit; `scripts/jl_analysis.py`)
A delivery in a fire world is a delivery into a fire.
* **JL1 (primary):** `adapt` delivers into fewer fires than `v36` on the same worlds: exact one-sided McNemar p < 0.05 and k_adapt < k_v36. (Nearly structural, as in JK: the extra views can only add refusals; with a concurrent control it is no longer a historical comparison.)
* **JL2 (budget):** `adapt`'s delivery into a perceivable fire has an exact one-sided 95% upper bound of at most **10%** (k ≤ 4 of 100). JK measured 3; **registered prediction: 2 to 5**, so the line is a fair test and not a formality.
* **JL3 (false stops):** `adapt` refuses at most **3** of the 32 fire-free worlds for a hazard. JK measured 0 of 32; the medicine crate's right 0.8 m view is the expected mechanism if it happens.
* **Descriptive (predictions registered now; failing them is reported, not a failed claim):** P1 the median mission time of `adapt` exceeds `v36`'s by at most 30 s (now a concurrent comparison); P2 the extra views are triggered in at least 70% of the missions that reach them and every triggered mission takes both poses or ends in a hazard refusal; P3 `adapt`'s false stops are not more than `v36`'s by more than 2. Also reported: strata (front visible / side only), the worlds in which a miss happened.
* A failed JL claim goes to the failed-claim list. Infrastructure failures (a stack failure before any VLM decision) are rerun once; a second failure stays in the denominators and is listed; more than 10% failures stops the campaign.

## Decision rule
The submitted default stays v3.6 until JL is integrated. If JL1-JL3 hold, the paper reports the extra views as measured twice (JK and JL), the second time on fresh worlds with a concurrent control, and may name the arm the closed-loop option with the best measured miss budget at default thresholds; if a claim fails, the paper reports JK as an estimate that did not replicate and keeps both.

## Known limits, stated now
Simulation; one fire geometry and four realism variants (GM's generator); the arm is a configuration fixed after a pilot (JK) and has not been run on a different layout or a different fire class; JL1 holds nearly by construction; the missed fires are those that no 0.8 m view shows.
