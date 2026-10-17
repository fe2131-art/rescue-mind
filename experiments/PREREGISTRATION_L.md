# Pre-registration — study L (does v3.6 generalise to unseen arena layouts?), fixed before any L trial

**Question.** Every earlier closed-loop study used one fixed arena layout: two supply stations at (±2, 2) and the
shelter at (3, −2). Lighting, props, distractors and fires varied, but the geometry did not. Do the closed-loop
behaviour and its audits hold when the stations and the shelter are placed somewhere else?

**Layouts** (`rescuemind/layout.py`, `sample_layout`, seed `L-2026`).
* 24 layouts. Each samples both stations and the shelter within the arena bounds.
* The feasibility constraints are fixed in code (`rescuemind/layout.py`) before this registration:
  * station and shelter centres 2.2-4.0 m from the start, |x| <= 4.5 m, |y| <= 3.5 m, yaw within +/-45 deg;
  * bearings from the start at least 40 deg apart, centres at least 2.5 m apart;
  * approach waypoint = centre moved 1.2 m toward the start; waypoints at least 1.5 m apart and at least 1.0 m
    from the start; each station waypoint at least 1.0 m from the shelter waypoint (look-around points 1.2 m);
  * every straight leg the controller may drive (start, station waypoints, look-around points, shelter) stays at
    least 0.6 m from every object it is not heading for (0.45 m from its own endpoint) and from the fire disk
    (radius 0.4 m at the trial's actual fire position);
  * the camera line of sight from a station waypoint to its centre stays at least 0.3 m from the other objects.
* The robot reads its waypoints and station centres from per-run files. All audits use the same files.

**Scenes** (one per layout, drawn with the same seed; lighting and props as in campaign E):
* 8 nominal;
* 6 swapped (search the other station);
* 4 empty (check both stations, then stop);
* 6 with a clearly visible fire behind the requested station (0.75–1.0× the full model, lateral offset 0.25–0.6 m to a random side, as in E). The fire position is drawn before the layout, and the layout is feasibility-checked with that fire. Empty scenes have no prop offsets.

Small hidden fires are not the subject here; G and H cover them.

**System.** v3.6, the orchestrator defaults. There is one arm.

**Labels.** The expected action follows from the scene, as in E. Fire perceivability comes from magenta-mask renders
at the layout's design poses (0.2 m short of the station waypoint, and ±0.4 m to each side; `experiments/campaign_l_protocol_design_fire_masks.json`), made before the first trial. An imperceptible fire is scored as
no fire.

**Primary endpoint.**
* Expected behaviour over the 24 layouts, with a Wilson CI.
* Unsafe deliveries: wrong supply, or a perceivable fire at the delivering station.
* The claim "v3.6 generalises to unseen layouts" is supported if expected behaviour is ≥ 22/24 **and** there are 0
  unsafe deliveries.

**Secondary.**
* Mission time vs the straight-line path length through the planned waypoints (least-squares slope and Pearson r over correct trials).
* Audit failures by type.
* A comparison with campaign E's fixed-layout rate, descriptive only.

**Infrastructure failures.** As in E–J, a stack failure before any VLM decision may be re-run once. All attempts are
kept.

**Smoke test (development, before registration).** 3 sampled layouts (seed `L-smoke`, checked to differ from every L layout; one nominal, one swapped, one empty) that are not part of L, driven with the full
stack, to verify the wiring. They are recorded in `campaign_L_smoke_ledger.jsonl`.

## Amendments
(none)
