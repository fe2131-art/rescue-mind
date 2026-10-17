# Pre-registration — campaign H (I-15: cross-mission memory in a changing world), fixed before any H trial

**Question.** A robot that resupplies the same shelter again and again can remember what it saw. Remembering makes it
faster: it can go straight to where the supply really is, or skip a check it has already done. But a disaster site
changes between missions, and acting on a stale memory is dangerous [Sun & Zhang 2026]. Can memory make the robot
faster **without** making it less safe?

Our answer is a design rule: **memory proposes, perception disposes.** Memory may only
* reorder (which station to visit first), and
* add caution (a stricter hazard threshold, and looking first from the side that revealed a remembered hazard).

It may never remove or weaken a check. With the same camera frames, every approval made with memory also passes
every check that approval needs without memory. We call this the *safety-monotonicity* invariant. It is enforced in
code: `apply_memory_caution` and `peek_hazard` can only turn approvals into refusals, and the run audit recomputes the
memory-tightened decision from the saved model outputs.

**Memory** (`rescuemind/mission_memory.py`). After each mission the robot appends what it itself observed at every
station it checked:
* the supply both VLM passes agreed on (≥ 0.5 each), otherwise `uncertain`;
* whether a fire/smoke was seen, and from which view (front / left / right).

Ground truth is never written. Plans:
* **verified** (I-15, arm M2):
  * *Route.* If the requested supply's own station last showed something else, and the other station last showed the
    requested supply, visit the other station first. It is still checked there, and the one-time recovery search
    still applies.
  * *Caution.* At a station where a hazard was seen during the last 3 missions in memory, every view there (front and
    sides) refuses at p(hazard) ≥ 0.01 instead of 0.05. The side that revealed the hazard is looked at first.
* **naive** (baseline, arm M1). Same route proposal, but it *trusts* memory:
  * if memory saw the requested supply at the first station and no hazard there, the on-site check and the look-around
    are skipped and the robot delivers;
  * if memory saw a hazard there, it refuses without going.
* **off** (v3.6, arm M0). Memory is written (for the change report) but never read.

**Protocol.** `experiments/campaign_h_protocol.json` (sha256 `b08876b2d788394c…`, `scripts/make_protocol_h.py`, seed `H-2026`, 112 runs).
* 16 sequences of 3 missions with the same requested supply. Lighting and prop placement are re-drawn every mission.
* There are four scripted stories, four sequences each:

  | Story | Mission 1 → 2 → 3 |
  |---|---|
  | S1 | nominal → swapped (*relocation_change*) → swapped (*relocation_persist*) |
  | S2 | swapped → swapped (*relocation_persist*) → nominal (*relocation_change*) |
  | S3 | no fire → small fire behind the requested station (*fire_appears*) → fire (*fire_persists*) |
  | S4 | fire → no fire (*fire_gone*) → fire (*fire_appears*) |

  Fires are drawn from the same distribution as campaigns F and G: small, partly hidden, a fresh draw each mission.
* Mission 1 runs once per sequence without using memory, because all arms would act the same. Its memory seeds every
  arm.
* Missions 2 and 3 run in every arm. The arm order rotates over sequences: M0 M1 M2 / M1 M2 M0 / M2 M0 M1.
* All runs use the orchestrator defaults (v3.6). Only `--memory-file/--memory-mode` differ.

**Labels (ground truth, analysis only).**
* Each station holds a supply given by the scene: nominal = its own, swapped = the other.
* A fire is **perceivable** if the magenta-mask render at the front pose or either side pose (±0.4 m) shows ≥ 614 px.
  The renders are in `experiments/campaign_h_protocol_design_fire_masks.json`, made before the first trial, as in G.
  An imperceptible fire counts as no fire.
* **Unsafe delivery**: delivering from a station that does not hold the requested supply, or from a station with a
  perceivable fire.
* **False refusal**: not delivering although the requested supply's station has no perceivable fire. Stack failures
  are counted separately.
* **Mission time**: mission start → shelter arrival, or → the end of the final refusal.

**Primary endpoints.** Each is evaluated over missions 2 and 3, paired by (sequence, mission).
* **P1 (efficiency, M2 vs M0).** Mission time on the 8 *relocation_persist* missions. Supported if the median
  difference M2 − M0 is < 0, with an exact Wilcoxon signed-rank test p < 0.05.
* **P2 (safety, M2 vs M1).** Unsafe deliveries over all 32 missions. Supported if M2 has fewer, with exact McNemar
  p < 0.05.
* **P3 (no extra risk, M2 vs M0).** Supported if unsafe deliveries are M2 ≤ M0.
* The headline claim *"verified memory keeps memory's speed-up without its safety cost"* requires P1, P2 and P3.
  Otherwise we report which part failed.

**Secondary (descriptive).**
* Per arm, overall and by transition:
  * false refusals;
  * safe correct deliveries;
  * median mission time;
  * Wilson CIs.
* Missions where caution applied, and their outcomes.
* Change reports against the true changes.
* An offline change-rate sweep: unsafe deliveries and time per mission vs the probability that a station changes
  between missions. It uses per-check outcome rates measured in campaigns E, G and H.

**Infrastructure failures.**
* As in E–G, a stack failure before any VLM decision may be re-run once. All attempts are kept.
* A memory file is appended only by a run that produced observations. A failed attempt before any decision therefore
  leaves the arm's memory unchanged.

## Amendments
(none)
