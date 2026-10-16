# Ubuntu + NVIDIA GPU 実行手順 v1.0

## 0. 環境診断

Ubuntu 24.04、ROS 2 Jazzy、Gazebo Harmonicを想定。検証済み実行コンテナでは `ros2` と `gz` が不在であり、**ここからはUbuntuホスト側で実測**する必要がある。APIキーをGitHubやZIPへ入れない。

```bash
cd rescuemind_v10
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
bash scripts/v10_verify.sh
bash scripts/check_ubuntu_ros.sh
nvidia-smi
```

## 1. 3つのターミナルを開く

```bash
# A: Gazebo (play buttonが有効なこと)
source /opt/ros/jazzy/setup.bash
gz sim -r -v 4 worlds/rescuemind_test_arena.sdf
```
```bash
# B: bridge
source /opt/ros/jazzy/setup.bash
bash scripts/bridge_direct_gazebo.sh
```
```bash
# C: sensor readiness; this must PASS before driving
source /opt/ros/jazzy/setup.bash
bash scripts/live_readiness.sh
```

`gz topic -l`に `/cmd_vel`, `/odom`, `/scan`, `/camera`が現れるか確認。Gazebo側の名前空間が違えばbridgeの対応を変更する。`/camera`で Image headerに撮影時刻が入り、連続増加することを確認。

## 2. 車輪・センサのみの試験（AIとは呼ばない）

```bash
python3 ros/gazebo_waypoint_mission.py --motion-check --out outputs/local_motion.json
```

意図と異なる移動、障害物衝突、異常なLiDAR停止があれば中止。`--motion-check`はAIが一切関与しない**非AIベースライン**。

## 3. Jev必須のライブAI判定

```bash
# 実際のサービスで発行した値をターミナルの履歴や動画に表示しない
export TYPESAFE_API_KEY='...'
export DASHSCOPE_API_KEY='...'
export DASHSCOPE_BASE_URL='https://<workspace>.<region>.maas.aliyuncs.com/compatible-mode/v1'
python3 ros/gazebo_waypoint_mission.py --run-live \
  --instruction '避難所Bに飲料水を届けて' \
  --checkpoint-image outputs/local_runtime_diagnostics/water_frame.jpg \
  --out outputs/local_runtime_diagnostics/water_mission.json
```

**重要**：文字列 `<workspace>` は例示であり、そのまま使わない。使用リージョンの公式Model Studio画面のURLで置換する。実行スクリプトは開始前に存在・形式を検査するが、キーが有効か、APIが利用可能かは物資拠点到着後の実応答を要する。Jev/Qwenどちらかがエラーなら次区間を許可しない。

## 4. 1〜3分実録動画と監査

```bash
# 別ターミナル / X11 GUI; WaylandならOBS等で録画
RECORD_SECONDS=120 bash scripts/record_gazebo_evidence.sh
# 走行結果JSONだけではロボットが実際に動いた証拠として不十分
python3 scripts/audit_robot_run.py \
  --record outputs/local_runtime_diagnostics/water_mission.json \
  --out outputs/local_runtime_diagnostics/audit.json
python3 scripts/build_evidence_bundle.py \
  --record outputs/local_runtime_diagnostics/water_mission.json \
  --frame outputs/local_runtime_diagnostics/water_frame.jpg \
  --video outputs/local_runtime_diagnostics/actual_gazebo_raw.mp4 \
  --out outputs/local_runtime_diagnostics/actual_evidence_bundle.zip
```

証拠パッケージは動画60〜180秒、ROS現地画像SHA-256、イベント順序、モデル合意ログを照合し、失敗ならZIPを作らない。これは**本物の映像かどうかを自動的に保証するものではない**。実録画を目視で確認し、個人情報をすべて除外する。

## 5. 実験とレポート

水・医療物資の正しい物資、間違い、不可視、危険画像をそれぞれ用意。正解ラベルを事前に人手で付け、同一画像をJev単体、Qwen単体、合意方式で比較。結果は `rescuemind-benchmark` か `python -m rescuemind.benchmark_vision --records ...` で集計。現時点の配布物には**実API測定値はない**。

最終提出PDFや動画名は課題原文を参照。提出前に `scripts/submission_preflight.py` で形式をチェックし、公開状態はブラウザで人手確認。
