# RescueMind v1.8 — START HERE / 最終課題・優秀賞向け

**Status 2026-10-16: offline code validated, actual Gazebo and Jev/Qwen calls not yet validated.**

## A. What this project ACTUALLY attempts

A Gazebo simulated mobile robot receives a Japanese request, drives near a supply station, acquires a NEW ROS camera image, asks the **mandatory Jev 1.14.0** and Qwen3.8-Omni-Flash to verify the supply, then either drives near shelter B or stops. It does **not** grasp or carry supplies; it uses a direct waypoint controller, not a Nav2 global planner. Demonstrating that AI changes the second-leg motion, rather than just printing an image label, is the award-facing differentiator.

## B. What is new in v1.8

* An **independent ROS observer process** (`ros/odom_evidence_recorder.py`) subscribes to `/odom` and `/cmd_vel`, recording a newline-delimited JSON observation trace with a per-run ID.
* The supervisor refuses to report success unless BOTH the mission-owned receipt AND the independent trace show motion from origin → selected supply station → shelter, in order. Teleport-like jumps, timestamp reversals, wrong ROS frames and missing velocity observations are rejected.
* `scripts/v18_verify_run.py` verifies stored observations again independently. `scripts/v18_motion_evidence_campaign.py` runs *six synthetic test cases* (clearly **NOT physical run data**).
* JEV API is mandatory for live missions. There is **no automatic fallback** to a rule pretending to be the model.

**Limit:** this adds independent **ROS-topic** evidence, not secure attestation of an actual Gazebo process. Rogue ROS publishers can fabricate `/odom`. Review actual Gazebo footage and topic graph before public claims; safety guard is not certified.

## C. Reproduce offline tests (no ROS, no NVIDIA GPU, no API)

```bash
cd rescuemind_v18
python3 -m pip install -e .
bash scripts/v18_verify.sh
```

The most important experiment reports are in `verification/v18/`. Look for `v18_TEST_REPORT.json`, `synthetic_motion_evidence_campaign.json`, and the new unit-test output. Do not present synthetic test measurements as model accuracy or Gazebo success.

## D. Ubuntu 24.04 + NVIDIA GPU real run (the critical missing step)

```bash
bash scripts/check_ubuntu_ros.sh
bash scripts/setup_ubuntu_jazzy.sh
bash scripts/v18_verify.sh
python3 scripts/v16_orchestrate.py --plan --scenario motion-check
python3 scripts/v16_orchestrate.py --run --scenario motion-check
```

The `--run` mode, **not** `--plan`, now starts the independent subscriber as a fourth managed service; it writes `outputs/runs/<run_id>/independent_ros_topics.jsonl`. When complete, inspect the `stack_result.json` and require `state=COMPLETED` **and** `independent_motion_evidence.pass=true`.

To verify saved records again:

```bash
python3 scripts/v18_verify_run.py outputs/runs/<run_id> --scenario motion-check
```

For Jev + Qwen live mission, export **privately** `TYPESAFE_API_KEY`, `DASHSCOPE_API_KEY`, `DASHSCOPE_BASE_URL` (official region-specific HTTPS workspace endpoint; do **NOT** put any key into source or terminal recordings):

```bash
python3 scripts/v16_orchestrate.py --run --scenario live \
  --instruction '避難所Bに飲料水を届けて'
python3 scripts/v18_verify_run.py outputs/runs/<run_id> --scenario live
```

The live mission **must not proceed** if Jev/Qwen API requests fail, disagree, indicate danger, or detect wrong supplies. The Jev Box experimental primitive must be combined with separate **presence detection**, never accept location alone.

**Ubuntu execution has NOT been performed in this generated package.** If `gz` or `ros2` is missing, the orchestrator refuses execution. A Python simulation is not a replacement for the required robot video.

## E. How to aim for an award

The lecture's four scored dimensions are creativity, technical skill, real-world applicability, and video/report clarity. Show two **real** Gazebo runs with identical camera pose and obstacles but different contents (right vs wrong supply): movement allowed vs denied at the checkpoint. Measure AI decision errors and abstention on a human-labelled **held-out** set, API latency, and mission success with run IDs/actual logs. Include unsuccessful attempts and limitations. Avoid reporting scripted case success as AI accuracy.

Final deliverables by **2026-11-02 10:00 JST**: 60–180 s MP4 depicting **actual** robot operation; PDF named `説明資料_PAI最終課題_<OmniCampusアカウント名>.pdf`; public GitHub repo; YouTube URL titled `PAI最終課題_<OmniCampusアカウント名>` (at least unlisted). Exclude personal information and API secrets. Detailed checklist: `docs/V18_AWARD_EXPERIMENT_AND_SOURCES.md`.
