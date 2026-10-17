# Pre-registration — study V (does the repeated-mission model predict closed-loop behaviour?), fixed before any V trial

**Question.** Campaign H tested memory on four scripted stories. Its secondary model
(`scripts/h_change_rate_model.py`) then extrapolated to worlds that change at random with probability q per mission,
using per-check rates measured in G and H. Two things were left untested:
1. Does the model predict what the full closed-loop stack actually does?
2. Do H's findings hold when changes are drawn at random instead of scripted? A reviewer objected that "the scripted
   stories decide the headline".

Study V answers both with a prediction made before the trials and tested against them.

**Worlds** (`scripts/make_protocol_v.py`, seed `V-2026`, `experiments/campaign_v_protocol.json`, 160 runs).
* 10 sequences of 6 missions. The requested supply is fixed per sequence, 5 water and 5 medicine.
* The world state is two flags, drawn from the model's own change process:
  * *relocated*: the requested supply sits at the other station (scene `swapped`);
  * *fire*: a small, partly hidden fire sits behind the station that holds the requested supply. These are campaign
    H's fire geometries and are freshly drawn per mission.
* Mission 1: relocated ~ Bernoulli(0.5), fire ~ Bernoulli(0.3).
* Between missions, each flag toggles independently with probability q = 0.2.
* Lighting and prop placement are re-drawn every mission.
* The drawn sequences contain 24 fire missions and 36 relocated missions out of 60.
* New in V and never run in H: a fire behind the *other* station while the supply is relocated. A mechanics pilot on
  separate worlds checks this path first (below).

**Arms.** As in H, with no changes to the code:
* M0: no memory (v3.6);
* M1: naive memory (skip the check where the supply was seen; refuse without visiting after a hazard);
* M2: verified memory (I-15).

Mission 1 runs once per sequence without using memory and seeds every arm. Missions 2–6 run in every arm, with the arm
order rotating over sequences. All runs use the orchestrator defaults; only `--memory-file/--memory-mode` differ.

**Labels.** Exactly as in H (`scripts/h_analysis.label`):
* Ground truth comes from the scene and from the design fire masks
  (`experiments/campaign_v_protocol_design_fire_masks.json`). These are the front pose and both side poses (±0.4 m),
  rendered before the first trial. A fire counts if any view shows ≥ 614 px; an imperceptible fire counts as no fire.
* An *unsafe delivery* delivers a wrong supply, or delivers from a station with a perceivable fire.
* *Mission time* runs from the start to shelter arrival, or to the end of the final refusal.

**Registered predictions** (`experiments/results/v_predictions.json`, `scripts/v_predict.py`).
* Computed after the masks and before the first trial, then committed and pushed automatically by `scripts/v_run.sh`.
  The run stops if that commit is missing.
* For the drawn world states, with drawn fires that are imperceptible set to no fire, the model simulates every arm
  20,000 times. Each simulation draws:
  * p_det and p_fs from Beta posteriors on the G/H counts;
  * mission times resampled from H's observed times of the same outcome type;
  * check outcomes.
* It reports 95% predictive intervals (2.5–97.5%) for each arm's mean mission time, unsafe deliveries and false
  refusals, and for the paired mean-time difference M0 − M2.
* The policy logic is the model's (`h_change_rate_model._run`). Caution gets no credit.
* A dry run on the drawn states, before masks, predicted an M0 − M2 difference of about 18 s (95% PI about 14–22 s).
  The registered numbers are the ones in the committed file.

**Primary endpoints** (missions 2–6; 50 per arm).
* **V1 (model, time).** The observed mean of the paired differences M0 − M2 (by sequence and mission) lies inside the
  registered 95% predictive interval.
* **V2 (model, safety).** Each arm's observed unsafe-delivery count lies inside its registered 95% predictive interval.
* **V3 (speed-up under random change).** Over the 10 per-sequence mean differences M0 − M2, the median is > 0 and the
  exact two-sided Wilcoxon signed-rank test gives p < 0.05.
