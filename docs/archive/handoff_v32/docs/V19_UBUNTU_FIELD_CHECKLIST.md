# v1.9 Ubuntu real-run field checklist

## Prerequisite validation

1. Verify Ubuntu release and NVIDIA driver: `cat /etc/os-release; nvidia-smi`.
2. Verify `source /opt/ros/jazzy/setup.bash`, `ros2 --help`, `gz sim --help`, ROS bridge: `ros2 pkg prefix ros_gz_bridge`.
3. Verify rosbag installed: `ros2 bag record --help`; if absent, install distro-matched `ros-jazzy-rosbag2` via apt (after setting up ROS apt sources).
4. Use `bash scripts/setup_ubuntu_jazzy.sh` before running Python mission if apt `rclpy` is not visible inside a vanilla venv.
5. Save console output privately and scrub any identifying data. Do NOT log, echo or record secret API keys.

## Motion-only trial

```bash
python3 scripts/v16_orchestrate.py --plan --scenario motion-check --capture-rosbag
python3 scripts/v16_orchestrate.py --run --scenario motion-check --capture-rosbag
```

If readiness fails, consult `outputs/runs/<id>/readiness_last.txt`, `gazebo.log`, `bridge.log`, `velocity_guard.log` and `independent_odom_recorder.log`. Use `ros2 topic list -t`, `ros2 topic hz /odom`, `ros2 topic hz /scan`, `ros2 topic hz /camera`, `ros2 topic echo /rescuemind/guard_ready --once`. Check `gz topic -l` for matching names. Do not manually publish to `/cmd_vel` while guard is running.

The result is valid *software evidence* only when the supervisor returns `COMPLETED`, the independent ROS path passes, optional bag metadata passes and actual footage visibly depicts robot travel. Motion-check **does not** satisfy the course's AI requirement.

## Jev/Qwen live trial

Set `TYPESAFE_API_KEY`, `DASHSCOPE_API_KEY`, `DASHSCOPE_BASE_URL` in a private local shell/session, not in notebooks, source, screenshots or transcript. Then:

```bash
python3 scripts/v16_orchestrate.py --run --scenario live --capture-rosbag \
  --instruction '避難所Bに飲料水を届けて'
```

The same run directory must show:

- `mission.json`: on-site ROS capture, correct type, `checkpoint_decision` with allow, shelter arrived, image SHA.
- `independent_ros_topics.jsonl`: independent ROS odom trace and guarded published speed.
- `stack_result.json`: `state=COMPLETED`, `independent_motion_evidence.pass=true`, `authorization_motion_chronology.pass=true`, `rosbag_evidence.pass=true`.
- `rosbag2/metadata.yaml` and bag storage file. Inspect with `ros2 bag info ...`.
- A real Gazebo video (separately recorded). A JSON-only PASS is insufficient to claim physics.

Run postflight validation:

```bash
python3 scripts/v18_verify_run.py outputs/runs/<id> --scenario live
ros2 bag info outputs/runs/<id>/rosbag2
```

The physical world SDF robot has **no gripper or goods transporter**. Do not claim item delivery. If API calls fail or image does not contain the item, record the failed attempt and stop. No mock substitute in live mode.

## Demonstration video plan (2:00 target)

00:00–00:15 need/context; 00:15–00:30 live instruction and models; 00:30–00:55 vehicle approaches supply; 00:55–01:15 camera image and model outputs; 01:15–01:35 correct case moves; 01:35–01:50 wrong-item case stops; 01:50–02:00 real comparative results and limitations. If sped up, prominently label speed.

Sanitize UI tabs/usernames, API tokens, system paths, workspace data, email and non-public information before upload. Confirm PDF naming, public GitHub and accessible YouTube as specified in the original course assignment.
