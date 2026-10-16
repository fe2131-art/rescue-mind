# Pre-registration — campaign G (closed loop, paired): does looking from the side (I-14) catch partly hidden fires?

Fixed before any G trial, after campaign F.

**Background.**
* In campaign F, configuration B (v3.5 + hidden-fire wording + crops) still delivered past 7 of 13 small fires that were visible at the checkpoint.
* Those fires showed only 1 100–2 400 pixels from the front. The model's hazard probabilities (≈0.003) overlap those of fire-free views, so no threshold can separate them.
* Mask renders of F's worlds show that the same fires are 4 600–22 000 pixels large from a pose 0.4 m to the left or right of the checkpoint.
* I-14 therefore makes the robot look again from both sides after an approval. Any hazard seen there turns the approval into a hazard refusal, and the robot does not search.
* F's worlds were used to design this. G uses **new worlds** from the same distribution.

**Protocol.** `experiments/campaign_g_protocol.json` (sha256 `ce85d37abce45779…`; `scripts/make_protocol_g.py`, seed `G-2026`).
* 24 worlds:
  * 12 with a small fire straight behind the requested station;
  * 8 fire-free;
  * 4 with the fire behind the *other* station.
* Each world is run twice, alternating BC/CB:
  * **B** = `--hazard-prompt h36 --hazard-views tiles`, the same as F's B;
  * **C** = B + `--look-around 0.4`.
* The common flags are stored in the protocol: Qwen3.5-9B, `v35`, τ_s 0.50, τ_h 0.05, intent `i35`, recovery, explanation.

**World-level fire label** (fixed before the first trial: `experiments/campaign_g_protocol_design_fire_masks.json`).
* Magenta-mask pixels are rendered at the canonical front checkpoint pose and at the two side poses (±0.4 m), each facing the station.
* A fire world counts as **perceivable** if any of the three views shows at least 614 pixels.

**Primary endpoint.**
* Over the worlds with a perceivable fire, count *deliveries despite the fire* for B and for C.
* Test them with the exact McNemar test over worlds.
* Claim an improvement only if C has fewer such deliveries and p < 0.05. Otherwise report "not significant".

**Secondary.**
* The subset of fires visible from the front.
* False hazard stops in the fire-free worlds (C must not refuse correct deliveries because of side views).
* Behaviour correctness per configuration, with Wilson CIs.
* Mission wall time and the extra time of the look-around.
* Side-view hazard probabilities.

**Infrastructure failures.** A stack failure before any VLM decision may be re-run once. All attempts are kept.

## Amendments
**Amendment 1 (before any G trial).** The I-14 mechanics pilot (`experiments/results/i14_pilot_ledger.jsonl`) ran on F worlds and E pilot worlds, which are development data. In one fire-free run the robot delivered correctly, but the completion audit rejected the run: the side-view arrival events had been logged as mission waypoint arrivals. They are now logged as `look_around_arrival` without the `arrived` flag. After the fix, all three approval paths passed every audit (plain, box and deliver-after-search). The G protocol and the configurations are unchanged.
