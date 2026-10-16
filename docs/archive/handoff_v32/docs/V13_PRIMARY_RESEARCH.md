# 一次資料・仕様確認（2026-10-16）

※以下は公開仕様の調査。ローカル実装での接続成功とは区別する。

| 対象 | 一次資料URL | 確認できた内容 | 未確認・リスク |
|---|---|---|---|
| 講座 | `assignment/Physical-AI応用1講座-最終課題.txt` | 合格要件、4評価基準、2026-11-02 10:00 JST締切 | 配点・審査者による重みは非公開 |
| Jev | https://typesafe.ai/blog/jev-1-14 | 画像とBoxは実験機能、`TypeSafe-Danger-Zone-Images: true` | 実APIの認証・応答/認識精度は未測定 |
| Jev API | https://www.jevtypesafeai.com/clerk_1790100707857/docs | `jev-1.14.0`, `box`(常に矩形)、存在確認には`noul`併用 | API変更・experimental preview |
| Qwen3.8 | https://www.alibabacloud.com/help/en/model-studio/qwen-omni | `qwen3.8-omni-flash` 画像→テキスト、Chat Completions、workspaceベースURLと地域キー | 課金/地域/APIアクセスは未確認 |
| Gazebo | https://gazebosim.org/docs/harmonic/ros2_integration/ | `ros_gz_bridge`の方向指定`[`/`]`、対象型 | 手元のROS/Gazeboトピックは実検証が必要 |
| Gazebo DiffDrive | https://gazebosim.org/docs/harmonic/migrating_gazebo_classic_ros2_packages/ | 左右車輪joint・wheel radius/separation、topic等 | センサーQoS、車輪の物理接地、速度指令途絶時の保証は未検証 |
| ROS Jazzy | https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html | Ubuntu 24.04 Noble向けdeb、`/opt/ros/jazzy/setup.bash` | ユーザーPCのUbuntu版は未確認 |

## 調査から採用した変更

1. Jevを必須の視覚判断部として明示し続ける。Qwen3.8のAPIはクラウド用に維持する。
2. Gazebo実走行の前にROSグラフ、Python `rclpy` import、画像/scan/odomの実配信を確認する。
3. Ubuntu apt版ROSのPythonモジュールを認識できる`--system-site-packages` venvを推奨。ただしユーザーPCでは未実行。
4. 速度監視は前方LiDARだけなので、後退速度は拒否。ROSの`Twist`は平面差動二輪の軸だけを許可する。

## 性能を主張しない項目

Jev+Qwenの一致は誤りの独立性を証明しない。AI誤許可率、誤拒否率、走行成功率、速度ガード実動作は実画像と実Gazeboで試すまで数値化しない。
