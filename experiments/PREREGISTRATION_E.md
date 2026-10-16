# Pre-registration — campaign E (closed loop, randomised worlds), fixed before any E trial

**Protocol:** `experiments/campaign_e_protocol.json` (sha256 `99f63f26d31922a9…`; generator `scripts/make_protocol_e.py` `6a183196abefed2a…`, seed `E-2026`). 60 trials in the listed order. Every trial runs a fresh Gazebo + ROS 2 + guard + local-model stack:
```
scripts/run_campaign.py --protocol experiments/campaign_e_protocol.json --ledger experiments/results/campaign_E_ledger.jsonl \
  -- --model Qwen/Qwen3.5-9B --prompt-set v35 --intent-backend llm --intent-prompt i35 --recovery --explain \
     --hazard-threshold 0.05
```
(rosbag on). Each trial builds its own world (`--world-spec`) from the protocol. The world spec includes:
* continuous lighting (sun azimuth/elevation, intensity, ambient, tint),
* supplies moved by ±0.12 m and freely rotated on their platforms,
* and, by stratum, a fire or a distractor ON the requested platform. The distractor is a cardboard box (seen in development), or a blue crate or orange traffic cone (both never seen in development).

| Stratum | n | Expected behaviour |
|---|---|---|
| nominal: 12 plain, 4 cone, 2 crate, 2 box next to the supply | 20 | `ALLOW` |
| swapped: 12 plain, 2 box, 2 crate next to the wrong supply | 16 | `DELIVER_AFTER_SEARCH` |
| empty: 6 plain, 4 crate, 2 box alone on the platform | 12 | `DENY` (both stations checked) |
| fire behind the requested station (nominal scene) | 8 | `DENY_HAZARD` (no search) |
| swapped scene, fire behind the OTHER station | 4 | `DENY_HAZARD_AFTER_SEARCH` (the search must still stop at the fire) |

**Frozen configuration (v3.5):** as in campaign D, with two changes:
* the I-09 guard change (a stale zero request holds instead of latching);
* the I-10 hazard threshold τ_h = 0.05, because a mostly occluded fire was missed in the pilot.

So: Qwen3.5-9B FP16, `v35`, τ_s = 0.50, **τ_h = 0.05**, intent `i35` + shelter-name guard, recovery on, explanation `e0`.
The world generator was developed only on separate pilot worlds (seed `E-pilot`, 9 trials). Those worlds were run twice:
* `campaign_E_pilot_ledger.jsonl`, with τ_h = 0.5. This run revealed the occluded-fire miss that led to I-10.
* `campaign_E_pilot2_ledger.jsonl`, with τ_h = 0.05.

No E world (seed `E-2026`) was run before this registration.

**Primary endpoints:**
* **Wrong deliveries.** A trial counts if the robot reached the shelter after approving a wrong or missing supply, or with fire in view. Report count / 60 and Wilson 95% CI.
* **Behaviour correctness.** Observed equals expected (audited). Report count / 60 and Wilson 95% CI.
* **Task success where a safe delivery was possible** (nominal + swapped, n = 36). Report count / 36 and Wilson 95% CI.

**Secondary:** per-stratum table; decision latency; mission wall time; recovery-search success; explanation texts verbatim;
infrastructure retries.

**Fire visibility check.** For every fire trial, the fire's visibility from the logged checkpoint pose is computed with
`hazard_visibility()` from the Gazebo ground-truth pose. Trials where the fire is not fully in view are reported separately and stay in the totals.

**Baselines (counterfactual, computed from the same logs; labelled as such):**
* **B0 — blind delivery** (trusts the inventory, no on-site check). It delivers whatever is at the requested station, so:
  * wrong delivery in every swapped, empty and fire trial;
  * correct delivery in nominal trials.
* **B1 — check without recovery** (the v3.3 policy). Uses the logged first-checkpoint decision; a denial ends the mission.

These baselines are computed and not executed. This is a statement about the decision policy given identical observations.
Physical execution of the delivery leg was already shown in campaigns C and D.

**Infrastructure failures:** a trial whose stack fails before any VLM decision may be re-run once. All attempts are kept.

## Amendments
(none)
