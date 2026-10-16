# Ubuntu + NVIDIA GPU 実行の5ステップ（v2.2／現環境では未実走）

**前提:** Ubuntu 24.04、ROS 2 Jazzy、Gazebo Harmonic。プロジェクト外のユーザー環境を自動で変更しない。まず依存関係確認、APIキーをGitHubに絶対書かない。GPUはGazeboのカメラ表示に利用できるが、Jev＋Qwen3.8はクラウドAPIでありGPUは必須ではない。

### 1. 環境を点検

```
cd rescuemind_v22
bash scripts/check_ubuntu_ros.sh
bash scripts/setup_ubuntu_jazzy.sh
bash scripts/v22_verify.sh
```

### 2. AIなしでモータ・カメラを確認

```
python3 scripts/v22_orchestrate.py --plan --scenario motion-check --scene nominal
python3 scripts/v22_orchestrate.py --run --scenario motion-check --scene nominal --capture-rosbag
```

失敗時は `outputs/runs/<run_id>/gazebo.log`, `bridge.log`, `velocity_guard.log`, `mission.log`, `readiness_last.txt` を確認。`gz topic -l` と `ros2 topic list -t` の対応を確認。ROSグラフとGazebo画面に個人情報や秘密鍵がないことも点検。

### 3. Jev / Qwenの実APIを接続

シェルの環境変数などに `TYPESAFE_API_KEY`, `DASHSCOPE_API_KEY`, `DASHSCOPE_BASE_URL` を設定。値をログ・動画・リポジトリに書かない。**本ZIPではAPIの到達性・認証・精度は検証できていない。**

### 4. 対照実験を撮影

```
python3 scripts/v22_orchestrate.py --run --scenario live --scene nominal --capture-rosbag --instruction '避難所Bに飲料水を届けて'
python3 scripts/v22_orchestrate.py --run --scenario live --scene swapped --capture-rosbag --instruction '避難所Bに飲料水を届けて'
python3 scripts/v22_orchestrate.py --run --scenario live --scene empty --capture-rosbag --instruction '避難所Bに飲料水を届けて'
```

**毎回世界を新規起動すること。** カメラの実画像を目視して、ボトル／救急箱が視野に入っているか確認。模擬AI回答ではなく実APIレスポンス・所要時間・ROS bag・動画を保存する。誤物資・欠品でモデルが「拒否」した場合、CLIが非ゼロ終了するのは現在の想定どおり。ただしネットワーク異常による停止を成功扱いしてはいけない。

### 5. 独立監査・発表準備

```
python3 scripts/v22_audit_trials.py outputs/runs/<nominal_id> outputs/runs/<swapped_id> outputs/runs/<empty_id> --csv outputs/v22_real_trial_audit.csv
```

出力CSVでモデルの誤許可と不必要な拒否、測定遅延を分析し、実際のGazebo映像（60–180秒）を撮影。OmniCampus公開GitHub・PDF・YouTube URLを提出。提出前に原文の動画設定と個人情報禁止要件を確認する。緊急時はオフラインテスト追加ではなく、**最短で実Gazeboロボット映像を完成する**。
