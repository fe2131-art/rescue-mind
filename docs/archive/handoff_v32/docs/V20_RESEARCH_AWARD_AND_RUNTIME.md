# v2.0 調査・評価戦略・実装根拠（2026-10-16）

## 1. 課題文の基準（ユーザー提供資料・10/8版）

評価は創造性、技術力、実用性、表現力。合格にはロボットがタスクを実行する動画と提出物が必要。提出物は60–180秒の実際のロボット動画、コード一式、説明PDF。11/2 10:00 JST締切。GitHub公開、YouTube公開/限定公開、個人情報を含めないこと。講義サンプル丸写しを避ける。

## 2. 公開一次資料の確認（Webで確認した情報）

- Gazebo Harmonic ROS 2 bridge: <https://gazebosim.org/docs/harmonic/ros2_integration/>。明示的なGZ_TO_ROS／ROS_TO_GZ方向、別名のROS/GazeboトピックをYAMLで関連付ける方式が公式サポート。
- ros_gz_bridge `/clock`: <https://github.com/gazebosim/ros_gz/blob/ros2/ros_gz_bridge/README.md>。Gazeboのclockが `/world/<worldname>/clock` へ掲載される場合に注意し、唯一の時計として**GZ->ROS**でブリッジする。
- ROS bag simulation time: <https://github.com/ros2/rosbag2/blob/rolling/README.md>。`--use-sim-time`使用時、最初の`/clock`が来るまで記録は開始しない。過去のv1.9は明示的な `/clock` bridge・bag sim-time化がないため再現性の懸念。
- TypeSafe Jev 1.14: <https://typesafe.ai/blog/jev-1-14>。2026年10月公開の公式説明。画像・Boxは実験段階であり、実APIと実画像での適合性検証は未実施。**Jevは必須**。Boxは対象の存在証明としては単独で使わない。
- Alibaba Cloud Qwen3.8-Omni-Flash: <https://www.alibabacloud.com/help/en/model-studio/qwen3-8-omni-flash>。公式モデルページ（2026-09更新）で画像入力／テキスト出力、複数リージョンと対応するAPIキーが確認できる。<https://www.alibabacloud.com/help/en/model-studio/qwen-omni> に画像入力例。

上記は**仕様確認**であり、実際のAPI接続やGazebo統合試験を成功したという意味ではない。

## 3. v1.9を監査して特定した問題→v2.0改善

| 検証対象 | 旧状態のリスク | 新しい改善 | 確認可能な範囲 |
|---|---|---|---|
| ROS `/clock` | Gazebo時計がブリッジされず、ROS/ホスト時刻を混同する恐れ | SDF world名に一致したGazebo `/world/rescuemind_arena/clock` をROS `/clock`へ一方向マッピング | YAML/SDF静的監査 PASS／実ROS未検証 |
| カメラ/scan/odomのstamp | 単一センサごとの進行は監視しても同じシミュレーション時間領域か不明 | clock進行と3センサtimestamp近接を照合 | 合成データ単体試験／実ROS未検証 |
| rosbag2の証拠 | ROS bagがホスト時刻で記録され、再生／センサtimestamp解釈が曖昧 | `--use-sim-time`, `/clock`収録、metadataでclock存在を要求 | command計画・モックmetadata検証／bag実収録未検証 |
| 起動判定 | `v15`のセンサ品質チェックだけでclock統一を検証しない | `v20_live_readiness.sh`でclock probeを追加 | シェル静的検査、実行計画検証 |

**時計の切り分け**：LiDAR/カメラ/オドメトリの観測時刻はROS simulation clock。故障検出の経過時間にはPython `time.monotonic()`、API許可と別プロセス軌跡の照合にはホストUnix時刻を用いる。異なる時間領域の数値をそのまま減算しない。

## 4. 優秀賞に向けた最優先の実験

1. **創造性**：同じROSカメラ観測でも物資適合/不適合で次の行動が変わる、実Gazebo録画を成功系・拒否系で撮影する。
2. **技術力**：Jev必須＋Qwen3.8判定、モータ制御、独立速度ガード、ROS時計、rosbag収録と因果ログの整合性を示す。
3. **実用性**：実カメラ画像に人手で正解ラベルを付け、Jevのみ・Qwenのみ・合意方式の偽許可率・偽拒否率・判定保留率・レイテンシをペア条件で計算（評価セットは未取得）。
4. **表現力**：1–3分MP4には実際のGazebo画面、指示、現地カメラ、AI出力、次動作、比較結果を配置。シミュレータ映像と合成グラフを明確に区別。

**注意**：速度ガード・保守的拒否が実ロボットの認証済み安全性を保証するわけではない。独自Gazeboモデルは物資を把持も積載もしない。目的は「現地の物資をAIで確認して避難所Bへ接近する／停止する」。Nav2の実経路計画もこの直接駆動レーンでは実証していない。

## 5. スケジュール上のゲート

- 10月20日：`motion-check --capture-rosbag`を**実Gazebo**で実行してclock・カメラ・LiDAR・オドム・車輪が接続できるか検証。
- 10月23日：Jev/Qwen実API通信と物資画像の認識を1ケースずつ実測（記録保管時には秘密情報を消去）。
- 10月26日：正常と誤物資の二条件を繰り返し試行、偽許可と停止を比較。
- 10月29日：1–3分の実ロボット動画、実測テーブル、図を確定。
- 11月1日：PDF、公開GitHub、YouTube、omnicampusのリンク・公開状態・個人情報を最終確認（11月2日10:00までに提出）。

**もし10月23日までに独自Gazeboの車輪試験が通らない場合**：公式Nav2/TurtleBot3デモへ戻すか、既存ロボットモデルの稼働実績ある構成に置換する。動画要件を失うより難しい技術を減らす方を優先する。Jev必須は維持。

## 6. 検証ログの読み方

`verification/v20/V20_VERIFICATION.json` に結果がある。記載されたPython件数・人工故障の件数は**ソフトウェア検証**であり、Gazebo実走行やJeV/Qwenモデルの実画像精度ではない。 `real_ros_gazebo` `real_jev` `real_qwen38` の3項目が未検証なら、提出PDFの実測欄に数字を埋めてはならない。
