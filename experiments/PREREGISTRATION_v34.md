# Pre-registration — v3.4 closed-loop evaluation (campaign D), fixed 2026-10-17 before any trial

**Protocol:** `experiments/v34_protocol.json` (sha256 prefix `673badffb3dd67d1`), 42 trials in the listed order, each a
fresh Gazebo + ROS 2 + guard + local-model stack via `scripts/run_campaign.py --protocol experiments/v34_protocol.json`.
* R001–R030: same IDs/order/scenes as campaign C (3 scenes × 2 supplies × 5 repeats).
* R031–R042: fire behind the requested station (6), dim evening light (4), cardboard box on an empty platform (2).
* Each trial's instruction comes from a phrasing pool disjoint from the I-04 held-out set.

**Frozen configuration** (chosen only on development data, see docs/IMPROVEMENT_LOG.md I-01…I-08):
* Model: Qwen/Qwen3.5-9B, FP16, eager attention, V100 (docker STACK=next: torch 2.8.0+cu126, transformers 5.20.0)
* Vision prompts: `v35`; hazard Yes/No in the same prompt set; decision τ_s = 0.50, τ_h = 0.50 (unchanged since v3.3)
* Instruction parser: local LLM closed-set (`i35`) + explicit shelter-name guard (`--intent-backend llm`)
* Recovery search: on (`--recovery`); explanation: on (`--explain`, prompt `e0`, never used for decisions)
* World: spherical wheel collisions (I-01); rosbag on.

**Expected behaviour (scoring):**
nominal → `ALLOW` (delivered, audited); swapped → `DELIVER_AFTER_SEARCH` (first station denied, other station
confirmed, delivered, recovery audit passed); empty / empty+box → `DENY` (both stations refused, robot stops);
fire → `DENY_HAZARD` (refused at the first station, no search).
An instruction the parser refuses counts as FAILED for that trial (the request was supported).

**Metrics:** behaviour correctness (audited), VLM decision correctness per checkpoint, false approvals
(any ALLOW of a wrong/missing supply or with fire in view), instruction-parse correctness, decision latency,
explanation texts (reported verbatim).

**Infrastructure failures:** a trial whose stack fails before any VLM decision may be re-run once; every attempt
is kept in `experiments/results/campaign_D_ledger.jsonl`. No trial is discarded after a decision exists.
