# RescueMind v2.2 | START HERE (2026-10-16)

**Submission is NOT yet complete.** This release contains source, Gazebo experiment SDFs, offline tests, an explicitly unsubmitted PDF draft and tools for auditing future *real* ROS run captures. It contains **no actual Jev/Qwen API results or Gazebo physics video**.

## What changed, and why it matters for award evaluation

Previously, nearly all risk/deny experiments fed synthetic AI outputs into the decision gate. v2.2 adds an actual physical-looking **controlled-scene protocol** for Gazebo, so genuine camera frames can be collected:

| Scene | Water shelf | Medicine shelf | Intended task for water request |
|---|---|---|---|
| `nominal` | Bottle shapes | First-aid case | AI can authorize continuation *if* both recognize and agree |
| `swapped` | First-aid case | Bottle shapes | AI should refuse at water shelf |
| `empty` | Empty | Empty | AI should refuse at water shelf |

All shelf bases are the SAME neutral color (removes color-label shortcut); robot, sensors, stage waypoint coordinates, lighting and ground are identical across the three generated SDFs. **Passing XML/structure checks is not proof that images render visibly or models recognize objects.** Never claim scene correctness without checking the real Gazebo camera frames.

New modules: `rescuemind/scene_variants.py`, `rescuemind/negative_evidence.py`, `scripts/v22_orchestrate.py`, `scripts/v22_audit_trials.py`, `scripts/v22_generate_scenes.py`, `tests/test_v22_scenes_and_denials.py`.

## Offline reproduction

```bash
cd rescuemind_v22
python3 -m pip install -e .
bash scripts/v22_verify.sh
python3 scripts/v22_orchestrate.py --plan --scenario live --scene nominal
python3 scripts/v22_orchestrate.py --plan --scenario live --scene swapped
python3 scripts/v22_orchestrate.py --plan --scenario live --scene empty
```

`--plan` **does not execute** Gazebo/AI or require credentials. `scripts/v22_generate_scenes.py` regenerates scenes and a hash manifest; run this to reproduce scene artifacts.

## Ubuntu 24.04 / Jazzy / Gazebo Harmonic (REAL TESTS NOT YET EXECUTED)

```bash
bash scripts/check_ubuntu_ros.sh
bash scripts/setup_ubuntu_jazzy.sh
bash scripts/v22_verify.sh

# First prove movement without AI (not submission proof):
python3 scripts/v22_orchestrate.py --run --scenario motion-check --scene nominal --capture-rosbag

# After Jev + Qwen API credentials and screenshot visibility are confirmed:
python3 scripts/v22_orchestrate.py --run --scenario live --scene nominal --capture-rosbag \
  --instruction '避難所Bに飲料水を届けて'
python3 scripts/v22_orchestrate.py --run --scenario live --scene swapped --capture-rosbag \
  --instruction '避難所Bに飲料水を届けて'
python3 scripts/v22_orchestrate.py --run --scenario live --scene empty --capture-rosbag \
  --instruction '避難所Bに飲料水を届けて'
```

**IMPORTANT:** In `swapped` / `empty`, a correctly denied mission currently exits **nonzero**, and `stack_result.json` says `FAILED`. This reflects the underlying process failing closed, not an experiment failure. Verify a correct denial using a **separate, independent** ROS trajectory audit:

```bash
python3 scripts/v22_audit_trials.py outputs/runs/<nominal_id> outputs/runs/<swapped_id> outputs/runs/<empty_id> \
  --csv outputs/v22_real_trial_audit.csv
```

Missing capture/AI response, crash, timeout and trajectory mismatches are **not** accepted as an expected AI denial. A refusal is accepted only when logged as an actual on-site AI checkpoint denial with corroborating station-stationary ROS observations. These ROS logs alone cannot authenticate Gazebo or model provenance; inspect screen recording and raw API audit separately.

Jev `jev-1.14.0` remains **mandatory**; `qwen3.8-omni-flash` is used as a second model. Never put API keys in ZIP/GitHub. APIs were NOT called in the artifact builder environment. The `real_model` field in saved responses is a claim requiring external validation.

## 4 award criteria and evidence

- **Creativity:** same mission, controlled change in station contents -> robot continuation vs rejection.
- **Technical depth:** Gazebo + ROS camera/laser + Jev/Qwen inference + velocity relay + independent odom and authorization chronology.
- **Practicality:** separately report unsafe permission, false rejection, coverage, and inference latency; don't assert two-model superiority until real-data results.
- **Presentation:** split-screen 120 s real Gazebo video: correct/swap/missing trials plus inference/trajectory overlay, source and evaluation metrics.

## Submission barriers (2026-11-02 10:00 JST)

- [ ] Verified ROS/Gazebo movement on user's Ubuntu machine
- [ ] Jev/Qwen requests authenticated and captured for *real* checkpoint frames
- [ ] No explicit anonymous/unknown or hallucinatory permission in mismatch cases
- [ ] 60-180 second real robot MP4; speed multiplier disclosed if used
- [ ] Public GitHub, PDF named `説明資料_PAI最終課題_omnicampusアカウント名.pdf`
- [ ] YouTube URL submitted on OmniCampus, minimum unlisted; no personal identifiers or keys

See `docs/V22_AWARD_STRATEGY_AND_EXPERIMENT.md` and `docs/V22_PRIMARY_SOURCES.md`.
