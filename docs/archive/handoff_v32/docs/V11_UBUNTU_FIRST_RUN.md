# Ubuntu/NVIDIA GPUで実機相当Gazeboを試す手順

推奨：Ubuntu 24.04 / ROS 2 Jazzy / Gazebo Harmonic。ユーザーのUbuntuバージョンが異なる場合は公式互換表を確認。個人アカウント/APIキーは動画・GitHubに含めない。

## 1. まずオフライン
```bash
cd rescuemind_v11
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
bash scripts/v11_verify.sh
bash scripts/check_ubuntu_ros.sh
```
`outputs/release/v11_verification.json` にテスト件数、ROS/Gazeboの利用可否が出力される。

## 2. Gazebo + ROS Bridge (別端末)
```bash
# 端末A
source /opt/ros/jazzy/setup.bash
gz sim -r -v 4 worlds/rescuemind_test_arena.sdf
```
```bash
# 端末B
source /opt/ros/jazzy/setup.bash
bash scripts/bridge_direct_gazebo.sh
```
```bash
# 端末C
source /opt/ros/jazzy/setup.bash
bash scripts/live_readiness.sh
```
`gz topic -l`でトピック名を確認し、`ros2 topic hz /camera` と`ros2 topic hz /odom`でハートビートを確認。Gazeboの再生/一時停止状態も確認。

## 3. 最初はモデルなしで車輪を動かす
```bash
python ros/gazebo_waypoint_mission.py --motion-check \
  --out outputs/local_runtime_diagnostics/motion_check.json
```
ロボットが座標通りに動くか、障害物で止まるか、`/odom`方向とワールドが整合するか確認。失敗時はAIのAPIを呼ばず、SDF接地・ROSブリッジ・LiDAR範囲を修正。

## 4. Jev必須 + Qwen実API（どちらも環境設定を個別に取得）
```bash
export TYPESAFE_API_KEY='(本物のAPIキーをシェル内だけに入力)'
export DASHSCOPE_API_KEY='(Model Studio APIキーをシェル内だけに入力)'
export DASHSCOPE_BASE_URL='https://YOUR_WORKSPACE.REGION.maas.aliyuncs.com/compatible-mode/v1'
python ros/gazebo_waypoint_mission.py --run-live \
 --instruction '避難所Bへ飲料水を届けて' --camera-max-age 3.0
```
有効なAPIアクセスとカメラ画像がない場合は**停止**し、成功したふりをしない。モデル呼び出し中もカメラとLiDARとodomを監視。出力ログ・画像はデフォルトで`outputs/runs/<run_id>/`へ保存。

## 5. 実際の映像とログをチェックして証拠ZIPにする
```bash
# X11の場合。Waylandの場合はOBS等で実際のGazebo画面を収録
RECORD_SECONDS=120 bash scripts/record_gazebo_evidence.sh
python scripts/audit_robot_run.py --record outputs/runs/<ID>/mission.json
python scripts/build_evidence_bundle.py \
 --record outputs/runs/<ID>/mission.json \
 --frame outputs/runs/<ID>/on_site_supply.jpg \
 --video outputs/local_runtime_diagnostics/actual_gazebo_raw.mp4 \
 --out outputs/local_runtime_diagnostics/evidence_<ID>.zip
```
APIログ、画像、Gazebo画面、真の動作を人間が照合する。動画の個人情報除去、公開権利、コード秘密情報、GitHub public、YouTube公開条件は手動確認が残る。

## フォールバック
ROS-Gazeboの静的検査が通っても実接地・撮像・動作が保証されない。もし独自ワールドで安定しなければ、講座許可の別環境（公式Nav2サンプル）へ移行し、Jevがミッション継続の判断を行う部分を必ず残す。
