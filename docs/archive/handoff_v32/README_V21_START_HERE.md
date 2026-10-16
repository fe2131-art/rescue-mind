# RescueMind v2.1 — START HERE / 2026-10-16

**Submission is not ready yet.** The course requires a 60–180 s video of an actual simulator/hardware robot carrying out a task, public GitHub code, a named PDF, and YouTube URL. This ZIP includes code, offline verification and a DRAFT PDF only. No real Jev/Qwen request or Gazebo physics run was performed in this container.

## Main improvement over v2.0

The previous readiness checked ROS topics, but not independently whether Gazebo Transport actually advertised the expected simulation streams. New **Gazebo Transport preflight** checks SDF ↔ bridge YAML ↔ live `gz topic -l` before allowing any motion. This catches missing Gazebo sensor streams and topic-name changes earlier. It does **not** prove real message content or physics; subsequent ROS payload/timestamp/safety checks still apply.

New files:

- `rescuemind/gazebo_transport_contract.py` — static SDF and YAML cross-contract and Gazette topic-list check.
- `scripts/v21_gz_transport_probe.py` — read-only external `gz topic -l` probe with explicit reasons for failure.
- `scripts/v21_live_readiness.sh` — Gazebo topic preflight **before** existing ROS safety checks.
- `scripts/v21_orchestrate.py` — v2.0 supervisor with the new prereq gate.
- `tests/test_v21_gazebo_transport.py` — 18 new tests (positive, missing topics, mutations, subprocess errors).
- `docs/V21_AWARD_RESEARCH_AND_LIMITATIONS.md` — sources and verification limitations.
- `verification/v21/*` — reproducible evidence, not a fake Gazebo success log.

**Jev 1.14.0 is mandatory** in the live path; Qwen3.8-Omni-Flash is the second inference. We do NOT claim physical grasping, cargo transport, Nav2 replanning, or production safety.

## Offline reproduction (no ROS / no API required)

```bash
cd rescuemind_v21
python3 -m pip install -e .
bash scripts/v21_verify.sh
python3 scripts/v21_orchestrate.py --plan --scenario motion-check
python3 scripts/v21_orchestrate.py --plan --scenario live --capture-rosbag
```

A real Gazebo Transport probe intentionally **fails closed** when Gazebo is absent:

```bash
python3 scripts/v21_gz_transport_probe.py
```

## On your Ubuntu 24.04 + NVIDIA PC

```bash
bash scripts/check_ubuntu_ros.sh
bash scripts/setup_ubuntu_jazzy.sh
bash scripts/v21_verify.sh

# Vehicle motion WITHOUT AI: prerequisite, not final video
python3 scripts/v21_orchestrate.py --run --scenario motion-check --capture-rosbag

# Only when physical simulation and model credentials work
python3 scripts/v21_orchestrate.py --run --scenario live --capture-rosbag \
  --instruction '避難所Bに飲料水を届けて'
```

If readiness fails, see `outputs/local_runtime_diagnostics/v21_gz_transport.json`, `outputs/local_runtime_diagnostics/v20_clock.json`, `outputs/runs/<run_id>/readiness_last.txt`, and service logs.

**Expected Gazebo topics:** `/world/rescuemind_arena/clock`, `/odom`, `/scan`, `/camera`. `/cmd_vel` is a Gazebo **subscriber** and is therefore intentionally **not required** in `gz topic -l` before the bridge is connected. Run `gz topic -l` yourself when diagnosing actual topics. Topic names alone do not prove messages, clock progress or motor response.

## Submission blockers

1. [ ] Real Gazebo robot reaches aid station (attach actual screen recording).
2. [ ] Real Jev and Qwen image inference on fresh ROS camera data (record honest output/latency).
3. [ ] Demonstrate both continuation and model disagreement/denial on robot video.
4. [ ] Evaluate false permission, false rejection, coverage, and inference latency on held-out labeled images.
5. [ ] Produce 60–180 second MP4 containing actual robot task execution, no personal info.
6. [ ] Public GitHub, OmniCampus PDF naming, appropriate YouTube URL and settings.

Deadline: **2026-11-02 10:00 JST**. Do not upload existing 17 s grid prototype as a final robot video.
