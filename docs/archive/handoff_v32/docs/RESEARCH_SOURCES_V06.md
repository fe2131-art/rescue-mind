# 出典確認と採否の記録（確認日：2026-10-16 JST）

## 講座原文（一次資料）

- `assignment/Physical-AI応用1講座-最終課題.txt`（10/8版）：1～3分のロボット実行動画、コード、PDF、公開GitHub、YouTube URL、2026/11/2 10:00。創造性・技術力・実用性・表現力を加点観点とする。数値の採点配分は記載なし。

## 外部一次資料（API仕様の裏付けであり、私たちの実測ではない）

1. Jev TypeSafe System One API: <https://www.jevtypesafeai.com/clerk_1790100707857/docs>。`jev-1.14.0`の画像入力、`box`は「見つからない」を返さないため`noul`併用、opt-in images headerが必要と明記。画像機能は実験的。
2. TypeSafe docs: <https://docs.typesafe.ai/images> / <https://docs.typesafe.ai/primitives/box>。v0.5のHTTPクライアント構成を参照。ただし本APIへ通信していないため動作保証はしない。
3. Alibaba Cloud Qwen3.8 Omni Flash: <https://www.alibabacloud.com/help/en/model-studio/qwen3-8-omni-flash>。2026/9/28更新、画像→テキスト出力、対応リージョン、Chat Completions/Responses。
4. Alibaba Cloud Omniモデル一覧: <https://www.alibabacloud.com/help/en/model-studio/model-list-omni/>。2026/10/11更新の一覧に`qwen3.8-omni-flash`がある。最新モデルだと断定しない。地域やモデル可用性が変わり得る。
5. Alibaba Cloud multimodal API: <https://docs.modelstudio.console.alibabacloud.com/en/model-studio/qwen-omni>。ワークスペースURLが地域により異なる。SDKバージョン・OpenAI互換endpointに注意。
6. Nav2 first-time setup Gazebo: <https://docs.nav2.org/jazzy/configuration_and_development/first_time_robot_setup_guide/gazebo/>。独自ワールドにNav2を載せるにはTF/odom/localization/sensorをそれぞれ構成しなければならない。
7. Nav2 Quickstart: <https://ros-navigation.github.io/mkdocs.nav2.org/jazzy/getting_started/quickstart/quickstart/>。`ros2 launch nav2_bringup tb3_simulation_launch.py headless:=False`。
8. Nav2 Collision Monitor: <https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/core_servers/collision_monitor/>。CPUソフトウェアによる追加緊急停止処理。安全認証機器ではない。
9. Gazebo Harmonic ROS 2 integration: <https://gazebosim.org/docs/harmonic/ros2_integration/>。`ros_gz_bridge`のメッセージ変換。
10. Gazebo ROS/GZ bridge README: <https://github.com/gazebosim/ros_gz/blob/ros2/ros_gz_bridge/README.md>。`/TOPIC@ROS_MSG]GZ_MSG`方向はROS→Gazebo。`[`方向は逆。画像・Twist・Odometry・LaserScanを確認。
11. Gazebo Harmonic diff drive: <https://gazebosim.org/docs/harmonic/moving_robot/>。joint / wheel separation / topic / odom のSDF書式。
12. Nav2 Odometry Gazebo: <https://docs.nav2.org/jazzy/configuration_and_development/first_time_robot_setup_guide/odom/setup_odom_gz/>。`gz-sim-diff-drive-system`からオドメトリ。

## どの情報が事実確認できていないか

- JevやQwenが**このSDFで生成した画像の水/救急箱を本当に認識できるか**：未検証。
- Gazebo worldのレンダリング、wheel physics、camera topic名：実起動なし。SDF XML・構成要素をオフラインで検証しただけ。
- `ros_gz_bridge`の本物のROS環境での通信：未検証。
- LiDAR watchdogが実際に障害物の前で何秒で停止するか：未検証。
- Jevのboxを直接障害物回避に用いる設計ではない。画像上の相対座標がマップ座標になるわけではない。
- 現時点の成果物にはAI推論精度、ROS走行成功率、実験ビデオに基づく数字は存在しない。
