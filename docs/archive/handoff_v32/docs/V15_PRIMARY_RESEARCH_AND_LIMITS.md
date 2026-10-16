# v1.5 一次資料の調査記録（2026-10-16）

| 確認した対象 | 一次資料 | 確認した内容 | 注意 |
|---|---|---|---|
| 講義最終課題 | `assignment/Physical-AI応用1講座-最終課題.txt` | 1〜3分、GitHub public、PDF、YouTube、評価4軸 | 賞の定量配点は無し |
| Gazebo Harmonic連携 | https://gazebosim.org/docs/harmonic/ros2_integration/ | ROS-Gazebo topic bridge と `[`/`]` 方向 | ROS本番通信は未実測 |
| Gazebo DiffDrive | https://gazebosim.org/api/sim/8/classgz_1_1sim_1_1systems_1_1DiffDrive.html | left/right joint・wheel radius・topic・odom topic | 明示されたコマンドtimeoutの保証は確認できない |
| ROS/Gazebo移植資料 | https://gazebosim.org/docs/harmonic/migrating_gazebo_classic_ros2_packages/ | odom / cmd_vel / scan のマッピング例 | 本プロジェクト独自worldの保証ではない |
| Jev画像API | https://typesafe.ai/blog/jev-1-14 | jev-1.14.0、画像とboxを実験的に提供 | 画像はdanger zone機能、APIキー必須 |
| Jev詳説 | https://docs.typesafe.ai/go/images ; https://docs.typesafe.ai/go/box | 公式ブログの参照先 | 詳細ページはこの調査環境から本文取得不能、実API契約は未検証 |
| Qwen3.8-Omni-Flash | https://www.alibabacloud.com/help/en/model-studio/qwen3-8-omni-flash | 画像を含むマルチモーダル入力からテキストを出力、リージョン別キー | 提供元仕様。モデル認識性能の実測ではない |
| Qwen Omni API | https://www.alibabacloud.com/help/en/model-studio/qwen-omni | Chat Completionsの画像入力例 | 使用リージョンとエンドポイントを合わせる |

## 改善サイクルの発見

- 調査：ROS topicが1件通ることは、実際のセンサー形式や時間進行の健全性を保証しない。
- 改善：`rescuemind/sensor_contract.py` にカメラバイト数・画像エンコーディング・カメラ/scan/odomの時刻単調性、scan値と姿勢クォータニオン検査を追加。`scripts/v15_ros_sensor_probe.py` が本物のROSトピックを読む、**指令を書き込まないread-only診断**。
- 検証：`tests/test_v15_sensor_contract.py` は静的モックメッセージ・異常なバイト/scan/odometry入力をテスト。ROS2自体の起動は未実施。
- 統合：`scripts/v15_orchestrate.py` の起動ゲートをv1.5の実データreadinessへ変更。失敗時には移動プロセスが起動しない。

## 評価の重要な限界

- 画像が技術的にデコード可能でも、物資が正しく撮れていることは別の評価。
- lidar/odomが適切でも、マップ座標・遮蔽物・衝突が正しい保証にはならない。
- JevとQwenは同じ見落としをする可能性がある。モデルの出力一致だけを安全保証としない。
- 走行監視はシミュレータ向けの研究実装であり、実機の機能安全認証を持たない。
