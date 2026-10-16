# RescueMind v3.1 — 課題基準、コード改善、一次資料調査、未検証事項

## 1. 課題原文から確定するもの

出典: `Physical-AI応用1講座-最終課題.txt`（10/8版）。**課題名**「AI×ロボティクスによる創造的タスクの実現」。AI使用必須（推論のみ可）、ロボット実行動画1〜3分、コード一式、簡単なレポート。加点は**創造性・技術力・実用性・表現力**。OmniCampusに提出するPDF、public GitHub URL、YouTube動画URL（限定公開以上）、提出締切**2026-11-02 10:00 JST**。氏名・所属・メールアドレス等の個人情報は含めない。

優秀賞は選定予定であり、獲得の保証はない。作品は災害時物資の**現地認識と避難所への接近**であり、物理把持・運搬、Nav2動的経路再計画は未実装。これらを誇大表示しない。

## 2. v3.1で発見した欠陥

`v3.0`の `scripts/check_guard_topology.sh` による**走行開始前**のROS発行者検査は存在したものの、**走行開始後**のGraph Publisherの変化を監視していなかった。ミッションが正常にガードされた`/rescuemind/cmd_vel_request`を使っても、別のROSノードが直接`/cmd_vel`をPublishすれば、速度ガードを迂回する。原因は開始時点の構成検査しかなく、独立監視プロセスがなかったこと。

### 修正

- `rescuemind/runtime_guard_graph.py`: ROS不要の純粋ロジックで、`/cmd_vel`は**ノード`rescuemind_velocity_guard`、namespace `/`、型 `geometry_msgs/msg/Twist`**、`/rescuemind/guard_ready`は**同ノード、型 `std_msgs/msg/Bool`**、ともに1 Publisherのみ許可。
- 初期DDSグラフ発見中は、**未知Publisherが1つでも存在すれば即座に失敗**し、期待Publisherが部分的に発見済みの場合だけ短い待機を許可。いったん監視を開始した後、0件・複数・型違い・時刻逆行はいずれもラッチして不許可。
- `ros/runtime_guard_graph_watch.py`: 約200msおきに`rclpy.Node.get_publishers_info_by_topic`を参照。異常時は`/rescuemind/estop`にBool(True)を連続Publishして非ゼロ終了。Supervisorが異常プロセス終了を検出しスタックを中断。
- `scripts/v22_orchestrate.py`: `guard_graph_watch`を全実行計画に追加。正常完走・意図したAI拒否の双方で`guard_graph_watch.jsonl`が存在し、1件だけのガード発行者を継続観測できた証拠を監査。欠落なら成功としない。
- 人工16条件、既存460件に対する追加自動試験、従来のカメラ・時計・独立ROS軌跡・bag終了検査の回帰試験を実行。

### 限界

これは**ROS DDSグラフのノード名/名前空間/型に対する診断**であり、publisherの本人確認・鍵ベースの認証ではない。故意に同じノード名を使う攻撃やGazebo Transportへの直接publishは抑止できない。ROSグラフの変化から検知まで最大約200msと通信遅延が生じ得る。`estop`も通信可能性に依存し、ハードウェアや安全認証を意味しない。実GazeboのPublisher発見やESTOPの確実な適用はこの環境では未検証。

## 3. 優秀賞への示し方

| 評価軸 | v3.1で示せる実装 | 実動画・実測でなお必要な証拠 |
|---|---|---|
| 創造性 | 同じ命令で、物資配置（nominal/swapped/empty）に応じてJev＋Qwenで行動を分岐 | 正常と拒否のGazebo画面比較 |
| 技術力 | 差動二輪の制御、視線合わせ、静止・二枚撮影・clock照合、二重AI、独立速度ガード、**追加の実行中Graph Watch** | 具体的なロボット走行・ROS bagトレース |
| 実用性 | 期待Publisher以外の混入時に停止を試み、独立ログを必須化 | 実ROSでの異常注入と停止距離/遅延評価 |
| 表現力 | 時間軸のAI判断と移動・停止の独立証拠、30試行の事前固定計画 | 実動画60〜180秒、実測の比較図と説明PDF |

映像では少なくとも**nominalでの許可移動**と**swappedでの認識拒否停止**を同じ画面構成で見せる。技術解説パートでは `/cmd_vel` に直接送信する誤ノードをグラフ監視が検知することを実ROS上で示せれば、単なるVLMデモとの差別化になる。ただし確認できた場合に限る。

## 4. 技術調査（課題原文由来ではない外部一次資料）

- **ROS 2 Jazzy Topic Endpoint API（発行者を取得できる）**: ROS基盤`rcl_get_publishers_info_by_topic`。 https://api.nav2.org/jazzy/html/graph_8h.html 。発行者のnode name、namespace、type、QoS等を取得可能。`rclpy`実装の利用方法は https://github.com/ros2/rclpy/blob/rolling/rclpy/rclpy/node.py の `get_publishers_info_by_topic`。後者はrollingブランチのため、**Jazzy実機でAPI互換性を確認する必要あり**。
- **Gazebo Harmonic DiffDrive**: https://gazebosim.org/docs/harmonic/moving_robot/ 。`<topic>`に速度コマンドのGazebo Topicを定義できる。監視は**ROS側 `/cmd_vel`のみ**でGazebo Transportを認証しない。
- **Gazebo Harmonic / ROS 2ブリッジ**: https://gazebosim.org/docs/harmonic/ros2_integration/ 。センサー・速度トピックの双方向連携を行う。
- **rosbag2**: https://github.com/ros2/rosbag2 。`--use-sim-time`の時計待ちとメタデータ確定を要実機確認。
- **Qwen3.8-Omni-Flash**: https://www.alibabacloud.com/help/en/model-studio/qwen3-8-omni-flash 。画像入力・テキスト出力に関する仕様を参照。
- **TypeSafe Jev 1.14.0**: https://docs.typesafe.ai/images と https://docs.typesafe.ai/primitives/box 。一次資料の所在は確認、当環境から直接API認証実行はしていない。Jevはこの作品の**必須コンポーネント**として残す。

外部技術仕様の確認と、作品が実際に動作したという証拠は区別する。現段階は**実ROS/Gazeboを起動できないため、全てのトピック観測はモック/人工データ**である。

## 5. 提出前に残る実証とリスク

1. Ubuntu 24.04 + ROS 2 Jazzy + Gazebo Harmonicにて`--scenario motion-check`実走行。
2. `guard_graph_watch.jsonl`が`sole_guard_confirmed`を継続記録し、未知publisherの出現を検知できるか実ROS上で試験（**必ず安全なシミュレータのみ**）。
3. Jev＋Qwenの実APIで現地撮影画像を評価し、nominal/swapped/empty各シーンの実停止を録画。
4. 事前固定した30試行の実測値（誤許可、誤拒否、推論レイテンシ、通信失敗）を作成。
5. 60〜180秒MP4、YouTube公開設定、public GitHub、説明PDF、個人情報除去を締切前に確認。

**未完了**: 実Gazebo/ROSグラフの監視、Jev/API、Qwen/API、実rosbag、30試行の実測、動画完成。人工故障テスト数は現実の安全率でもAI精度でもない。
