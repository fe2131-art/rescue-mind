# v1.8 -> v1.9 verified implementation loop

## Problem found

The v1.8 independent trace checked that the same run observed supply and shelter in sequence, but did **not** match these visits against when on-site Jev+Qwen authorization occurred. Thus a physically impossible story could pass if the ROS trace showed the shelter reached while the AI was still evaluating the station.

## Fix

1. Add `mission_start_unix_ns` to mission runtime and explicit host time basis. The existing `t_wall_s` events are anchored to this start.
2. New `rescuemind/causal_evidence.py`: verify chronological order, independently observed station dwell, no unauthorized departure, and shelter arrival only after authorization. Compare host wall timestamps with host wall timestamps, not ROS simulation time with host Unix time. Safety posture remains fail-closed.
3. Wire it into `scripts/v16_orchestrate.py` and `scripts/v18_verify_run.py`. Non-AI motion-check is not inaccurately described as a VLM run.
4. Optional `--capture-rosbag` with `SIGINT` finalization and required-topic/DB metadata checking. ROSbag metadata does not authenticate the process or prove a picture represents a certain world.
5. 10 deterministic synthetic timeline test scenarios + unit tests + reused fault campaigns and static checks. Real Gazebo and external APIs remain untested.

## Runtime limits and remaining risks

- No real ROS/Gazebo executable in this authoring container, nor credentials. ROS bag integration is API-aligned code with mocks/metadata fixtures, not field-validated.
- API latency may make station dwell long, camera may fail due to rendering or GPU driver, ROS timestamps/wall clocks may be inconsistent. These must be checked on Ubuntu.
- Clock discontinuities cause rejection; that is preferable to spurious PASS. Independent ROS telemetry may be spoofed and does not prove real physics. Neither this code nor Jev box estimates are safety-certified.
- Nav2 global replanning and actual emergency goods transport are not included in the active lane. Avoid claiming them in video.
- Further value depends on actual camera content, illumination, physically plausible interactions, real failure rates, and a demonstrable robot task video.
