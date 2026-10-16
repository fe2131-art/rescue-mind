# RescueMind v1.8 — assignment-grounded award strategy and primary-source research

Document and research date: **2026-10-16 JST**. This is not a claim of real-Gazebo or live-model validation.

## The assignment is authoritative

`assignment/Physical-AI応用1講座-最終課題.txt` specifies a creative AI-guided robot task; AI inference is sufficient (no mandatory training). Scoring additions are **創造性・技術力・実用性・表現力**; no numerical weighting was given. Robot task footage 60–180 seconds, public GitHub code, PDF report and YouTube URL are the deliverables. Deadline **2026-11-02 10:00 JST**. Physical transportation is not mandatory, but a robot must *execute a task* on video. Do not paste tutorial samples unchanged.

## Reality-first technical priority

1. **By Oct 20**: capture actual Gazebo driving plus independent ROS odometry from the separate process. Refuse success if there is no observed movement.
2. **By Oct 23**: record fresh on-site Gazebo camera images, authenticate Jev API 1.14.0 and Qwen 3.8 API. If integration fails, simplify scene/route; do not claim artificial allow/deny is an actual AI decision.
3. **By Oct 26**: record paired **real** success/deny missions with same start pose, lighting and camera pose. Keep abnormal logs.
4. **By Oct 29**: benchmark at least 20 annotated images per supply class as an initial target (more if feasible) plus negative/uncertain scenes; compare Jev-only, Qwen-only and dual approval. Report **false approval** and **false rejection**, model latencies, paired differences and confidence intervals. Heuristic thresholds are not calibrated precision estimates.
5. **By Oct 31**: cut 120-s YouTube movie with exact 1–3-minute compliance, check public repo, no personal info and PDF evidence. Submit before 2026-11-02 10:00 JST.

## How the 4 criteria should appear in the 120-second video

| Time | Scene and evidence | Criteria |
|---|---|---|
| 0:00–0:15 | Hazard response mission and Japanese instruction; actual Gazebo world | Creativity, applicability |
| 0:15–0:45 | Mobile robot proceeds to station; show `/odom` or trajectory overlay | Technical skill |
| 0:45–1:10 | **Fresh** on-site camera frame and genuine Jev/Qwen judgments; decision gate | Technical skill, creativity |
| 1:10–1:35 | Correct supply: next-leg movement; wrong supply: fail-closed in a real paired run | Applicability, narrative |
| 1:35–2:00 | Measured error/coverage/latency table with failure-case caveats | Expression and rigor |

All timestamps in the video are only storyboard targets. Use real footage, not simulated illustrations labelled as Gazebo proof. The robot approaches and checks a supply station then approaches shelter B; no physical object pickup/delivery is implemented. **This custom arena does not demonstrate Nav2 dynamic replanning.**

## Primary external sources actually reviewed

* TypeSafe official release: https://typesafe.ai/blog/jev-1-14 — `jev-1.14.0` image and Box are *experimental*, opt-in (`TypeSafe-Danger-Zone-Images: true`).
* Jev API documentation: https://www.jevtypesafeai.com/clerk_1790100707857/docs — Box always returns coordinates even when target absent; pair with a separate presence question. **This documentation is a third-party mirror, not first-party TypeSafe docs**; actual response contracts need authentication tests.
* Alibaba Cloud model official: https://www.alibabacloud.com/help/en/model-studio/qwen3-8-omni-flash (updated 2026-09-28): `qwen3.8-omni-flash` image input, text output; region-specific API key.
* Alibaba Cloud API examples: https://www.alibabacloud.com/help/en/model-studio/qwen-omni — Chat Completions image example uses region-specific `DASHSCOPE_BASE_URL`, `modalities=["text"]`, `stream=True`.
* Gazebo official pairing: https://gazebosim.org/docs/harmonic/ (Noble/ROS Jazzy recommendation).
* Gazebo Ubuntu official: https://gazebosim.org/docs/harmonic/install_ubuntu/ (`gz-harmonic` on Noble).
* `ros_gz` official examples: https://github.com/gazebosim/ros_gz/blob/ros2/ros_gz_sim_demos/README.md (reliable command delivery, sensor bridges).

Sources above verify existence/formats, NOT project installation/runtime behavior. Verify API compatibility with the actual subscribed Jev and Alibaba workspaces before any claim of working recognition.

## Results that are safe to report today

* Python regression test count: see **generated** `verification/v18/v18_TEST_REPORT.json` (actual result, not a predetermined claim).
* Deterministic ideal unicycle with scripted AI permit/deny: six previously implemented cases, explicitly **not ROS/Gazebo/model inference**.
* New independent movement evidence checker: synthetic nominal and five adversarial cases executed with actual code; neither Gazebo nor an authenticated sensor source was involved.
* Still **NOT VERIFIED**: actual Jev/Qwen image understanding, actual `/odom` emitted by real Gazebo, real robot movement, genuine 60–180s video, GPU performance.

## Remaining risks

* ROS topics are not authenticated by this log validator; a spoofed publisher can produce a plausible trajectory. Independent topic observations are more useful than a self-reported goal receipt but are not strong provenance.
* Velocity relay cannot physically guarantee motor stop after its own crash. Simulator research only; not a real safety controller.
* VLM disagreement can improve caution but also increase missed opportunities. Measure both mistakes under human-labelled scenes.
* API costs, network delays and regional availability are not measured yet. Never publish credentials.
