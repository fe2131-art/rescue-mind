# v2.6 変更履歴とテスト境界

前回v2.5の `camera_aim_aligned` → 新規カメラフレーム → Jev＋Qwenの間に、ロボットが物理的に静止したことの **Odometry twist＋位置・姿勢の連続検査**を追加。

主なコード：`rescuemind/stationary_gate.py`、`ros/gazebo_waypoint_mission.py`、`rescuemind/v26_stationary_evidence.py`、`scripts/v26_stationary_campaign.py`、`scripts/v26_orchestrate.py`、`tests/test_v26_stationary.py`。

- カメラ方向合わせが終わっても、Odometry速度・位置・姿勢が落ち着くまでAI画像は撮らない。
- オドメトリが安定した後に新しいROSカメラ画像を取得する。
- Jev/Qwen推論と拒否の停止維持の最中も、観測姿勢が変われば失敗。
- 正常到達と意図した拒否の両方で、撮影前の静止イベントを実行監督が必須とする。
- v2.5の人工ROS模擬を拡張し、停止指令後に外力で移動し続ける場合を故障注入。
- 12人工時系列、静止時系列CSV、全374回帰テスト、実行計画4、従来の9拒否条件をオフラインで検証。

**重要:** モデル実APIとGazebo物理走行の実証はまだない。静止閾値は「オドメトリ上の低速」を示すだけで物理安全規格ではない。
