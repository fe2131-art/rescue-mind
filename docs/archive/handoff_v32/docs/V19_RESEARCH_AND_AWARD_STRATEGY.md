# RescueMind v1.9 — Original assignment, primary research and award strategy

Verification date: 2026-10-16 (JST). Distinguish official information / author-derived hypothesis / executable code tests.

## A. The supplied course text controls the scope

The user-supplied `assignment/Physical-AI応用1講座-最終課題.txt` (10/8 version) requires an AI-enabled robot task, a **60–180 sec robot demonstration video**, all code, and a PDF description. Course scoring adds creativity, technical merit, real-world applicability and communication. No fixed numeric scoring weights or guaranteed award criteria are stated. Submission begins 2026-10-19 and closes **2026-11-02 10:00 JST**. Public GitHub; YouTube at least unlisted. Avoid names, organizations, email addresses and secrets. This project does not copy the sample task source unchanged.

## B. Verified external primary sources

1. **TypeSafe official release** (Jev 1.14): https://typesafe.ai/blog/jev-1-14 . Describes experimental image input and `box` under `TypeSafe-Danger-Zone-Images: true`. Says this is a preview/experimental workflow; not a safety-certified detector. `jev-1.14.0` pinned in code.
2. **Jev API technical documentation**: https://www.jevtypesafeai.com/clerk_1790100707857/docs . `box` gives normalized coordinates but ALWAYS a box (no "not found"); `noul` presence check required. This is implemented in previous versions' checkpoint validation.
3. **Alibaba Cloud Model Studio**: https://help.aliyun.com/en/model-studio/qwen3-8-omni-flash . Confirms the existence, provider, images/text inputs and text outputs of `qwen3.8-omni-flash` (doc updated 2026-10-10). This is API-provided, not a locally downloaded open checkpoint in this plan.
4. **Gazebo Harmonic ROS2 integration**: https://gazebosim.org/docs/harmonic/ros2_integration/ . Confirms ROS/Gazebo bridge syntax and direction. Our `bridge_direct_gazebo.sh` maps `/odom`, `/scan`, `/camera` Gazebo to ROS and `/cmd_vel` ROS to Gazebo.
5. **ROS 2 official rosbag2**: https://github.com/ros2/rosbag2 . Confirms `ros2 bag record --topics ... -o ...` and `ros2 bag info`. v1.9 bag recording and checks are based on these documented public interfaces.

These sources support the API/platform design, **not the claim that the application works on the user's PC**.

## C. Improvements tied to scoring

| Course criterion | v1.9 concrete contribution | Required real evidence (not yet obtained) |
| --- | --- | --- |
| Creativity | On-site Jev/Qwen authorization *causally gates* the robot's second leg | Same navigation setup, correct vs wrong supply, video comparison |
| Technical skill | Independent ROS odometry witness PLUS permission timestamp test PLUS optional rosbag | Observed Gazebo and ROS graph, causal audit passes on actual records |
| Practical value | Unsafe/ambiguous observation rejects; speed/sensor supervision | Real-image false-allow/false-deny/abstention and stop-delay |
| Communication | Two contrasting runs, plot + event timeline + human-readable failure reasons | 120-second edited actual robot recording, report with figures |

**Do not imply physical transport**: the robot does not grip or carry emergency supplies. Describe it as *supply station identification and shelter approach*; navigating to the station does not prove it can deliver goods. The active lane is direct-drive, **not Nav2 dynamic replanning**.

## D. Actual research experiment protocol

- Fix independent ground truth per image, scene ID, camera pose, illumination, mission text, API model IDs and version, hazards, and the action that would have been correct.
- Evaluate **Jev-only, Qwen-only, Jev+Qwen fail-closed fusion** on exactly the same held-out images. Report per-trial decisions and reasons, false-alarm and miss counts, Wilson intervals. A low allow rate may hide excessive false denials.
- Make paired comparisons, ideally using recorded real outputs from the same scenes. Keep all real model latency results separate from simulated VLM fixtures and fail-safe rules.
- Real robot runs: same scene positions, compare correct target / wrong target / ambiguous marker / API outage / camera dropout. Record ROS topic bag when enabled plus independent observer trace and actual Gazebo footage. Never label a synthetic result "Gazebo verified".
- Blindly inspect random subset of videos/frames to reduce confirmation bias. Preserve failures and disclose limits. Never present artificial 972-condition gate results as image recognition accuracy.

## E. Time-critical stop/go decisions

- 10/18: Ubuntu24.04/Jazzy/Harmonic initial smoke, obtain frame/scan/odom or switch to a known ROS/Gazebo starter world.
- 10/20: real motion-check from console; no AI claim yet.
- 10/23: first **real API image** + on-site checkpoint; if unavailable, do not fake results—document blocker and pivot to a simpler demonstrable AI+robot capability.
- 10/27: prioritize repeated real runs, stable logs and video over adding another model.
- 10/29: final 60–180-second robot demonstration and real evidence summary.
- 10/31: GitHub/public checklist, privacy audit, PDF + YouTube publication (unlisted minimum) and URL checks.
- 11/01: submit early; deadline is Nov 2 **10:00 JST**.

No automatic task can submit YouTube or OmniCampus for you as part of this ZIP. External runtime/API credentials are essential for true integration claims.
