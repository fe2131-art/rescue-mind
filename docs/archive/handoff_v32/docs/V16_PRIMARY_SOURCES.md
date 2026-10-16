# 一次資料調査・情報源（2026-10-16）

**課題原文**: `assignment/Physical-AI応用1講座-最終課題.txt`。下記は別途公開Webで確認した技術仕様（課題原文そのものの記載ではありません）。

| 技術 | 公式ソース | 確認した仕様と制限 |
|---|---|---|
| ROS 2 Jazzy | https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html | Ubuntu 24.04 debが対象。ROS環境をsourceしてからPython/rclpyを確認 |
| Gazebo Harmonic | https://gazebosim.org/docs/harmonic/ros2_integration/ | ros_gz_bridge、`[`はGZ→ROS、`]`はROS→GZ。Bridgeがあるだけではセンサー内容は保証されない |
| ros_gz_bridge | https://github.com/gazebosim/ros_gz/blob/ros2/ros_gz_bridge/README.md | Twist, Odometry, Image, LaserScanの変換とトピック対応 |
| DiffDrive | https://github.com/gazebosim/gz-sim/blob/main/examples/worlds/diff_drive.sdf | wheel joint/半径/間隔/topicのSDF設定例。独自SDFは実Gazeboで未検証 |
| Jev 1.14 | https://www.jevtypesafeai.com/jev-1-14 ; https://www.jevtypesafeai.com/clerk_1790100707857/docs | 画像/Boxは実験的。Boxは不在でも返るので存在判定と組合せる。API未実行 |
| Qwen3.8-Omni-Flash | https://www.alibabacloud.com/help/en/model-studio/qwen-omni | 画像入力/テキスト出力。region/workspaceのBase URLを使用。API未実行 |

## 課題原文に明記された要件

- AI活用必須。ロボットがタスクを実行する動画を**60〜180秒**で撮影。
- コードをGitHub publicリポジトリに置き、PDFレポートの提出とYouTube URLの提出が必要。
- タイトル`PAI最終課題_omnicampusアカウント名`、レポート名`説明資料_PAI最終課題_omnicampusアカウント名.pdf`。
- YouTubeは限定公開以上、全体公開は加点推奨。個人情報・秘密情報を含めない。
- 締切2026-11-02（月）10:00。

**未検証**：ROS/Gazebo車輪走行、Jev/Qwenの真の画像認識精度、APIレイテンシ、録画した最終提出動画。
