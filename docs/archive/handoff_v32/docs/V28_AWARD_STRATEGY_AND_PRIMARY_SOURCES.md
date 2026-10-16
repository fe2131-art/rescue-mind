# RescueMind v2.8：一次資料・受賞戦略・実証計画

更新日：2026-10-16（JST）／対象：Physical AI応用1講座 最終課題（10/8版）

## A. 課題文から直接確認した条件

課題名は「AI×ロボティクスによる創造的タスクの実現」。AIを何らかの形で使用することは**必須**。ROS / Gazebo / Genesis等を想定するが実機・他ツールも可。評価加点は**創造性・技術力・実用性・表現力**。必要物は**1〜3分のロボット実行動画、全ソースコード、短いレポート**。2026-11-02（月）午前10時までに、OmniCampusへレポートPDFとpublic GitHub URL、およびYouTube動画URLを提出。YouTubeは最低「限定公開」、公開が望ましい。動画はMP4、倍速の場合は明記。氏名・所属・メールアドレス・API秘密情報を含めない。

## B. 作品の正確な範囲

RescueMindは自然言語で指定された物資拠点へ**差動二輪ロボットが移動**し、棚へ向き直り、物理的静止を確認し、ROS Imageの二枚を品質・時刻検査してから、**TypeSafe Jev 1.14.0 必須＋Qwen3.8-Omni-Flash**の合意で避難所Bへの次区間を許可するプロトタイプ。誤物資・欠品・曖昧な画像・センサー障害は停止する。**物資を把持・輸送しない。Nav2動的経路計画の実証ではない。** 認識した棚が安全でも避難経路全体の安全性を保証できない。

## C. v2.8で発見・修正した欠陥

従来の二枚画像ゲートは `frame_stamp_ns` の単調増加をチェックするが、ブリッジやキューで遅延した**古いフレームが連続して到着**した場合、どちらのフレームも現在のシミュレーション時刻から離れていることを検出できない。結果として古い画像で二重AI判断する危険がある。

v2.8：`rosgraph_msgs/msg/Clock` を `/clock` で受け、画像がGazebo時刻から最大1.2秒遅れ、最大0.25秒未来までという暫定許容範囲に入る場合だけ取得。最後の**時計前進から0.9秒**以上経過すると中断する（同じ時計値の重複受信を前進に数えない）。時計逆行・時刻領域の混合を拒否。受理時の画像ROSスタンプ・時計スタンプ・差分を記録し、独立した監査コードで再検査。数字は**未校正の工学的初期値**でありROS/Gazebo実機成功・安全認証を意味しない。

## D. 受賞を狙う見せ方と定量評価

| 評価軸 | デモで見せるもの | 検証・数値 |
|---|---|---|
| 創造性 | 同一指示で正規・入れ替え・欠品に応じてロボットの行動が変わる | 3シーン×2物資の比較 |
| 技術力 | 棚への向き合わせ→静止→二枚撮影→Gazebo時計照合→Jev+Qwen→独立安全ガード | ROS bag / 独立オドメトリ、異常時系列を拒否 |
| 実用性 | 通信断・時計遅延・誤物資では意図した停止 | 偽許可率、偽拒否率、推論時間、停止の実軌跡 |
| 表現力 | 1〜3分動画にロボット・カメラ・AI判断・停止結果を同時表示 | 実画像、実ROSログ、試行IDを重ねて説明 |

統制実験：`experiments/v23_locked_protocol.json` の**30試行計画**（3シーン×水/医療物資×5反復）はあくまで計画。反復が多くてもシーン独立性は6条件のみ。実画像で全試行を取得し、合否と推論時間をまとめる。モデル推論失敗は画像認識による正常拒否として加点しない。事故防止のため最低でも nominal 1件、swapped 1件の実ROS／実Gazebo収録を締切前に最優先。

## E. 1分〜3分の実動画構成案（未撮影）

- 0〜15秒：困難な現場で、人がすべてを確認せずにロボットに指示する課題と作品の目的。
- 15〜50秒：Gazebo画面でnominal：移動、棚へ向き合わせ、静止・取得時刻ゲート、二重AI許可、避難所へ接近。
- 50〜80秒：swapped/empty：**実APIによる**拒否が出てロボット停止。システム故障は別ラベルで説明。
- 80〜105秒：独立ROS観測の軌跡・タイムスタンプ・安全ガード、実測比較。最後に制約（物資把持なし）を明記。

上記は撮影指示であって、動画の作成や推論実験の成功を示さない。

## F. 公開一次資料との照合（2026-10-16アクセス）

1. Gazebo Harmonic ROS 2 integration: https://gazebosim.org/docs/harmonic/ros2_integration/ — ROS-Gazeboの対応メッセージ・YAMLブリッジ設定と方向 `GZ_TO_ROS`。 `/clock` の橋渡しは既存の `configs/ros_gz_bridge_v20.yaml` を使用。
2. Gazebo Harmonic DiffDrive migration: https://gazebosim.org/docs/harmonic/migrating_gazebo_classic_ros2_packages/ — Gazebo HarmonicのDiffDrive SDFプラグイン、トピック、加速度制限に関する参考。実Gazebo互換性は別途検証が必要。
3. ROS 2 rclpy QoS definitions: https://github.com/ros2/rclpy/blob/rolling/rclpy/rclpy/qos.py — センサーデータQoSのBest Effort特性を確認。これはJazzy版のライブラリ動作をこの環境で検証したわけではない。
4. TypeSafe AI primary blog: https://typesafe.ai/blog/jev-1-14 — Jev画像とBoxの実験的な機能、`TypeSafe-Danger-Zone-Images: true`。必須Jev 1.14.0 APIの実接続は未検証。
5. Alibaba Cloud Model Studio Qwen-Omni: https://www.alibabacloud.com/help/en/model-studio/qwen-omni — Qwen3.8-Omni-Flashの画像入力／テキスト出力。APIキーと実エンドポイントは未検証。

**区別すべきこと**：課題の提出条件はローカル課題原文由来。外部API/ROS/Gazebo仕様はリンク先の公開一次資料由来。閾値、独立証拠設計、比較方法は本作品の設計・推論。API推論や物理走行の測定値を創作していない。

## G. 現環境で検証できなかった条件

`ros2`、`gz`、NVIDIA GPUと実API認証情報がない。よって Gazebo描画・物理軌跡・Jev/Qwen実推論・ROS bag実収録・動画は**未検証・未完成**。v2.8の439テストと14故障条件はモック／人工条件／静的検査のみ。最優先タスクはユーザーのUbuntu 24.04 / ROS2 Jazzy / Gazebo Harmonicでの実走行・実APIテスト。
