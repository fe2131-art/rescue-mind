# RescueMind v2.0 — START HERE (2026-10-16)

## What it is

A research prototype for Physical AI 応用1. **Jev 1.14.0 is mandatory**, with Qwen3.8-Omni-Flash as a second vision model. A Gazebo diff-drive robot approaches a supply station, checks a *new* ROS camera frame, and either continues toward shelter B or stops. **No physical grasping/loading/delivery, and no demonstrated Nav2 replanning.**

## Why v2.0

**v1.9 did not explicitly bridge Gazebo's simulation `/clock`.** Gazebo sensor `header.stamp` values belong to simulated time, whereas watchdogs and the independent AI-authorization audit use host monotonic/Unix times. Those are separate domains; never subtract them directly. ROS bag recording with `--use-sim-time` must first receive `/clock`.

v2.0 adds:

- `configs/ros_gz_bridge_v20.yaml`: 5 **one-direction** mappings, including `/world/rescuemind_arena/clock` -> ROS `/clock`.
- `scripts/v20_clock_probe.py`: read-only checks for advancing `/clock` and clock-domain-consistent `/camera`, `/scan`, `/odom` header stamps.
- `scripts/v20_orchestrate.py`: fails launch readiness if clock check fails; with `--capture-rosbag` records `--use-sim-time` plus `/clock`.
- `rescuemind/sim_clock_contract.py`, `rescuemind/bridge_contract.py`: testable pure-Python contracts.
- `rescuemind/bag_evidence.py`: backward-compatible metadata validator that requires recorded `/clock` **only when simulation-clock capture is requested**.

**Important**: v2.0 static assertions and mocked offline tests passed, but this container does not contain ROS 2, Gazebo, or cloud API credentials. Runtime success is unverified. This is not a safety-rated system.

## First run: offline only (works without ROS/GPU/API)

```bash
cd rescuemind_v20
python3 -m pip install -e .
bash scripts/v20_verify.sh
python3 scripts/v20_bridge_audit.py
python3 scripts/v20_orchestrate.py --plan --scenario live --capture-rosbag
```

## Run with Ubuntu 24.04 + Jazzy + Harmonic (on your NVIDIA PC)

```bash
bash scripts/check_ubuntu_ros.sh
bash scripts/setup_ubuntu_jazzy.sh
bash scripts/v20_verify.sh
```

**Bring-up before enabling any AI motion**:

```bash
python3 scripts/v20_orchestrate.py --run --scenario motion-check --capture-rosbag
```

This starts Gazebo -> YAML bridge -> velocity guard -> independent ROS observer -> bag recorder, and then checks guard, sensor payloads and ROS `/clock` before moving. `motion-check` is an **AI-free diagnostic**, not the final assignment video.

**Only after success**: privately configure `TYPESAFE_API_KEY`, `DASHSCOPE_API_KEY` and your **region-specific** `DASHSCOPE_BASE_URL`, then run:

```bash
python3 scripts/v20_orchestrate.py --run --scenario live --capture-rosbag \
  --instruction '避難所Bに飲料水を届けて'
```

Inspect `outputs/runs/<run_id>/stack_result.json`, `mission.json`, `independent_ros_topics.jsonl`, `rosbag2/metadata.yaml`, `checkpoint.jpg`, and your **actual** Gazebo recording. `--plan` is not proof of execution. Runtime failures do **not** imply the model is safe. See `docs/V20_RESEARCH_AWARD_AND_RUNTIME.md`.

## Course requirements (source: supplied 10/8 assignment)

- Show **robot executing task** in real simulator/hardware video, MP4 **60–180 s**; label accelerated playback.
- Submit report PDF named `説明資料_PAI最終課題_<OmniCampusアカウント名>.pdf`, public GitHub code URL, YouTube URL/title `PAI最終課題_<OmniCampusアカウント名>`.
- YouTube **at least unlisted**, public recommended; set not for children, no age restriction, no instant premiere. Keep available during marking.
- No personal/contact/confidential info, API tokens, or identifying overlays. Deadline **Nov 2, 2026 10:00 JST**.
- **The included PDF is a DRAFT and is NOT ready to submit**: real Gazebo/API results and screenshots must be added.
