# RescueMind v1.0 一次資料調査・仕様確認（2026-10-16）

調査と実装の関係を明示する。オンライン検索で確認した*公式ドキュメント*と、v1.0の**ローカルで試験したコード**は異なる根拠階層で扱う。

| 技術 | 公式一次資料（リンク） | 確認した公開仕様 | 適用コード | 未検証 |
|---|---|---|---|---|
| TypeSafe Jev | https://typesafe.ai/blog/jev-1-14 および https://docs.typesafe.ai/go/images と https://docs.typesafe.ai/go/box | `jev-1.14.0` では実験的画像入力、`box`、画像 opt-in header。Boxは物体非存在でも矩形を返すため `noul` と併用 | `rescuemind/jev.py`, `checkpoint.py` | 実API認証、画像推論の正答率、キャリブレーション |
| Qwen3.8-Omni-Flash | https://www.alibabacloud.com/help/en/model-studio/qwen-omni および https://www.alibabacloud.com/help/en/model-studio/qwen3-8-omni-flash | 画像・テキスト入力、テキスト出力、クラウド Chat Completions、stream と `modalities:["text"]` | `rescuemind/qwen35.py`, `rescuemind/streaming.py` | 東京等の実ワークスペース接続、画像推論品質と遅延 |
| ROS 2/Gazebo | https://gazebosim.org/docs/harmonic/ros2_integration/ | ros_gz_bridge の `]` が ROS→Gazebo、`[` が Gazebo→ROS、センサー/速度コマンドの対応が必要 | `scripts/bridge_direct_gazebo.sh`, `worlds/rescuemind_test_arena.sdf` | 本物の ROS/Gazebo メッセージ通信、物理挙動 |
| Gazebo DiffDrive | https://gazebosim.org/api/sim/8/classgz_1_1sim_1_1systems_1_1DiffDrive.html | 車輪ジョイント、半径、車輪間隔、コマンドトピック、odomトピックなどを設定 | SDF DiffDriveプラグイン | 実駆動の安定性、衝突時挙動 |
| Nav2 | https://docs.nav2.org/jazzy/getting_started/quickstart/quickstart/ および https://docs.nav2.org/jazzy/configuration_and_development/simple_commander_api/simple_commander_api/ | Jazzy向けの公式Turtlebot3 QuickstartとBasicNavigator API | `ros/nav2_mission.py`（別経路） | 独自GazeboワールドでのNav2統合。TF/AMCL/mapsが未設定 |

## 実装上の注意

1. **Jev必須**：`TYPESAFE_API_KEY` がなく実API接続できない場合、ライブミッションを成功と主張しない。
2. **Qwen3.8はクラウド**。NVIDIA GPU上で直接動くオープン重みとして扱わない。ローカル代替は Qwen3.5-4B で、別の検証条件。
3. **二重判断≠独立判断**：2モデルの画像認識誤りは相関する可能性がある。合意していても安全確実とはいえない。
4. **画像のみでは通路安全を証明できない**。LiDAR Watchdog は停止用で、Nav2の自律迂回とは異なる。
5. **時刻は2種**：ROS画像headerの撮影時刻とアプリが受信したモノトニック時刻を区別。新鮮な画像の受信だけでは撮影時の鮮度を証明できない。
6. TypeSafe visionは実験的仕様。一次資料閲覧時点の仕様とAPI実行が一致しない可能性を実API試験で検証する。

## 研究設計への示唆

- Jev単体、Qwen単体、合意方式の*同一画像*ベンチマーク。真値はAPI出力から作らず、人手で独立にラベル付けする。
- 優秀賞の見せ場は物資の把持ではなく、**現地認識によって走行が分岐する様子**。動画では `supply_station` → on-site image → Jev/Qwen approval/denial → `shelter_approach` と表示する。
- 結果は安全例・危険例・画像認識が曖昧な例で分割。誤許可率と不要な拒否率を両方示し、信頼区間を併記。

> 最終課題原文由来：加点は創造性・技術力・実用性・表現力。動画は1〜3分、PDFとpublic GitHub URLとYouTube URLが必要。提出期限は2026-11-02 10:00 JST。上記モデル仕様は外部一次資料由来で、講座が推奨モデルを指定したわけではない。
