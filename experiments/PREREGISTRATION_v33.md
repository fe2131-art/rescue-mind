# Pre-registration — v3.3 closed-loop test (fixed 2026-10-16, before any test trial)

**Test set:** the 30 trials in `experiments/v23_locked_protocol.json` (sha256 prefix `fadc528717b52957`),
executed in the locked `order`, each as a fresh Gazebo + ROS 2 + guard + local-VLM stack
(`scripts/run_campaign.py` → `scripts/v32_orchestrate.py --run --scenario live`).
3 scenes (nominal / swapped / empty) × 2 requested supplies × 5 repeats.
Repeats share the same world, so they are **not 30 independent scenes**.

**Model / method (frozen):** Qwen/Qwen2.5-VL-3B-Instruct, FP16, eager attention, Tesla V100,
`scripts/local_vlm_server.py --method scored` (closed-set log-probability; option order permuted
between pass 1 and pass 2; separate hazard Yes/No question).

**Decision rule (frozen):** ALLOW iff both passes name the requested supply, the requested label's
probability is ≥ **0.50** in both passes, and neither pass reports hazard (p(Yes) ≥ 0.5).
Chosen on the separate 48-image development set (`experiments/vlm_devset`, seed 7, randomized
teleported viewpoints): positives min p ≥ 0.569, negatives max p ≤ 0.019.

**Ground truth:** SDF scene (scorer only, never sent to the robot or model).
Expected action: ALLOW for nominal, DENY for swapped and empty.

**Outcome classes:** `COMPLETED` (ALLOW + independent ROS + Gazebo ground-truth arrival at the shelter),
`COMPLETED_EXPECTED_DENIAL` (DENY + robot stayed at the station per ground truth + bag finalized),
otherwise `FAILED`.

**Primary metrics:** false-approval count (wrong/missing supply allowed), false-denial count,
decision accuracy, VLM latency (frame → decision), mission wall time.

**Infrastructure failures:** a trial whose stack fails *before any VLM decision* may be re-run once;
every attempt (including the failed one) stays in `experiments/results/campaign_ledger.jsonl`
with `final=false`, and is reported.  No trial is discarded after a VLM decision exists.

## Amendment (2026-10-16, before campaign B)

Campaign **A** was aborted after 9 trials (12 attempts): 4 attempts failed **before any VLM
decision** because the freshly started mission node had not yet discovered `/odom` or `/scan`
within its fixed 3 s warmup (DDS discovery race on a loaded 4-core host). R008 failed twice and
would have been a final infrastructure failure. All VLM decisions that did occur in A were correct
(9/9). A's ledger is kept unchanged in `experiments/results/campaign_A_aborted_ledger.jsonl`.

Change (startup only; model, prompts, threshold and decision rule unchanged): the mission now keeps
its zero-velocity warmup until every required stream has delivered a first message, up to 20 s
(`--sensor-wait`), with the mission watchdog grace aligned to it. Campaign **B** re-runs all 30
trials in the locked order from scratch and is the reported test; A is reported alongside it.

## Amendment 2 (2026-10-16, before campaign C)

Campaign **B** was aborted after 5 trials (9 attempts): every attempt was stopped *before any VLM
decision* by the runtime graph watcher, which correctly detected a **second `/cmd_vel` publisher**.
Cause: aborting campaign A had SIGKILLed the orchestrator, so entire stacks (velocity guard included)
were left running as orphans and kept publishing into the next trials. B's ledger is kept unchanged
(`experiments/results/campaign_B_aborted_ledger.jsonl`).

Changes (orchestration only; model, prompts, threshold, decision rule unchanged): services are
stopped with SIGINT → SIGTERM → SIGKILL per process group; the orchestrator turns SIGTERM/Ctrl-C into
a full teardown; the campaign runner forwards Ctrl-C instead of killing the orchestrator; Docker runs
with `--init`; and a **stale-stack preflight** (`scripts/stack_quiescence.py`) refuses to start a trial
while any `/cmd_vel` publisher or Gazebo world is already visible. Campaign **C** re-runs all 30
trials from scratch in the locked order and is the reported test; A and B are reported alongside it.
