# v2.2 一次情報調査（取得確認日 2026-10-16）

## 講座の要求（ユーザー資料）
- `Physical-AI応用1講座-最終課題.txt`（課題概要、合格要件、評価基準、提出方法、注意事項）

## 公開一次資料（ウェブ上で再確認したもの）
- **TypeSafe AI / Jev 1.14**: https://typesafe.ai/blog/jev-1-14 — 画像と`box`の機能追加。画像とboxは実験的機能として案内。単一Boxは存在の確証ではない。API契約は実環境で要確認。
- **Jev API reference**: https://docs.typesafe.ai/go/box と https://docs.typesafe.ai/go/images — 公開参照先。実APIの成功は未検証。
- **Alibaba Cloud qwen3.8-omni-flash**: https://help.aliyun.com/en/model-studio/qwen3-8-omni-flash — 2026-10-10更新。テキスト・画像・動画・音声入力／テキスト出力、地域別APIキー、Chat Completions/Responses。
- **Omni Chat Completions**: https://help.aliyun.com/zh/model-studio/qwen-omni — 画像URL入力と `modalities:["text"]`, `stream:true` の実例。モデル仕様が変わる場合は一次資料を再確認。
- **Gazebo Harmonic ROS 2 integration**: https://gazebosim.org/docs/harmonic/ros2_integration/ — `ros_gz_bridge` のYAMLトピックマッピングと方向 `GZ_TO_ROS` / `ROS_TO_GZ`。
- **Gazebo ROS 2 bridge README**: https://github.com/gazebosim/ros_gz/blob/ros2/ros_gz_bridge/README.md — simulation `/clock` の単方向ブリッジ。
- **Gazebo demos**: https://github.com/gazebosim/ros_gz/blob/ros2/ros_gz_sim_demos/README.md — DiffDriveのトピック/QoS例。

## 知見と未確認事項の区別

- これらの公式情報から、Jev画像判定とQwen3.8の画像理解、ROS/Gazebo通信を組み合わせる構成自体は検討可能といえる。
- **ただし**このZIPでの`scene_variants.py`のXML検査は、GazeboがSDFを正しく描画するという実行保証ではない。
- JevとQwenが水ボトルや救急箱を見分けるか、誤認識が相関するか、ネットワーク遅延が何秒かは測定していない。
- 過去のシミュレーションテスト件数は物理安全性・認識精度の実証ではない。実験の対象・母数・用いた機械的／人工的条件を明記する。
