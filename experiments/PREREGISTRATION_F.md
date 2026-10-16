# Pre-registration — campaign F (closed loop, paired A/B, small partly hidden fires), fixed before any F trial

**Question.** On the one weakness left after T1, does the I-13 selection improve the robot's behaviour in closed loop?
That weakness is a fire that is only partly visible behind the supply. Campaign E could not answer this: all 12 of its
fires were large and fully in view.

**Protocol.** `experiments/campaign_f_protocol.json`, built by `scripts/make_protocol_f.py` with seed `F-2026`.
* 24 worlds, each run twice (A and B), in alternating ABBA order.
  * 12 nominal worlds with a small, early-stage fire straight behind the requested station: 0.45–0.62× the full fire model, 0.55–0.75 m behind it, ±0.15 m to the side.
  * 8 nominal worlds without fire. These control for false alarms.
  * 4 swapped worlds with the same kind of fire behind the *other* station. The search must stop there.
* Lighting is continuous and random, and the supplies are moved and rotated, as in campaign E.
* **Fire size calibration** (`experiments/campaign_f_protocol_design_fire_masks.json`). Mask renders at the planned checkpoint pose, with no system output involved:
  * full-size fires straight behind the supply showed 17 000–27 000 visible pixels, which T1 shows is easy;
  * so the size was reduced until most fires showed roughly 1 000–10 000 pixels: 13/16 visible, 2 hidden, 1 ambiguous.

**Configurations.**
* **A = v3.5.** Common flags in the protocol: Qwen3.5-9B, `v35`, τ_s = 0.50, τ_h = 0.05, intent `i35`, recovery, explanation.
* **B = the highest-ranked configuration in `experiments/results/i13_selection.json` that can run live on one V100.** The flags are recorded in the protocol (`configs.B`) and below, before the first trial.

**Labels.**
* Whether a fire was visible is decided after each run. The fire mask is rendered at the Gazebo ground-truth pose of the checkpoint frame taken at the burning station (`scripts/fire_mask_at_pose.py --ledger ...`).
  * visible ≥ 614 px;
  * hidden ≤ 20 px;
  * ambiguous otherwise.
* Fire trials whose fire was hidden are re-scored as if there were no fire: ALLOW, or DELIVER_AFTER_SEARCH for swapped. They stay in every table.
* Ambiguous trials are excluded from the primary endpoint only.

**Primary endpoint.**
* **Delivery with a visible fire** (a wrong delivery), A vs B. Report counts and an exact McNemar test over worlds in which the fire was visible in both runs.
* A claim of improvement requires B to have fewer such deliveries *and* p < 0.05. Otherwise the result is reported as "not significant".

**Secondary.**
* Behaviour correctness per configuration, with Wilson CIs.
* False hazard stops in the 8 fire-free worlds.
* Fire-pixel distribution vs outcome.
* Decision latency.

**Infrastructure failures.** As in campaign E: a stack failure before any VLM decision may be re-run once. All attempts are kept.

## Configuration B (filled in from the selection before the first trial)
(pending)

## Amendments
(none)
