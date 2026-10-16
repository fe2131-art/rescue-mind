# v1.4 一次資料調査・根拠・未検証範囲（2026-10-16）

## 課題原文（確定情報）

`assignment/Physical-AI応用1講座-最終課題.txt`。加点項目は「創造性」「技術力」「実用性」「表現力」。動画1〜3分、コード一式、PDF説明資料を提出する。GitHubリポジトリはpublic、YouTubeは最低限定公開。締切は2026-11-02 10:00 JST。個人情報の記載・映り込み禁止。運搬そのものは必須ではなく、受講者自身がタスクを設定する。

## 公式・一次資料から確認できた事項

| 対象 | 公開資料URL | 支持される事項 | この環境で未検証の事項 |
|---|---|---|---|
| Gazebo Harmonic | https://gazebosim.org/docs/harmonic/moving_robot/ | DiffDriveのjoint、wheel_separation、wheel_radius、topic、odometryトピックの設定例 | 本SDFがユーザーUbuntu/GPUで物理駆動するか |
| Gazebo ⇔ ROS 2 | https://gazebosim.org/docs/harmonic/ros2_integration/ | `ros_gz_bridge` はメッセージ型対応の範囲内で通信をブリッジする | カメラ画像・LiDARの実パブリッシュ、QoS |
| ros_gz_bridge公式リポジトリ | https://github.com/gazebosim/ros_gz/blob/ros2/ros_gz_bridge/README.md | Twist、Odometry、Image、LaserScanの対応と一方向のブリッジ設定例 | ROS Jazzy実環境での接続検証 |
| Qwen3.8-Omni-Flash | https://www.alibabacloud.com/help/en/model-studio/qwen3-8-omni-flash | 入力に画像とテキスト、出力にテキストをサポート（2026-09-28更新） | 実APIでのJSON返信形式、推論遅延、推論精度 |
| Qwen-Omni | https://www.alibabacloud.com/help/en/model-studio/qwen-omni | Model Studio Chat Completions使用、地域依存の`DASHSCOPE_BASE_URL`（2026-10-15更新） | 現在の認証情報とワークスペースの実疎通 |

## Jevのエビデンスの取り扱い

- Jevは**ユーザー指定の必須要件**。コードは`jev-1.14.0`を明示的に固定し、`TYPESAFE_API_KEY`がなければ実行を拒否する。
- TypeSafe提供とされる仕様への原資料のリンク: https://docs.typesafe.ai/images および https://docs.typesafe.ai/primitives/box 。今回のウェブ閲覧では両URLの本文取得に失敗したため、**一次資料を直接確認できたとは主張しない**。
- 次の情報は独立した転載・ゲートウェイ・コミュニティ資料を通して確認できた：`jev-1.14.0`における画像`assets`、実験的`box`、`TypeSafe-Danger-Zone-Images`ヘッダー、Box単体で対象存在が保証されない仕様。
  - https://www.jevtypesafeai.com/jev-1-14
  - https://www.jevtypesafeai.com/multimodal-jev
  - https://jevwiki.ai/wiki/concepts/box.md
- 実APIでの稼働・レスポンス契約は未検証。サードパーティー・ゲートウェイにAPIキーを安易に渡さず、ソースに含む直接APIのエンドポイントをTypeSafe公式の利用者向け資料で照合してから実行すること。

## 選定と研究仮説（資料から自動的には導けない）

- 二つのモデルが一致するときだけ進むことで、誤許可率が低下する**可能性**はある。しかし共通データによる相関エラーがあり、実測しない限り改善は主張できない。
- 人工反例12件は**プログラムの安全ポリシー**比較であり、視覚モデルの実性能を証明しない。
- 独立速度ガードは単純なROSノードであり、Gazeboがガードごと停止した時に直前の速度を保持しないと保証できるものではない。物理安全認証は存在しない。
- 物理的な把持・運搬はない。現在の実装は独自Gazeboの**直接駆動**であり、Nav2の経路再計画成功を主張しない。
