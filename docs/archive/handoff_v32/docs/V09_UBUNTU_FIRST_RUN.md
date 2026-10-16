# RescueMind v0.9 — Ubuntu 24.04 / NVIDIA PC の実行手順

## A. 先にZIPだけで検証（APIキー不要・ROS不要）

```bash
unzip RescueMind_v0.9_award_improvement_verified.zip
cd rescuemind_v09
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install -e .
bash scripts/v09_verify.sh
bash scripts/check_ubuntu_ros.sh
```

`outputs/release/v09_verification_summary.json`の `actual_gazebo_motion_verified=false` はこの実行環境から確認できていないことを表す。ローカルPCで成功したら別途証拠を追加する。

## B. 実GazeboとROS 2（別々の端末）

Ubuntu 24.04 + ROS 2 Jazzy + Gazebo Harmonic が基本。インストール方法はROS/Jazzy・Nav2/Gazebo公式手順を使用し、バージョンを混在させない。

```bash
# 端末1: Gazebo
source /opt/ros/jazzy/setup.bash
gz sim -r -v 4 worlds/rescuemind_test_arena.sdf

# 端末2: ROS/Gazebo topic bridge
source /opt/ros/jazzy/setup.bash
bash scripts/bridge_direct_gazebo.sh

# 端末3: 実際にメッセージが来ているか検査
bash scripts/live_readiness.sh
```

`live_readiness.sh`は `/odom`、`/scan`、`/camera` の**受信**を検査する。カメラに物資が映っているか、ロボットがGazeboで物理的に走るかの確認ではない。センサー型、フレームID、Odometryの原点、Gazebo側のTopic名・QoS、足回り接地が適切か目視でも確認する。

## C. まず車輪だけ実走行（AIなし）

```bash
source /opt/ros/jazzy/setup.bash
python ros/gazebo_waypoint_mission.py --motion-check --out outputs/local_motion.json
```

注意：この直接駆動コントローラは**Nav2ではない**。固定ウェイポイントに向かい、危険時は停止する。障害物再経路計画はしない。物資を把持・積載しない。障害物があると近接検出または停滞検出で停止する設計。

## D. Jev＋Qwenを使って現地判断

キーは絶対にREADME、公開GitHub、コマンドのスクリーン録画、PDFへ書かない。ターミナル画面に`export`値を映さない。

```bash
export TYPESAFE_API_KEY='REPLACE_LOCALLY'
export DASHSCOPE_API_KEY='REPLACE_LOCALLY'
export DASHSCOPE_BASE_URL='https://<your-workspace>.<your-region>.maas.aliyuncs.com/compatible-mode/v1'

python ros/gazebo_waypoint_mission.py --run-live \
  --instruction '避難所Bに飲料水を届けて' \
  --checkpoint-image outputs/local_on_site_water.jpg \
  --out outputs/local_live_water.json

python scripts/audit_robot_run.py \
  --record outputs/local_live_water.json \
  --out outputs/local_live_water_audit.json
```

**物資拠点への出発は自然言語ポリシーとセンサー検査で決定し、物資拠点到着後の第二走行はJevとQwenの両方が一致かつ危険が明示されない場合のみ許可**。両モデルのオンライン可用性や実画像精度を確認しない限り本番完成ではない。

## E. スクリーン録画・実証

Gazebo・端末の判定ログなどを機密情報が見えない位置に配置したうえで、X11の場合は次のコマンドが使用できる。

```bash
RECORD_SECONDS=120 SCREEN_SIZE=1920x1080 bash scripts/record_gazebo_evidence.sh
ffprobe -v error -show_entries format=duration -of default=nw=1 outputs/local_runtime_diagnostics/actual_gazebo_raw.mp4
```

Wayland環境ではOBS Studio等のGUIで実際の画面を収録。録画スクリプトが生成するものは**実画面そのもの**であり、完成済みデモを合成するものではない。倍速時は動画内または説明欄に明記し、最終動画は1〜3分。

## F. 問題別対応と撤退基準

- `no camera`: `gz topic -l`とROSブリッジのcamera方向を確認。Gazebo GUIのレンダラ/OGRE2/ドライバも確認。
- `no odometry`: 差動二輪プラグインと車輪ジョイント、Gazebo再生状態、`/odom`橋接を確認。
- `front_obstacle_too_close`: 近接停止。最小距離と物資棚/避難所の接近点を再設計。センサーを無効化して走行しない。
- `drive_commanded_but_no_translation`: 車輪接地、コントローラ座標、静的障害物、物理パラメータを調整。
- `checkpoint DENIED`: 現地実画像を保存し、Jev/Qwenラベルと危険判定・画角・APIエラーを分解して原因を記録。許可条件の緩和は実データで正当化できたときのみ。
- **10/23までに独自ワールドで走らない場合**：ROS 2/Nav2公式TurtleBot3サンプルへ切り替え、Jev+Qwenのチェックポイント・安全判定ロジックを再利用する（アダプタ移植が必要。完成済みとは主張しない）。

## G. 提出前チェック

- YouTube: 1〜3分、タイトル `PAI最終課題_<omnicampusアカウント名>`、最低限定公開。子ども向け・年齢制限「いいえ」。公開設定の詳細は課題文に従う。
- OmniCampus: `説明資料_PAI最終課題_<omnicampusアカウント名>.pdf` と public GitHub URL、および YouTube URL。
- 氏名・所属・メール・APIキーをレポート、コード、動画に残さない。
- `scripts/submission_preflight.py` は形式しか判定しない。公開状態・実映像は人の確認が必要。
