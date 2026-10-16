# Ubuntu 24.04 + NVIDIA GPU：v1.3 初回実行・診断手順

**最初にこの順番で**。Ubuntu 22.04ならJazzy apt手順をそのまま使わない。APIキーはGitHubへ保存しない。

```bash
cd rescuemind_v13
bash scripts/check_ubuntu_ros.sh
# ROS2 Jazzy、Gazebo Harmonic、ros_gz_bridge、Python3-venvの導入後
bash scripts/setup_ubuntu_jazzy.sh
bash scripts/v13_verify.sh
```

`setup_ubuntu_jazzy.sh`は`/usr/bin/python3` と `--system-site-packages` を使用し`rclpy` importを確認する。Ubuntu以外のLinuxでは同じapt手順を保証しない。手元の端末で実際に実行して初めて確認済みになる。

5端末で各回 `source /opt/ros/jazzy/setup.bash; source .venv/bin/activate` を行う。

```bash
# A: simulation
gz sim -r -v 4 worlds/rescuemind_test_arena.sdf
# B: ROS/Gazebo bridge
bash scripts/bridge_direct_gazebo.sh
# C: independent velocity relay
bash scripts/start_velocity_guard.sh
# D: live sensors and guard identity
bash scripts/v13_runtime_diagnostics.sh
# E: non-AI robot movement, after diagnostics pass
python3 ros/gazebo_waypoint_mission.py --motion-check
```

失敗時は`outputs/local_runtime_diagnostics/`のROS/GZトピック一覧と標準エラーを確認。`gz topic -l`に`/cmd_vel`、`/odom`、`/scan`、`/camera`が揃うか検査。トピック名は必ず実画面と照合してからブリッジを調整する。

APIキーがあるときのみ、別のターミナルで安全な実験シーンを作り：

```bash
export TYPESAFE_API_KEY='(ローカルで設定・履歴に残さない)'
export DASHSCOPE_API_KEY='(ローカルで設定・履歴に残さない)'
export DASHSCOPE_BASE_URL='https://(ワークスペースの正しいendpoint)/compatible-mode/v1'
python3 ros/gazebo_waypoint_mission.py --run-live \
  --instruction '避難所Bに飲料水を届けて'
```

CLI引数よりも実際の`DASHSCOPE_BASE_URL`環境変数がQwen3.8への接続先を決める。Jevは外部HTTPSサービス。失敗時にはガードとミッション両方を停止、Gazeboを一度停止して再起動する。**研究用シミュレータ限定であり、人や物に対する安全性を保証しない**。

ログにはAPIキーを含めない。録画はGazeboの実物のみとし、2D数理アニメーションで代用しない。提出用PDFは実測後に生成する。
