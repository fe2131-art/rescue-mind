# RescueMind v1.7 — START HERE (2026-10-16)

**Purpose:** Physical AI Applied 1 final assignment: creative AI-guided robot task, with truthful evidence of actual robot motion. Jev 1.14.0 is REQUIRED in the live mission. Qwen3.8-Omni-Flash is the second judge. The actual task is **approach a supply station, visually verify supplies, approach shelter B**. The system **does not grasp or physically deliver** objects; it uses a direct-drive controller rather than Nav2 replanning.

## 0. What has and has not been demonstrated

* Offline: 207 Python regression tests; 6 deterministic closed-loop scripted decision scenarios; cross-file SDF/bridge/guard contract checks. See `verification/v17/`.
* **NOT VERIFIED:** actual Jev/Qwen API calls; actual ROS 2 / Gazebo Harmonic motion; camera images from Gazebo; GPU throughput; actual robot-video submission. Neither scripted fixtures nor grid animations meet video requirements.
* The appended notes are not a substitute for seeing a real Gazebo run on your Ubuntu/NVIDIA computer.

## 1. Fast offline verification (works without ROS/GPU/API key)

```bash
cd rescuemind_v17
python3 -m pip install -e .
bash scripts/v17_verify.sh
```

Run the new scripted experiments on their own:

```bash
python3 scripts/v17_closed_loop_campaign.py
python3 scripts/v17_stack_contract.py
```

Results: `verification/v17/campaign_summary.json`, `closed_loop_*.json`, `stack_contract.json`, `v17_TEST_REPORT.json`.

## 2. Ubuntu 24.04 + ROS Jazzy + Gazebo Harmonic machine

Check the exact environment before running anything:

```bash
bash scripts/check_ubuntu_ros.sh
bash scripts/setup_ubuntu_jazzy.sh    # ROS must already be installed
bash scripts/v17_verify.sh
python3 scripts/v16_orchestrate.py --plan --scenario motion-check
python3 scripts/v16_orchestrate.py --run --scenario motion-check
```

The orchestrator starts Gazebo → ROS/GZ bridge → independent velocity guard → sensor readiness → mission. `--run` will **reject** missing dependencies rather than pretend it ran.

Then supply real API keys through your local environment (never store them in ZIP or GitHub): `TYPESAFE_API_KEY`, `DASHSCOPE_API_KEY`, `DASHSCOPE_BASE_URL` (the official Alibaba Cloud workspace OpenAI-compatible `/v1` base URL). Do **not** post the keys or their output to GitHub.

```bash
python3 scripts/v16_orchestrate.py --run --scenario live \
  --instruction '避難所Bに飲料水を届けて'
```

Jev 1.14.0 vision (`Box`) remains experimental, needs an opt-in header and may return a box even for an absent item. Always inspect image and API response before attempting live missions. This is a simulator research project, **not safety-certified software**.

## 3. How to interpret v1.7 closed-loop test

The closed-loop twin sends synthetic sensor message timestamps to the **real project velocity relay core** and uses the **real project waypoint controller** with an ideal 2-D unicycle integrator. It uses a **scripted Boolean AI decision, not either model**. There is no photorealistic perception, tyre-slip, network latency, ROS executor, camera rendering or real dynamics. Thus, an artificial scenario success rate cannot be reported as AI accuracy or Gazebo success rate.

## 4. Final submission must include

- One **actual robot execution** MP4 between 60 and 180 seconds; speedups labelled.
- A PDF named `説明資料_PAI最終課題_<OmniCampusアカウント名>.pdf`, with tested actual results.
- A **public** GitHub repo URL with executable sources and reproduction instructions.
- The YouTube video titled `PAI最終課題_<OmniCampusアカウント名>`, set to at least *Unlisted*. Follow original age/premiere settings.
- No personal name, affiliation, email, secrets or private provider data in code/report/video.
- Submit via OmniCampus by **2026-11-02 10:00 JST**.

## 5. Critical location of files

* Main controller: `ros/gazebo_waypoint_mission.py` — output goes to `/rescuemind/cmd_vel_request`.
* Relay: `ros/guarded_cmd_relay.py` — only this should publish `/cmd_vel`.
* Gazebo world: `worlds/rescuemind_test_arena.sdf`.
* Official-document research with limitations: `docs/V17_PRIMARY_SOURCES_AND_STRATEGY.md`.
* Scripted closed loop: `rescuemind/closed_loop_twin.py`.
* Verification report: `verification/v17/v17_TEST_REPORT.json`.
* New report: `docs/RescueMind_v17_REPORT_DRAFT_NOT_SUBMISSION.pdf`.

All previous v1.6 files are retained for regression and history; **start with this README, not older version-numbered runbooks**.