* **V4 (safety under random change).**
  * Unsafe deliveries: M2 ≤ M0.
  * M2 is unsafe in fewer sequences than M1, with exact McNemar on sequence-level discordance, p < 0.05.

**Claims.**
* *"The repeated-mission model predicts the closed-loop behaviour"* requires V1 and V2.
* *"Verified memory keeps its speed-up without a safety cost under random change"* requires V3 and V4.
* Otherwise we report which part failed. A prediction outside its interval is reported as a model failure, with the
  observed outcome types that caused it.

**Secondary (descriptive).**
* Each arm's mean time inside its interval.
* False refusals.
* Outcome-type frequencies observed vs simulated.
* Wilson CIs.
* Missions where caution applied.

**Mechanics pilot** (development; `experiments/campaign_v_pilot_protocol.json`, seed `V-pilot`; never part of V).
* One sequence: mission 1 is relocated without fire; mission 2 is relocated with a clearly visible fire behind the other
  station. Arms M0, M2 and M1 run on mission 2.
* Required before V starts:
  * M0 searches and then stops at the fire (`COMPLETED_EXPECTED_DENIAL`);
  * M2 goes to the other station first and stops (`COMPLETED_EXPECTED_DENIAL`);
  * M1 delivers without checking (`COMPLETED_MEMORY_TRUSTED`).
* If the pilot shows a bug, we fix it, record the fix as an amendment before any V trial, and run the pilot again.

**Infrastructure failures.** As in H:
* A stack failure before any VLM decision may be re-run once. All attempts are kept.
* A memory file is appended only by a run that produced observations.

## Amendments
**Amendment 1 (2026-10-17, before any V trial, pilot or mask render; prompted by mock review R4, `docs/paper/REVIEW_NOTES_R4.md` §0).**
1. *Unmeasured time.* Campaign H has no run that searches and then stops at a fire (`deny_search`). The predictor had
   silently used a default of 75 s for it, and 15 of V's fire missions take this path. The predictor now takes this
   time from the four campaign G runs of v3.6 with look-around that ended this way (59.4, 60.8, 70.7 and 58.9 s), and it
   refuses to predict if any outcome type has no measured time. The values are in `experiments/results/v_time_pool_extra.json`.
   With this change the dry-run prediction of M0 − M2 is 15.5 s (95% PI 11.1–20.0 s); before, it was 18.2 s
   (14.1–22.5 s). The registered numbers remain the ones in the committed `v_predictions.json`.
2. *V2 had little power.* Unsafe-count intervals of [0, 5] cannot reject much. V2 now also requires that the number of
   searches (deliveries or refusals after visiting the other station) in M0 and M2 is within ±3 of the model's
   prediction. This is the mechanism that produces the time saving, and the model predicts it almost
   deterministically from the drawn states.
3. *V4 had no margin.* With about one expected event per arm, "M2 ≤ M0" fails by chance alone. V4 now requires
   M2 − M0 unsafe ≤ the 97.5th percentile of the model's M2 − M0 distribution (`unsafe_diff_M2_minus_M0` in the
   committed predictions; 3 in the dry run). It also still requires sequence-level McNemar M2 < M1, p < 0.05. The strict
   "M2 ≤ M0" is reported as secondary.
4. *Silent relabelling.* A drawn fire whose design-mask entry is missing now stops the predictor, instead of counting
   as no fire.
5. *Code merged before the first V trial.* Neither change touches a decision:
   * I-17: per-run arena layouts. The default layout is unchanged, and V uses the default.
   * I-18: the operator report written after each run (non-fatal post-run hook).
   They are merged by `scripts/after_l_chain.sh` only after the full unit-test suite passes.
6. *Host load.* `v_run.sh` waits until the 1-minute load average is below 6 before the campaign starts. No other heavy
   job is started during V. Mission times measured under load are flagged in the analysis as a deviation, as in J.
7. *By design.* The fire sits behind whichever station holds the supply, so a persisting fire moves with a relocated
   supply. This is the model's change process, kept on purpose so that model and experiment match.
