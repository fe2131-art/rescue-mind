# v2.5 一次資料・確認範囲（2026-10-16確認）

## 課題原文から明示される条件
`assignment/Physical-AI応用1講座-最終課題.txt`: AIの使用（推論だけで可）、1〜3分のロボット動画、コード、説明PDF。加点は創造性・技術力・実用性・表現力。OmniCampusとYouTube URLが提出先、公開GitHub、個人情報禁止、締切2026-11-02 10:00。

## 実装に使う公開仕様（一次）
1. Gazebo Harmonic と ROS 2 の連携: https://gazebosim.org/docs/harmonic/ros2_integration/  — `ros_gz_bridge` YAML mapping、センサーをGazeboからROSへ、速度指令をROSからGazeboへ橋渡しする基本方法。
2. ros_gz_bridge公式GitHub: https://github.com/gazebosim/ros_gz/blob/ros2/ros_gz_bridge/README.md — 方向指定、ROS/Gazebo型、QoS。
3. ROS/Gazebo互換性: https://github.com/gazebosim/ros_gz — Jazzy/Harmonicがバイナリ対応。
4. Alibaba Cloud Qwen-Omni: https://www.alibabacloud.com/help/en/model-studio/qwen-omni — ストリーミング、画像入力、`modalities=["text"]`のAPI例、リージョン依存エンドポイント。Qwen3.8-Omni-Flashのモデル可用性は当日のコンソールで確認すること。
5. Jev 1.14情報: https://www.jevtypesafeai.com/jev-1-14 — Jev 1.14で画像/box、プレビュー扱いとの説明。**ドメインの公式運営主体や実API互換は本実行環境では独立に確認できない**ため、実環境でTypeSafeの正規ドキュメント・サービスを確認すること。前版が公式とみなした記事 `https://typesafe.ai/blog/jev-1-14` は今回ページ本文を取得できませんでした。

## v2.5で判明した実装上の問題（推論と直接観測を区別）
* **コード監査:** waypoint到着時のyawは拘束されておらず、現地画像が棚の方向を向く保証がない。
* **静的FOVモデル:** 水ボトル中心の仰角が従来の水平カメラで約0.36 rad。画角上端に余裕が少ない。
* **修正:** センサーピッチを -0.12 radにし、ROS制御で物資拠点中心へ回転したあと新しい画像を要求。カメラFOV内の物体中心をnominal/swappedで静的計算。
* **未検証:** 物理レンダリング、Occlusion、照度、VLMの本物の認識性能はこの幾何式からは証明できない。
