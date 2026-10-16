# RescueMind v1.7 | Evaluation strategy, primary sources, limitations

Document review date: 2026-10-16. These are **external public-source checks**, not observed Gazebo/API execution.

## Assignment-derived non-negotiable requirements

Read `assignment/Physical-AI応用1講座-最終課題.txt` (10/8 version). Required: AI used somewhere, robot executing a participant-defined task, 1–3 minute actual robot video, source files on a **public** GitHub repository, PDF report, YouTube URL, anonymous presentation. Scoring additions: **creativity, technical sophistication, practical relevance, presentation quality**. Deadline 2026-11-02 10:00. Code-only prototypes do **not** satisfy the requirement for video of a robot operating.

## Verified public documentation

| Provider / primary source | Verified claim | Implementation effect | Uncertainty |
|---|---|---|---|
| Gazebo: https://gazebosim.org/docs/harmonic/install_ubuntu/ | Harmonic binaries available for Ubuntu 24.04. | Use Ubuntu 24.04. | Does not show this SDF actually runs. |
| Gazebo ROS pairing: https://gazebosim.org/docs/harmonic/ros2_integration/ | ROS bridges carry Gazebo messages across topic interfaces. | Bridge `/cmd_vel` to DiffDrive and `/odom` `/scan` `/camera` to ROS. | Topic names & actual DDS QoS must be runtime-probed. |
| ROS Nav2 guide: https://docs.nav2.org/jazzy/configuration_and_development/first_time_robot_setup_guide/odom/setup_odom_gz/ | ROS-GZ bridge requires explicit directions/types, e.g. odometry Gazebo→ROS, velocity ROS→Gazebo. | Add cross-file direction/type tests. | This project uses direct go-to-goal, **not** a Nav2 global planner in its own Gazebo arena. |
| Official ROS/GZ examples: https://github.com/gazebosim/ros_gz/tree/ros2/ros_gz_sim_demos | DiffDrive and camera bridges are officially demonstrated. | Prefer known message types, inspect DDS QoS if silent. | Their example does not validate our arena. |
| Alibaba Cloud: https://www.alibabacloud.com/help/en/model-studio/qwen-omni | `qwen3.8-omni-flash` can take an image and produce text via Chat Completions; workspace URL is region-specific. | Qwen cloud mode with explicit workspace endpoint and auth, never automatic fallback. | Credentials required for actual inference; version/regional availability can differ. |
| Jev first-party docs (links supplied in earlier project): https://docs.typesafe.ai/images ; https://docs.typesafe.ai/primitives/box | v1.14 vision + box described as experimental; presence check required since box may always be emitted. | Pinned Jev 1.14.0, explicit opt-in images header, separate presence question. | First-party docs could not be retrieved by web fetch in this run. MUST check in console using live account before interpreting API response. |
| Jev non-first-party documentation: https://www.jevtypesafeai.com/jev-1-14 ; https://www.jevtypesafeai.com/jev/api | Independent gateway describes 1.14 image + box and official API endpoint. | Corroborating, **not a substitute for first-party confirmation**. | Independent website; no authenticated API call made. |

## Strategic ranking against the four scoring criteria

1. **Deliverable first**: obtain 60–180s **real Gazebo video** of sensor-driven robot (the major missing evidence).
2. **Creativity**: show the *same* observed station with a correctly recognized supply and with a mismatch; continuation vs denied second leg proves causal use of perception.
3. **Technical**: provide ROS topic graph, run IDs, camera acquisition stamps, Jev + Qwen original responses, guard logs and robot trajectory.
4. **Practical relevance**: measure unsafe authorization, unnecessary rejection, response latency, travel distance, and mission success (mean with confidence intervals). Never call toy scripted cases real recognition accuracy.
5. **Presentation**: use ~120s story: problem (10s), AI decision & sensor image (30s), motion (40s), mismatch fail-closed (25s), actual paired results & limitations (15s).

## Adversarial measurement plan

Keep every physical scene/lighting/camera pose pair fixed between methods. Collect at least 20 images per supply type **plus** ambiguous/obstructed views when feasible. Set human-reviewed labels with unknown allowed, blind to model outputs. Save timestamp, hashes, raw replies, model ID, confidence, latency, policy decision, ground-truth label, and robot behavior. Compare Jev-only, Qwen-only, dual agreement, and a non-AI lookup baseline. Do not fake measurements or substitute mock data. Report precision/recall and false-approval conditional on the true scene; false-rejection and coverage also matter. Confidence thresholds must be selected on a separate development set or clearly called heuristic.

## Fallback deadlines and risk

Deadline is **November 2 at 10:00 JST**. By Oct 20: Gazebo solo motion + sensor topics. By Oct 23: checkpoint camera and at least one authentic Jev/Qwen image response. By Oct 26: full robot behavior or narrow to reproducible two-step mission. By Oct 29: compare recorded observations and produce the video. By Oct 31: release/public URL/PDF/YouTube check. If real VLM unavailable, use a **genuine different AI system**, document the substitution and results honestly; do not count a scripted decision as the assignment's AI requirement. If Gazebo fails, use another allowed simulator or a verified actual robot execution rather than passing off a Python animation as a robot video.

## Model + safety limitations

The project is a mobile robot **waypoint approach** task; it does not grasp or carry cargo. The custom Gazebo arena lacks the complete Nav2/AMCL/TF/map pipeline for dynamic rerouting. Camera semantic hazard judgments alone do not locate hazard coordinates. Relay is a simulated fail-stop prototype, not an independently certified safety device. Backend credentials, actual Jev/Qwen recognition, image rendering and actual Gazebo motion remain unverified here.
