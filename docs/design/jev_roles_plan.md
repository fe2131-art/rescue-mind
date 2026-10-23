# JEV with divided roles (plan, 2026-10-23; not a registration)

**Premise correction.** The "29-43% fewer misses" of study JH is one base world and its three ablation copies (11 -> 10 by base world, I-93); JH1 stays a failed claim. The `--judge` mechanism of I-77 asks the *same* hazard question on the *same* views and takes the max: redundancy, not a division of labour. A division of labour has to give JEV something Qwen does not do.

**Roles.**
| | decides | speed | may |
|---|---|---|---|
| Qwen3.5-9B (gate) | request parse, item identity, the station hazard call (multi-crop, permuted options) | 2-6 s per station | refuse, approve |
| JEV (small, other family) | **where to spend more looking**: a loose-threshold sentinel on every view on the way and at the station | ~0.2-0.6 s per image | request extra views / a stop-and-report on the route; *never* approve, and it never refuses a delivery alone at the station |

Why this is different from JH: a JEV false alarm costs time (extra views), not a delivery; the refusal is still Qwen's, so the false-stop budget is Qwen's. A JEV miss costs nothing beyond Qwen's own miss. Prop. 2 is unchanged (JEV only adds looking).

**Evidence we can get without GPU, after JI:** `ji_cascade.py` on the JI scores: "JEV flag (its own loose threshold) -> Qwen on all six views, otherwise Qwen on three views" against always-three and always-six: misses, false stops, mean number of views (a time proxy). Descriptive; JI's registered claims are untouched.

**Closed-loop version (needs a register-first study):** judge in the VLM server beside Qwen. Memory: Qwen3.5-9B takes ~19 GB of the 32 GB V100, so only SmolVLM2-2.2B (JH: joint miss 9, union false stops 4/104; the fastest) fits next to it in fp16; InternVL3-8B (~16 GB) does not. Open items before registering: (1) the existing `adaptive_views` (I-20) already spends extra views when the gate's own score exceeds a low suspicion threshold; the JEV version swaps the trigger; (2) judge threshold needs its own closed-loop clean calibration (GD/GV showed a heavier clean tail than image level); (3) the route-sentinel idea needs a check that the lidar guard does not already stop for the flame (collision geometry in the fire models; smoke is not a lidar obstacle) and a concrete exposure endpoint.
