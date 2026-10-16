# Ubuntu24.04 + ROS2 Jazzy + Gazebo Harmonic 実行（v1.2）

## 事前条件

Ubuntu 24.04、画面表示可能なデスクトップ、ROS 2 Jazzy、Gazebo Harmonic、`ros-jazzy-ros-gz-bridge`、Python3と本プロジェクトの依存パッケージ。GPUがNVIDIAであっても、このPythonコードのJeVはクラウドAPI、Qwen3.8もクラウドAPI。NVIDIA GPUの存在だけではAPIは動作しない。

```bash
cd rescuemind_v12
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
bash scripts/v12_verify.sh
bash scripts/check_ubuntu_ros.sh
```

## 5つの別ターミナル

端末A — シミュレータ（実際のROS環境で要検証）
```bash
gz sim -r -v 4 worlds/rescuemind_test_arena.sdf
```

端末B — ROS/Gazeboブリッジ
```bash
bash scripts/bridge_direct_gazebo.sh
```

端末C — **独立速度ガード（今回追加、必須）**
```bash
bash scripts/start_velocity_guard.sh
```

端末D — ガードおよびセンサー準備診断
```bash
bash scripts/v12_live_readiness.sh
ros2 topic echo /rescuemind/guard_ready --once
ros2 topic info /cmd_vel -v
```

端末E — 非AI走行を先に確認
```bash
source /opt/ros/jazzy/setup.bash
python3 ros/gazebo_waypoint_mission.py --motion-check
```

続いてJevとQwen3.8のAPIキー、workspace base URLを正しく設定し、現地二段階判断を実行する。値は**コードや公開ログに記載しない**。

```bash
export TYPESAFE_API_KEY='...'
export DASHSCOPE_API_KEY='...'
export DASHSCOPE_BASE_URL='https://YOUR_AUTHORIZED_WORKSPACE_ENDPOINT/v1'
python3 ros/gazebo_waypoint_mission.py --run-live --instruction '避難所Bに飲料水を届けて'
```

※ `DASHSCOPE_BASE_URL` は**ご利用リージョンの公式ワークスペースエンドポイント**を指定。上記はプレースホルダ。`--run-live` でも外部APIに接続できなければ継続できない。推論待機中はゼロ速度指令を保持する。

## 重要事項

- ガードは`/rescuemind/cmd_vel_request`を受け、`/cmd_vel`だけをGazeboに中継。`/cmd_vel`のpublisherはガード1つだけでなければ中止する。
- すでに実行したROSノードやGazeboが残っていると、安全ガードを迂回するpublisherが生じ得る。`ros2 topic info /cmd_vel -v`を確認。
- camera、scan、odomが未到着・更新停止ならガードは速度0。異常時はラッチされるため、すべての走行プログラムを停止した上で原因を取り除いてから再起動する。
- ガード自体が強制終了したときにGazeboが自動停止する保証はない。**別途Gazeboをpauseし、車輪が停止したことを画面で確認すること**。実機には使用しない。
- `--legacy-direct-motion-check`は制御ループ開発用の危険な直通診断。`--run-live`では使用不能。提出デモでは使わない。
- 現地カメラの撮影方向が想定と合っていないと、モデルが正しい物資を認識できない。カメラ画像を実際に保存し、手作業で確認してから実API推論を実行する。
- 実行ログの`success=True`のみで、物資が運ばれたとは表現しない。本タスクは『物資拠点確認と避難所への接近』。
- `--run-live`の制御はNav2ではなく独自直接駆動。障害物を自動迂回するとは主張しない。
