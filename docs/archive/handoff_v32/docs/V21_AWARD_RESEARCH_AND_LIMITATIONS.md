# v2.1: Award-oriented investigation and implementation record

**Assessment source:** `assignment/Physical-AI応用1講座-最終課題.txt`, 10/8 edition. Evaluation axes exactly: 創造性, 技術力, 実用性, 表現力. The brief does not publish weights, ranking thresholds, or any guarantee of a prize.

## What was verified in this iteration

1. Re-ran v2.0's 249 Python tests from its unpacked source: PASS.
2. v2.0 had read-only ROS sensor/clock readiness but no independent Gazebo-Transport-topic listing check. Added a strict Gazebo SDF ↔ bridge YAML cross-contract and a `gz topic -l` preflight, then integrated it before ROS readiness in v2.1 orchestrator.
3. Ran new tests for missing `/camera`, missing `/world/rescuemind_arena/clock`, malformed stdout, missing Gazebo executable, nonzero exit, transient startup gaps, and mutated SDF/YAML configuration. All are **mock/statically constructed inputs**; do NOT label them live Gazebo results.
4. Re-ran the full regression suite; check `verification/v21/V21_VERIFICATION.json` and verbose unit log for exact counts. `ros2`, `gz`, Jev/Qwen credentials were unavailable in this runtime.
5. Explicitly keep both independent ROS motion/authorization auditing and camera timestamps from v2.0. A Gazebo topic appearing in `gz topic -l` by itself is not movement or even a proof that data are arriving.

## Why this increases the chance of a strong submission

| Assignment dimension | Observable addition | Required external proof |
|---|---|---|
| 創造性 | AI decides at the actual supply station whether to proceed | Footage of correct and incorrect supplies with different actions |
| 技術力 | Multi-layer SDF/Transport/ROS/guard preflight, independent movement evidence | Real ROS-Gazebo logs, camera/scan/odom, emergency-stop recovery |
| 実用性 | Fail closed on missing camera/clock/scan transport; detect failure *before* motion | Empirical false-allow / false-reject rates and failure conditions |
| 表現力 | Precisely named diagnostic files, structured evidence, 3-page PDF draft | 60–180s real Gazebo action video + real results and visuals |

## Sources and what they actually establish (checked 2026-10-16)

- Course 10/8 brief (user-provided, primary assignment): exact evaluation axes, submission procedure and Nov 2 at 10:00 JST deadline. No rubric weights.
- Gazebo Harmonic official ROS 2 integration: https://gazebosim.org/docs/harmonic/ros2_integration/ — bridge mappings, `GZ_TO_ROS` / `ROS_TO_GZ` and launch arguments. Does **not** demonstrate this particular scene executing.
- Gazebosim maintained `ros_gz_bridge` README and launch source: https://github.com/gazebosim/ros_gz/blob/ros2/ros_gz_bridge/README.md and https://github.com/gazebosim/ros_gz/blob/ros2/ros_gz_bridge/launch/ros_gz_bridge.launch.py — sample QoS/clock and YAML contracts. Software may differ in installed Jazzy package; verify on target PC.
- Gazebo Harmonic official sensor example: https://github.com/gazebosim/docs/blob/master/harmonic/tutorials/sensors/sensor_tutorial.sdf — an instance of DiffDrive/sensor tags, not proof our robot physics are correct.
- Alibaba Cloud Qwen3.8-Omni-Flash product documentation (updated Sep 30, 2026): https://www.alibabacloud.com/help/ja/model-studio/qwen3-8-omni-flash — image/text input support and text output. This does not establish runtime inference success or model superiority.
- Jev 1.14 discussion and preview examples: https://www.jevtypesafeai.com/jev-1-14 and https://jevwiki.ai/wiki/concepts/images.md — describes Jev 1.14 experimental image/Box (with necessary opt-in header, and Box requiring a separate presence question). These are **gateway/wiki reproductions**, not authenticated API execution, and official `docs.typesafe.ai/images` could not be retrieved in this run. **Runtime integration remains unverified**.

## Actual deliverables still missing

- Gazebo moving on user's Ubuntu/NVIDIA machine, and bridge topics receiving actual sensor payloads.
- Authenticated Jev 1.14 and Qwen3.8 image inference on recorded real ROS/Gazebo frames.
- Held-out image benchmark and full 60–180s submission MP4.
- PDF final updated with measured values (current v2.1 is explicitly a DRAFT), public GitHub URL, YouTube URL.

## Scope: the task is not physical delivery

No arm, gripper, cargo or actual item transport is implemented. Current experiment is **supply-station confirmation and shelter-approach navigation**, with a separate fail-closed safety relay. Neither Gazebo-run confirmation nor operational safety certification has been performed.
