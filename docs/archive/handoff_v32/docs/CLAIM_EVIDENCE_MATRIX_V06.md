# 証拠・主張の対応表（発表で必ず守る）

| 主張 | 判定 | どのコード/ファイルを参照するか | 注意点 |
|---|---|---|---|
| Jevが必須の安全ゲートがある | コード・モックテストで確認 | `rescuemind/multimodal_demo.py`, `safety.py` / `tests/*` | モックの`real_model`を編集できる点は認証ではない |
| Qwen3.8のSSEプロトコルを処理できる | 人工ストリーム試験済 | `rescuemind/qwen35.py`,`streaming.py` | Alibaba本APIのレスポンスは未取得 |
| ROS2 Nav2のタスク取得・キャンセルコードがある | 模擬ROS試験で確認 | `ros/nav2_mission.py`,`tests/test_ros_fake_integration.py` | 実ROS2/Nav2での挙動ではない |
| ROS2 Gazebo direct-driveの運動コントローラ実装 | 理想運動学で検証 | `ros/gazebo_waypoint_mission.py`, `rescuemind/waypoint.py` | 実Gazeboで車輪駆動テスト未実施 |
| 2D障害物を避けた経路の安全性 | 単純矩形近似のみ | `rescuemind/arena_geometry.py`, `outputs/release/v06_waypoint_regression.json` | Gazeboでは衝突/摩擦/車輪動作が異なる |
| A*再計画が有利なこと | 自作格子環境の10ケースで確認 | `outputs/release/trials.csv`,`rescuemind/evaluate.py` | Nav2の再計画を実測したわけではない |
| Jev+Qwen合意で誤許可が減る | **未検証** | `docs/EXPERIMENT_PROTOCOL.md` へ実測追記予定 | この段階で「改善した」と断言しない |
| Gazeboでロボットが実走行した | **未検証** | Ubuntuで `docs/V06_GAZEBO_EXECUTION.md` を実行後に証拠を保管 | 現ZIP内に実Gazebo録画なし |
| 最終課題の動画提出要件を満たす | **未達** | YouTubeに1〜3分の本物のロボット動画が必要 | 数式モデルのMP4は代替にならない |
| 実装・コードは第三者が再実行できる | Python部分は再展開・テストで確認 | `README.md`,`scripts/verify_all.sh`,`SHA256_MANIFEST.json` | APIキーやROSは利用者が準備 |
