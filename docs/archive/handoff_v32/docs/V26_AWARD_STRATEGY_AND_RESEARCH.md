# v2.6 優秀賞獲得戦略・一次資料調査・妥当性境界

**更新日:** 2026-10-16。対象：Physical-AI応用1講座 最終課題（10/8版）。課題本文は公開仕様とは別の、ユーザー提供の課題資料から抽出。

## A. 課題原文から確定する評価と提出制約

- 加点項目：**創造性、技術力、実用性、表現力**。
- 合格ライン：ロボットがタスク実行する動画と提出物の提出。AIを何らかの形で使うことは必須。
- 提出物：**60〜180秒の実際のロボット実行MP4**（2倍速は明記可）、使用コード全部、レポート。
- OmniCampus：PDF（`説明資料_PAI最終課題_omnicampusアカウント名.pdf`）、**GitHub public** URL。YouTubeのMP4 URLも提出。動画タイトル`PAI最終課題_omnicampusアカウント名`、最低限定公開。
- 氏名・所属・メール等の個人情報をコード・PDF・映像に含めない。締切は **2026-11-02（月）午前10時 JST**。
- 講座サンプルの丸写しは禁じられる。独自の工夫と限界を明記する。

## B. 採点軸ごとの優先戦略

| 軸 | すでに実装した独自性 | Ubuntuでまだ示すべきもの |
|---|---|---|
| 創造性 | 物資の現地二重VLM判断で移動を条件分岐。撮影姿勢をロボットが能動調整。 | 同一経路でnominalだけ避難所到着、swapped/emptyは拒否して停止する実映像 |
| 技術力 | カメラ向き合わせ、**静止ゲート**、ROSカメラの時刻、Jev/Qwen、独立速度ガード、独立オドメトリ監査。 | 実Gazeboの位置・速度・カメラ記録とAI許可時刻を突き合わせたログ |
| 実用性 | API異常・センサー停止・誤物資では停止側に倒す。正常な拒否と故障を区別。 | 実画像の誤許可率／誤拒否率、センサー雑音の影響、運用上の制約 |
| 表現力 | 30試行事前登録、シーン差分、ログ、JPEG SHA-256、監査証跡、PDF原稿。 | 60〜180秒動画の成功／失敗対比＋定量評価＋限界の説明 |

### 動画案（90〜150秒、**完成動画ではない**）

1. 0–15秒：救援指示とシーン構成。
2. 15–55秒：nominal移動→棚へ向きを調整→速度・姿勢の静止を確認→新規ROS画像→Jev/Qwen一致→避難所へ。
3. 55–95秒：swapped/emptyの同経路で拒否→外部観測で静止。
4. 95–120秒：AI判断ログと走行軌跡の対照、実測した誤許可・誤拒否（データ未取得なら未取得と記載）。
5. 120–135秒：把持・輸送なし、実世界安全認証なし等の限界。

### 重要な優先順位

**第一優先はUbuntu上の実走行と実API推論。** 新たなオフライン試験の数だけで受賞の確度は上がらない。動画が完成しないまま試験だけ増やさない。まずnominal 1回を最後まで実行し、swapped 1回の正常拒否を撮る。その後30試行プロトコルに進む。

## C. 今回の根拠付き技術検討（課題原文ではなく外部の一次資料）

- ROS 2 `nav_msgs/msg/Odometry` 正式メッセージ定義：位置は `header.frame_id`、twistは `child_frame_id` 基準。速度指令ゼロ≠車体停止なので、**車体座標系の実測twistと位置・姿勢差**を組み合わせて確認する。参照： <https://github.com/ros2/common_interfaces/blob/rolling/nav_msgs/msg/Odometry.msg> とNav2の解説 <https://docs.nav2.org/jazzy/configuration_and_development/first_time_robot_setup_guide/odom/setup_odom_gz/>。
- Gazebo Harmonic ROS連携：`ros_gz_bridge`は対応する型にのみ使用可能。画像、LaserScan、Odometry、Twist、Clockの対応と方向をYAMLで固定。参照： <https://gazebosim.org/docs/harmonic/ros2_integration/> と <https://github.com/gazebosim/ros_gz/blob/ros2/ros_gz_bridge/README.md>。
- Gazebo DiffDrive：速度指令をGazebo TransportのTwistで受ける。モデルにおける運動と撮影の確証はGazebo実走行が必要。参照： <https://gazebosim.org/docs/harmonic/moving_robot/>。
- Jev 1.14.0の画像・Box等のAPI仕様は公式と公開ドキュメントで照合対象。Boxは不在時にも値が返る設計への注意があり、対象の存在確認と二重モデル一致を必須にする。参照： <https://docs.typesafe.ai/images> 、 <https://docs.typesafe.ai/primitives/box>。**この実行環境からの実API検証は未実施**。
- Qwen3.8-Omni-Flashの画像入力はAlibaba Cloud Model Studio説明で確認対象。参照： <https://www.alibabacloud.com/help/en/model-studio/qwen3-8-omni-flash>。**実モデル呼び出し未実施**。

## D. v2.6で変更した故障モード

- **以前:** 棚向きの角度が許容域へ入るとゼロ速度要求を送信し、一定待機後の新規カメラフレームでVLMへ進めた。車体がまだ慣性・外力で動いている場合を直接検査していなかった。
- **今回:** `StationaryGate` は連続4個以上の新規ROSオドメトリ、0.65秒以上、線速度 `<=0.025m/s`、角速度 `<=0.055rad/s`、並進ドリフト `<=0.020m`、方位ドリフト `<=0.040rad` を要求する。確認失敗時は画像取得もAI推論も開始しない。推論中の移動は`MotionUnstable`で中断。
- **根拠の範囲:** 速度閾値は設計選択であり、**安全規格の基準値でもGazebo実測に基づく校正値でもない**。静止の意味は「指定したノイズ閾値内のオドメトリ停止」であり、実ロボットの完全停止を証明しない。LiDARやカメラ映像の実観測が別途必要。
- **監査:** `camera_aim_aligned -> checkpoint_stationary_verified -> checkpoint_frame -> checkpoint_decision` の順序を実行監督プログラムが必須とする（正常続行および意図した拒否の両方）。独立ROSオドメトリ監査と組み合わせる。

## E. 今回実際に実行した検証 vs 未完了事項

| オフライン検証 | 実Gazebo/実API |
|---|---|
| Python回帰、模擬ROS閉ループ、車体移動の注入試験、人工12条件の停止ゲート、時系列証拠の改ざん拒否、SDF/XMLの静的検査、ZIP CRC/SHA-256 | ROS Jazzyブリッジ実通信、DiffDriveの摩擦・惰性、画角・遮蔽のレンダリング、Jev/Qwen実画像推論、30試行実測、提出MP4 |

**未測定を合格率として扱わないこと。** 人工テストの全件成功は、実APIの正解率・実Gazebo走行率・物理安全性を意味しない。Nav2再計画・実際の物資運搬も未実装。
