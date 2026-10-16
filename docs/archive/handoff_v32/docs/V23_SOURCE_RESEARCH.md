# 一次資料調査（2026年10月16日時点）

## 講座の要求：ユーザー提供原文

- `assignment/`に課題10/8版の原文コピーを含む。確認すべき項目は評価基準、提出形式、公開設定、個人情報取り扱い、締切。これらは一次資料であり、外部記事で補完した条件ではない。

## 公開一次資料とコードへの影響

1. TypeSafe公式ブログ「Jev: For the builders AND dreamers」: https://typesafe.ai/blog/jev-1-14 — Jev 1.14.0の画像・Box、実験的な画像ヘッダー、モデル固定が重要。`box`を存在確認として使わず、`noul`で別判定する。
2. TypeSafe公式からリンクされているAPI文書: https://docs.typesafe.ai/go/images と https://docs.typesafe.ai/go/box — 今回は本文にアクセスできなかったため**一次文書本文の確認済みとはしない**。公式ブログで画像機能・Box・実験的ヘッダーの公開は確認。APIの具体的なリクエスト形式は実API試験前に再照合が必要。参考の https://www.jevtypesafeai.com/clerk_1790100707857/docs は公開ページだがTypeSafe公式ドメインではないため二次参照として扱う。
3. Alibaba Cloud Model Studio Qwen-Omni: https://www.alibabacloud.com/help/en/model-studio/qwen-omni — Qwen3.8-Omni-Flashの画像入力、トークンと出力条件。クラウドAPIの地域・APIキー設定が必要。**実リクエスト成功は未確認**。
4. Gazebo Harmonic sensors: https://gazebosim.org/docs/harmonic/sensors/ — 実際にGazeboを起動して描画・センサー確認が必要。SDFの静的妥当性と別。
5. ros_gz_bridgeリポジトリ: https://github.com/gazebosim/ros_gz/blob/ros2/ros_gz_bridge/README.md — Gazebo/ROS間のメッセージ型・トピック、clockブリッジ、cameraとROS座標フレーム上の注意。
6. Gazebo移行ガイド: https://gazebosim.org/docs/harmonic/migrating_gazebo_classic_ros2_packages/ — カメラについて`ros_gz_image`も選択肢。使用中の`ros_gz_bridge`と実環境の通信量を比較する。
7. rosbag2公式README: https://github.com/ros2/rosbag2/blob/rolling/README.md — `--use-sim-time`は初回clock受信以前には記録できない。`/clock`の欠落は記録を壊し得る。

## 研究上の警告

- 画像で認識できるかは**モデルカードでは保証されない**。Gazebo合成画像での実試験が不可欠。
- `real_model:true`はJSON内の自己申告であり、API呼び出しの真正性確認ではない。ログ・API課金記録・原画像の確認が別に必要。
- 同じ環境・ほぼ同じフレームを30回撮影しても真に独立なサンプルが30件増えたわけではない。信頼区間は記述的な目安に限定。
- 人工条件での回帰テストと現実の物体認識性能を比較しない。
