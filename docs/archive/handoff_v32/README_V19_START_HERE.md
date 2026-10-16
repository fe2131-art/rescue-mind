# RescueMind v1.9 — START HERE

**Scope: Jev 1.14.0 is mandatory. Qwen3.8-Omni-Flash is the comparison/fusion VLM.**

This is a simulator research project. It has **NOT** passed live Jev/Qwen API tests or Gazebo/ROS integration tests in the authoring container. All included measured tests are offline Python, synthetic conditions or idealized kinematic trajectories. Never interpret mock outputs as empirical VLM accuracy. Deadline **Nov 2, 2026 at 10:00 JST**.

## What the robot really does

Gazebo diff-drive robot moves from origin -> identified supply station. The ROS camera observes the station. Jev and Qwen inspect the on-site image, and a *fail-closed* decision gate allows or denies the robot's second leg to shelter B. This does **not** grasp, physically load, or deliver an item. The direct-controller lane is **NOT Nav2 obstacle rerouting**. Jev model is pinned `jev-1.14.0` (experimental image and box features), with no mock fallback in live mode.

## What changed from v1.8

1. **Authorization-trajectory timeline:** independent ROS observer wall timestamps are now checked against mission wall-clock anchor and the on-site Jev+Qwen decision. The audit rejects movements leaving the station before AI permission, a shelter visit preceding authorization, reversed clock, and missing dwell evidence.
2. **Optional ROS 2 bag evidence:** `--capture-rosbag` records `/odom`, `/cmd_vel`, `/rescuemind/cmd_vel_request`, `/camera`, `/scan`, `/rescuemind/guard_ready` to `outputs/runs/<run_id>/rosbag2`. Its process gets `SIGINT` on shutdown so rosbag can finalize `metadata.yaml`. If requested, a missing/incomplete recording rejects overall success. It requires `ros-jazzy-rosbag2` and disk space.
3. **Synthetic causal attack suite:** 10 predefined timeline cases; separate 6-case closed-loop study and previous fault campaigns retained. This is still NOT a Gazebo test.
4. **Triangulated result:** mission-owned arrival receipt + independently observed path + chronological validation (+ bag metadata with opt-in). None cryptographically authenticates Gazebo; video inspection still required.

## Reproduce offline (no API/GPU/ROS)

```bash
cd rescuemind_v19
python3 -m pip install -e .
bash scripts/v19_verify.sh
cat verification/v19/v19_TEST_REPORT.json
python3 scripts/integrity.py --check  # after release packaging
```

Results: `verification/v19/`. Do not submit synthetic animations as the mandatory robot video.

## Ubuntu 24.04 + ROS 2 Jazzy + Gazebo Harmonic + NVIDIA PC

```bash
bash scripts/check_ubuntu_ros.sh
bash scripts/setup_ubuntu_jazzy.sh
bash scripts/v19_verify.sh
python3 scripts/v16_orchestrate.py --plan --scenario motion-check --capture-rosbag
python3 scripts/v16_orchestrate.py --run --scenario motion-check --capture-rosbag
```

`--run` requires real local ROS/Gazebo. Review `outputs/runs/<run_id>/stack_result.json` for `state=COMPLETED`, `independent_motion_evidence.pass=true`, and `rosbag_evidence.pass=true`. A non-AI motor test is only a bring-up test, NOT an AI final-project result.

**Live AI stage (must use your actual personal API environment; never paste API keys into published logs):**

```bash
# Set TYPESAFE_API_KEY, DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL privately.
python3 scripts/v16_orchestrate.py --run --scenario live --capture-rosbag \
  --instruction '避難所Bに飲料水を届けて'
```

The `stack_result.json` must additionally contain `authorization_motion_chronology.pass=true`. Check real image saved with run ID and Jev/Qwen response audit. Before claiming success, confirm the Gazebo video and hardware-free simulation provenance manually. A bad or missing bag, chronologically impossible observation or API denial must not be presented as success.

Replay validation from the saved trace:

```bash
python3 scripts/v18_verify_run.py outputs/runs/<run_id> --scenario live
source /opt/ros/jazzy/setup.bash
ros2 bag info outputs/runs/<run_id>/rosbag2
```

## Official sources / reproducibility / experiment design

Start with `docs/V19_RESEARCH_AND_AWARD_STRATEGY.md` and `docs/V19_UBUNTU_FIELD_CHECKLIST.md`. Compare controlled runs with the correct vs incorrect supply image and matched initial poses. Keep **AI model accuracy** distinct from **ruleset rejection rate** and **ROS trajectory evidence**. Report false-allow, false-deny, abstention, time-to-decision, and task completion with confidence intervals only when real ground-truth data is collected.

## Mandatory course submission checklist

- Actual robot operation MP4, **60–180 seconds**; label playback speed if accelerated.
- GitHub repository **public**, complete code and environment instructions.
- PDF titled `説明資料_PAI最終課題_<OmniCampusアカウント名>.pdf` (replace placeholder).
- YouTube title `PAI最終課題_<OmniCampusアカウント名>`, at least **unlisted**, public recommended.
- Avoid personal identity, secret tokens, company/internal information in files/video.
- Submit the PDF + GitHub URL + YouTube URL to OmniCampus **by 2026-11-02 10:00 JST**.
