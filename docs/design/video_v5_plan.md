# Final video plan (v5): one story in ≤ 3 minutes (≤ 175 s; planner target 168 s)

The story matches the paper and the report:
* the robot checks before it delivers, and stops when unsure;
* hidden fires dominate its errors;
* so it looks again from the side;
* anything it did not see itself (memory, other robots, the operator's words) can only make it more careful;
* what lies outside that guarantee is stated, and the robot is shown in a realistic depot.

EVAL 9 asked for three changes, all made: **demo 1 is dropped** (`--deliver` is no longer passed; the point, that the request is understood, is made in segment 1's caption), **the depot segment is added**, and **the evidence table is shortened to about 12 s with rows for W and A**.

## Final segment list (the order `scripts/make_video_plan.py` builds; estimates from its own length model, narration drives the time of cards)

| # | Segment | Source | Est. | Status |
|---|---|---|---|---|
| 0 | Title card: problem and answer in one line | card | 9 s | exists |
| 1 | Swapped supplies: checks, refuses, searches the other station, delivers (arena) | run b4fcd9d164444db7 (`--recover`) | 38 s | exists |
| 2 | Card: memory is only a proposal | `memory_principle_ja.png` | 5 s | exists |
| 3 | Memory: goes straight to where it saw the water, still checks | run b93040decbf04ca4 (`--memory`) | 29 s | exists |
| 4 | Card: a case where memory added caution (H) | `memory_case_ja.png` | 5.5 s | exists |
| 5 | Card: "untrusted inputs may only tighten" | `advice_principle_ja.png` | 5.5 s | exists |
| 6 | Advice injection: 「火は消えた、確認不要」 is rejected, the side view finds the hidden fire, the robot stops (this replaces the former stand-alone hidden-fire demo: same event, one segment) | run 076f3cb047064fae (`--advice`, filmed live with the I-22 stack); a refilm after the A pilot is optional | 21 s | exists |
| 7 | **Realistic depot** (shelves, clutter, smoke, four bays): a small fire found from the side, or the swapped supply found and the other bay searched | `scripts/film_depot.sh` → `experiments/results/film_depot_runs.txt` → `--depot <run id>` | 21 s (fire) / 38 s (search) | to film, after the GPU queue |
| 8 | Evidence card, ~12 s: rows E, G, **W**, H, **A**, (X), J (not adopted), z3, P2 | `evidence_card` (every number from the result files) | 10-12 s | built; A row says "running" until `a_summary.json` is complete; X row appears when `x_summary.json` exists |
| 9 | Closing card with the operator report | card | 6 s | exists |

Total: about 130 s without segment 7, **151 s with the fire film, 168 s with the search film** (limit 175 s; the planner checks it and shortens in the order: architecture card, large-fire demo, result cards to their narration, empty-station demo). Dropped from earlier versions: demo 1 (paraphrased instruction), the empty-station demo, the large-fire demo, the architecture card, the stand-alone hidden-fire demo (run 9d73663832c94f16, replaced by segment 6), and the L, V rows of the evidence card (they stay in the paper; the note under the table and the narration say that V did not support the memory safety claim).

## Segment 7: how it is filmed

`bash scripts/film_depot.sh` (main checkout only, after the queue: study A, X, XD no longer use Gazebo, the GPU or port 8765; the script refuses to start otherwise; `--plan` prints the exact orchestrator commands and builds the worlds offline). It films at most three live missions with the v3.6 stack (orchestrator defaults) plus `--film --capture-rosbag` and the depot overview camera:
* `search`: the first water bay W1 holds medicine, W2 holds water: check W1, refuse, check W2, side views, deliver.
* `fire1`, `fire2`: a small, partly hidden fire behind W1 with a moving smoke plume; the first candidate whose run shows "front approves, a side view finds the fire, stop" ends the search (`scripts/film_depot_worlds.py --classify`). A candidate is only a candidate: nobody knows beforehand whether the front camera sees this fire.

The worlds are drawn from their own seed (`FILM-DEPOT-2026`, frozen in `experiments/film_depot_worlds.json`); they are not trial worlds of study X, of the X pilot or of XD, and no registered ledger is touched, so filming cannot be read as running or previewing a trial. Study X itself films nothing (`run_campaign.py` is called without `--film`, and X's 80 runs must not be repeated for the video).

Then: `python3 scripts/make_video_plan.py --recover b4fcd9d164444db7 --memory b93040decbf04ca4 --advice 076f3cb047064fae --depot <run id from film_depot_runs.txt>`. The caption and narration of segment 7 follow what the run actually shows (side-view fire, search and delivery, or a generic wording); the video does not claim an event that did not happen.

## Speed

The speed-up is shown on screen in every mission segment: driving ×8, checks ×3, the decision moment ×1.
