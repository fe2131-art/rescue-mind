# outputs/（ローカル実行の生成物。Git管理外）

- `runs/<run_id>/`：`scripts/v32_orchestrate.py --run` 1回分の全記録（各プロセスのログ、`mission.json`、判断に使った `checkpoint.jpg`、
  独立レコーダの `independent_ros_topics.jsonl`（オドメトリ・速度・Gazebo真値）、`rosbag2/`（MCAP）、`stack_result.json`、
  `--film` 指定時は `film/`（俯瞰カメラとロボットカメラのフレーム））。数GBになるため公開しない。
- 公開用の要約コピーは `scripts/export_evidence.py` で `experiments/results/evidence/<run_id>/` に作成（ホストのパスは除去）。
- `video/`：`scripts/make_demo_video.py` が出力する提出動画。
