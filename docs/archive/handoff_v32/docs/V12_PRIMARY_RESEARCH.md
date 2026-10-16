# 2026-10-16 一次資料/近接資料チェック

## 課題原文（配布ファイル）

`assignment/Physical-AI応用1講座-最終課題.txt`：創造性、技術力、実用性、表現力。提出：実行動画1–3分、PDF説明資料、public GitHub URL、YouTube URL。締切11/2 10:00 JST。

## 調査資料（閲覧日2026-10-16）

1. Gazebo Harmonic ROS2統合: https://gazebosim.org/docs/harmonic/ros2_integration/ — `ros_gz_bridge` のメッセージブリッジ、方向識別（`]` ROS→Gazebo、`[` Gazebo→ROS）。
2. ros_gz_bridge GitHub: https://github.com/gazebosim/ros_gz/blob/ros2/ros_gz_bridge/README.md — `geometry_msgs/msg/Twist`、`nav_msgs/msg/Odometry`、LaserScan、Imageなどのブリッジが掲載されている。
3. Gazebo Sim 8 DiffDrive reference: https://gazebosim.org/api/sim/8/classgz_1_1sim_1_1systems_1_1DiffDrive.html — `topic`,`odom_topic`,`wheel_radius`, `wheel_separation` の仕様。**こちらが必要とする`cmd_vel`指令の最大保持時間を保証するtimeoutパラメータを、この公開API説明では確認できなかった**。このため指令切れにゼロ速度を送る別プロセスを追加。ガード自体がクラッシュした場合の停止は保証できない。
4. Nav2 Jazzy quickstart: https://docs.nav2.org/jazzy/getting_started/quickstart/quickstart/ — JazzyでのTurtleBot3サンプルの再現、OSとパッケージ条件。独自Gazeboワールドの直接駆動はNav2動作の証拠ではない。
5. Nav2 Simple Commander API: https://docs.nav2.org/jazzy/configuration_and_development/simple_commander_api/simple_commander_api/ — `goToPose`、`cancelTask`、ライフサイクル待機など。
6. Jev 1.14 情報: https://www.jevtypesafeai.com/jev-1-14 、https://www.jevtypesafeai.com/typesafe/docs 。画像入力・Boxと`TypeSafe-Danger-Zone-Images`、Boxに対しNoulで対象存在判定を行う注意が記載。ただし本ドメインは**TypeSafe直営サイトであると独立確認できていない第三者の公開説明**。実際のサービスでの互換性はAPIキー取得後に検証必須。
7. Jev API endpoint説明: https://www.jevtypesafeai.com/jev/api 。`api.typesafe.ai/v1/systemone` と `jevtypesafeai.com/api/v1/decide` の区別。現在コードは公式TypeSafe経路のURLを固定しており、**その公式API自体への実接続はできていない**。
8. Qwen3.8-Omni-Flash model info: https://www.alibabacloud.com/help/en/model-studio/qwen3-8-omni-flash — Alibaba Cloud公式、2026-09-28更新。画像・音声・動画入力、テキスト出力。利用可能リージョンとモデルID `qwen3.8-omni-flash`。
9. Qwen Omni呼び出し方法: https://www.alibabacloud.com/help/en/model-studio/qwen-omni — Alibaba Cloud公式、2026-10-15更新。Chat Completionsのリージョンごとのworkspace base URL・APIキーを参照。

## 何を主張できないか

- Web上のドキュメントを読めたことは、API資格情報でのリクエスト成功を意味しない。
- ストリーミングをモックした単体テストは、Qwen3.8実出力の形式・精度・速度を保証しない。
- 153件以上のPythonテストが通過しても、Gazeboの接地・衝突・カメラ描画・ROSネットワーク動作は保証しない。
- 独立ガードのソフトウェア試験は、人間や実機の機能安全を保証しない。
