# 一次資料の確認記録（2026-10-16 JST）

調査時点で開けた公式公開ドキュメントを挙げる。各資料で**確認できた範囲**と、ローカルで実際に試していない部分を区別する。

| 技術/資料 | 公式URL | 確認内容 | 未確認 |
|---|---|---|---|
| Jev 1.14 | https://typesafe.ai/blog/jev-1-14 | 画像入力と実験的`box`、`TypeSafe-Danger-Zone-Images: true`が必要 | 実APIキーによる応答精度/料金 |
| Jev images | https://docs.typesafe.ai/go/images | preview画像を参照して決定する方式（TypeSafe公式ブログから参照） | ライブ環境での画像デコード成功 |
| Jev box | https://docs.typesafe.ai/go/box | `box`が存在しない対象にも矩形を返し得るのでNoulとの組合せが必要 | 現地の小さなボトル・救急箱の精度 |
| Qwen3.8-Omni-Flash | https://www.alibabacloud.com/help/en/model-studio/qwen3-8-omni-flash | 2026-09-28更新、テキスト/画像/音声/動画入力、テキスト出力、各リージョンのAPIキー | 契約/リージョン/APIキーを使った応答 |
| Gazebo ROS 2 Integration | https://gazebosim.org/docs/harmonic/ros2_integration/ | `ros_gz_bridge`トピック方向 `]` ROS→Gazebo、`[` Gazebo→ROS | カスタムSDFの物理シミュレータ起動 |
| Gazebo diff-drive demos | https://github.com/gazebosim/ros_gz/blob/ros2/ros_gz_sim_demos/README.md | DiffDrive+odometryとROSコマンドの実例 | 独自ロボットの車輪ジョイント・摩擦の妥当性 |
| Nav2 Jazzy Simple Commander | https://docs.nav2.org/jazzy/configuration_and_development/simple_commander_api/simple_commander_api/ | 非同期`goToPose()`/`cancelTask()`等を確認 | 独自Gazeboワールドでの完全Nav2統合 |

**評価上の線引き**: 上記公式説明の読み取りは文書検証であり、API/Gazeboの動作確認結果ではない。`scripts/validate_gazebo_world.py`が証明するのは静的XML/橋接/理想2D幾何だけである。
