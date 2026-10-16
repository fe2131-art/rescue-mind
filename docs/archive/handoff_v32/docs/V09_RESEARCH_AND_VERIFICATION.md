# v0.9: 一次資料調査・検証範囲（2026-10-16）

## 1. 資料の区分

- **課題原文**：`assignment/Physical-AI応用1講座-最終課題.txt`（10/8版）。最終採点項目＝創造性・技術力・実用性・表現力。必須提出＝OmniCampusのPDFとpublic GitHub URL、YouTubeのロボット動作MP4（1〜3分）URL。締切は2026-11-02 10:00 JST。動画タイトル・氏名などの個人情報禁止条件は原文を参照。
- **一次資料**：下表の公式仕様・操作例。2026-10-16確認時点の公開ウェブ文書であり、実API動作試験ではない。
- **実行した証拠**：`outputs/release/v09_*.json`、`v09_unittest.log`等。モック/理想化の結果を実VLM/実Gazebo成績に流用しない。

## 2. 公式一次資料

| 技術 | 公式URL | 支持される仕様 | 未確認の事項 |
|---|---|---|---|
| Jev 1.14.0 | https://www.jevtypesafeai.com/jev-1-14 | `model=jev-1.14.0`に固定。`assets`画像・`box`を使用、画像は実験的機能。 | 現地Gazebo画像での精度、API応答時間 |
| Jev box/Noul | https://www.jevtypesafeai.com/clerk_1790100707857/docs | boxは対象不在でも矩形を返すため別の存在確認が必要 | 場面別の較正誤差 |
| Jev発表 | https://typesafe.ai/blog/jev-1-14 | `TypeSafe-Danger-Zone-Images: true`、preview視覚入力 | ハードウェア安全性 |
| Qwen3.8 | https://www.alibabacloud.com/help/ja/model-studio/qwen3-8-omni-flash | 画像＋テキスト入力、テキスト出力。リージョン対応。2026-09-30更新 | 実契約、請求、精度 |
| Qwen-Omni | https://www.alibabacloud.com/help/en/model-studio/qwen-omni | OpenAI互換API、地域に対応するワークスペース URL、ストリーミング応答 | 画像入力での厳密なエラーハンドリング |
| Gazebo+ROS 2 | https://gazebosim.org/docs/harmonic/ros2_integration/ | `ros_gz_bridge` の `[`, `]` 方向、ROS/Gazeboメッセージ対応 | 独自SDFの物理駆動 |
| Gazeboサンプル | https://github.com/gazebosim/ros_gz/blob/ros2/ros_gz_sim_demos/README.md | DiffDrive、RGBカメラ、ROSインターフェースの例 | 独自ロボットの慣性・摩擦 |
| Nav2 Jazzy | https://docs.nav2.org/jazzy/getting_started/ | 公式TurtleBot3のGazeboナビゲーションクイックスタート | 本ZIPの独自SDFでのNav2対応 |
| Nav2 Gazebo設定 | https://docs.nav2.org/jazzy/configuration_and_development/first_time_robot_setup_guide/gazebo/ | TF、オドメトリ、センサー、地図、プランナ等の統合手順 | 本ZIPはカスタムNav2統合未完成 |

## 3. 前バージョンからの監査で判明した重要点

1. v0.8の`decide_checkpoint`は物資分類の一致とJev存在信頼度のみで次区間を許可し、画像中で危険が明示されてもそれを許可条件に反映していなかった。v0.9はJev hazard noulまたはJev/Qwen `scene=hazard`で拒否。欠損・NaN・不正な安全観測も拒否。
2. 差動二輪コントローラに**前進コマンド中の移動停滞**の監視がなかった。純Python `ProgressWatch` を追加しROS直接駆動に接続。自己位置の変化がないと停止要求。これは動的経路再計画ではない。
3. `--run-live`でカメラが出発前に未接続でも、物資拠点へ移動できた。v0.9は起動時カメラ画像の存在をチェック。ただし、ROSカメラのフレーム内容・画角・生成時刻は実Gazeboで確認要。
4. 旧ログ監査は、JevのモデルIDと自己申告された許可フラグだけでも「通過」できた。v0.9で両モデルの識別子・報告フラグと**再計算した判定結果**、イベント時刻順序を検査。ただしログの改ざん防止や映像による独立検証は提供しない。
5. 本作品のタスクは**物資拠点の識別と避難所接近**。物理的な積載・ピックアップ・配送物の移動、動的グローバル再計画は実装されていない。

## 4. 今回の検証の境界

**実際に実行**：Pythonの単体・結合モック検査、A*簡易経路、差動二輪の理想運動学、SDF XML/トピック形式の静的検査、人工JSON 972条件の許可拒否判定、PDFの描画確認、ZIP CRC・SHA-256・展開後再テスト。

**実行していない**：実ROS 2 / Gazebo Harmonic起動、リアルタイム物理走行、実Jev 1.14.0 HTTPS呼出し、Qwen3.8実API、実環境のカメラ映像、NVIDIA GPU実行、ロボット実行動画の撮影、OmniCampus/YouTube/GitHub公開操作。

**判断の限界**：画像上の危険疑いをもとに停止するだけで、LiDARの障害物座標とVLM検出箱を融合していない。画像に危険が見えないことは安全性の証明ではない。Jevのスコア閾値は未較正。NVIDIA GPUがあってもQwen3.8はクラウドAPIなので料金・ネットワークが必要。
