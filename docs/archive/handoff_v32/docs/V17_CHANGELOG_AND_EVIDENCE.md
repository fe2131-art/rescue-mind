# v1.7 improvement loop and evidence map

## Audit → improvement → execution

1. **Audit:** v1.6 had 198 passing Python tests but no test driving `WaypointController` into `VelocityRelay` across full scripted missions. Prior synthetic conditions tested the relay largely in isolation.
2. **Implementation:** new `rescuemind/closed_loop_twin.py` builds a deterministic 100ms simulator using the actual controller and actual relay decision core, with simulated camera/LiDAR/odometry messages and a scripted (NOT AI) station permit.
3. **Contrasting cases:** nominal route vs denied second leg, front obstacle, stale command, frozen camera, frozen odometry. Run outputs in `verification/v17/closed_loop_*.json`.
4. **Cross-file integration audit:** new `rescuemind/stack_contract.py` tests Gazebo joint names/ROS topics/bridge direction/supervisor guard start + waypoint proximity. Negative tests deliberately break bridge direction and guard name to prove the checker catches errors.
5. **Unit verification:** `verification/v17/v17_TEST_REPORT.json` plus `v17_unittest.log`; release packaging independently extracts and reruns the tests.
6. **Limitations:** no ROS 2, Gazebo, NVIDIA GPU or external API credentials available in this execution environment; no original robot footage claimed.

## Evidence hierarchy

| Grade | Artifact | What it demonstrates |
|---|---|---|
| A: actual robot+API | None yet | NOT achieved. Required for award-quality result. |
| B: real Gazebo but scripted AI | None yet | Would validate locomotion; not AI inference. |
| C: deterministic closed-loop with scripted data | 6 new scenario JSONs | Controller/relay integration and defined fault reaction only. |
| D: static / isolated tests | 207 Python tests, static cross-file check | Code-level logic and configuration relationships only. |
| E: proposals | storyboard, report draft | Plans, not evidence of execution. |

## Precise claims to avoid

- No actual VLM recognition success-rate estimates can be derived from the scripted test.
- A stationary robot shown in Gazebo is not evidence of successful Jev/Qwen decisions.
- Simulated two-stage movement cannot be described as physical cargo delivery.
- Standalone on-paper test counts are not proof of Gazebo physics or safety certification.
