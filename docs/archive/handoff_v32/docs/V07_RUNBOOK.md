# Ubuntu 24.04 + Jazzy + Gazebo Harmonic 実行ガイド v0.7

**この配布ZIPはPython検証済み、ROS/Gazebo・Jev・Qwen実APIは未検証です。**

## オフライン事前試験

```bash
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install -e .
bash scripts/verify_all.sh
bash scripts/check_ubuntu_ros.sh
```

## ステップA：Gazeboブリッジ接続（実GPUマシン）

ターミナル1：`gz sim -r -v 4 worlds/rescuemind_test_arena.sdf`

ターミナル2：`bash scripts/bridge_direct_gazebo.sh`

ターミナル3：
```bash
source /opt/ros/jazzy/setup.bash
ros2 topic echo /odom --once
ros2 topic echo /scan --once
ros2 topic info /camera
```

ターミナル4：
```bash
python ros/gazebo_waypoint_mission.py          # DRY RUN
python ros/gazebo_waypoint_mission.py --motion-check --out outputs/motion_check.json
```

※ motion-check はJevを通さない車輪制御試験のため、**AI課題の成功映像としては扱わない**。Gazeboを初期位置にリセットしてから次へ進む。

## ステップB：出発前撮影とJev＋Qwen

水/医療物資が画角に入るように撮影し、通路は別角度・別時刻で撮影する。ガイドの都合上、人間が適切な画角にカメラを向ける工程があり、全自動の視覚探査ではない。

```bash
python ros/capture_camera_frame.py --topic /camera --output outputs/supply.jpg
# ロボット/カメラを通路方向へ向けた後、別フレームを撮影
python ros/capture_camera_frame.py --topic /camera --output outputs/corridor.jpg
export TYPESAFE_API_KEY='<secret>'
export DASHSCOPE_API_KEY='<secret>'
export DASHSCOPE_BASE_URL='https://<workspace>.<region>.maas.aliyuncs.com/compatible-mode/v1'
python -m rescuemind.multimodal_demo \
  --image outputs/supply.jpg --corridor-image outputs/corridor.jpg --expected water \
  --qwen-model qwen3.8-omni-flash
```

実画像のモデル回答が揃わなければ走行拒否が正常。APIキーは端末履歴・画面録画・GitHubに映さないこと。

## ステップC：二段階AIミッション

```bash
# Gazeboを原点にリセットしてから
python ros/gazebo_waypoint_mission.py --run \
  --preflight-image outputs/supply.jpg \
  --corridor-image outputs/corridor.jpg \
  --qwen-model qwen3.8-omni-flash \
  --camera-topic /camera \
  --checkpoint-image outputs/on_site_supply.jpg \
  --out outputs/real_gazebo_v07.json
```

**必須のAIゲートは2箇所**：出発前（Jev+Qwen+通路判定）および物資拠点到着後（実ROS camera新規フレームからJev+Qwenで物資再確認）。後者が失敗すれば避難所へは出発しない。AI問い合わせ中は速度ゼロを定期送信し、LiDAR/odom途絶なら停止する。ただし実ROSでの挙動は未確認。

## ステップD：監査、録画、提出

```bash
python scripts/audit_robot_run.py --record outputs/real_gazebo_v07.json \
  --out outputs/mission_audit.json
python scripts/make_overlay_srt.py --record outputs/real_gazebo_v07.json \
  --output outputs/overlay_draft.srt
```

SRTは**ログから作る字幕の下書き**であって映像の捏造ではない。必ず実際のGazebo画面録画と時刻を突き合わせること。録画は1-3分、YouTube限定公開以上で提出する。

## 未検証/撤退基準

- 2026/10/23までに独自ワールドが安定走行しなければ公式Nav2/TurtleBot3経路を選ぶ。
- 実モデルがGazeboの簡素な物資形状を認識しなければ、実画像テクスチャや照明を変更して再評価。ラベルや閾値を正解に合わせて恣意的にいじらず、失敗例も記載する。
- 物理的な積み込み機構は存在しないため、「物資の物理配送」成功とは主張しない。
