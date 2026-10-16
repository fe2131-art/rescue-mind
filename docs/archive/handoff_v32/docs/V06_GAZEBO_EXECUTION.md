# v0.6: Gazeboワールドを実際に走行させる手順（ユーザーのUbuntuで実行）

**現在の検証レベル：実装・モック/数学モデルのみ。Gazebo Harmonic上の動作は、この配布時点で未確認。**

## 重要：２つの経路を混同しない

- `ros/nav2_mission.py`：**Nav2経路**。公式TurtleBot3サンプルが最短。Nav2による障害物回避と再計画を狙う。課題動画のメイン候補。独自ワールドとの接続は未完成。
- `ros/gazebo_waypoint_mission.py`：**直接駆動経路**。独自Gazeboワールド（物資拠点/避難所）で車輪駆動とオドメトリを確認するための新経路。ナビゲーションの再計画は実装していない。停止・センサ欠損は保守的に扱う。

## 環境

Ubuntu 24.04 + ROS 2 Jazzy + Gazebo Harmonic + ros_gz_bridge。NVIDIA GPU推奨（Gazeboカメラ・GPU LiDAR）。

```
source /opt/ros/jazzy/setup.bash
sudo apt update
sudo apt install ros-jazzy-ros-gz-bridge ros-jazzy-navigation2 ros-jazzy-nav2-bringup
```

ここで述べたaptパッケージ名は公式ROS/Gazebo手順を参考にしているが、使用するaptリポジトリとOS設定によって異なる。`bash scripts/check_ubuntu_ros.sh` で確認。

## 実行フロー（ターミナル4個）

ターミナルA（Gazebo、本当に画面が描画されるか確認）：

```
cd rescuemind_v06
source /opt/ros/jazzy/setup.bash
gz sim -r -v 4 worlds/rescuemind_test_arena.sdf
```

ターミナルB（Gazebo topicを確認してROSにブリッジ）：

```
gz topic -l | grep -E '/(scan|camera|odom|cmd_vel)'
bash scripts/bridge_direct_gazebo.sh
```

ターミナルC（必ず受信確認）：

```
source /opt/ros/jazzy/setup.bash
ros2 topic list
ros2 topic echo /odom --once
ros2 topic echo /scan --once
```

`/camera` が存在すれば、別の端末で 

```
python ros/capture_camera_frame.py --topic /camera --output outputs/supply.jpg
```

を実行する。`camera` トピックが別名の場合は `gz topic -l` で確かめ、ブリッジ引数を修正する。**ただし水/医療物資が写った画角を実際に確保する必要がある**。遠方で小さい、写らない、遮蔽がある場合には画像モデルが不確実となりミッションを許可しないのが正しい動作。廊下画像も別撮影して、異なる時点・方向の画像であることを人間が確かめる。

ターミナルD（まずキーなしの運動動作テスト）：

```
source /opt/ros/jazzy/setup.bash
python ros/gazebo_waypoint_mission.py
python ros/gazebo_waypoint_mission.py --motion-check --out outputs/gazebo_motion_check.json
```

`--motion-check` は**モータ・ROS bridgeの確認だけ**であり、AI課題の成功とは主張できない。物資ステーションの接近・避難所への到達だけを検査する。動いた場合はシミュレータを初期位置にリセットして次へ進む。

最後に実APIキー/画像（ユーザー環境でのみ）を用意して、**Jevが必須**のミッション実行：

```
export TYPESAFE_API_KEY='<secret>'
export DASHSCOPE_API_KEY='<secret>'
export DASHSCOPE_BASE_URL='https://<workspace>.<region>.maas.aliyuncs.com/compatible-mode/v1'
python ros/gazebo_waypoint_mission.py --run \
  --preflight-image outputs/supply.jpg \
  --corridor-image outputs/corridor.jpg \
  --qwen-model qwen3.8-omni-flash \
  --out outputs/real_gazebo_run.json
```

画像は既定で120秒以内のファイル更新時刻が必要。実際に異なる画像でない場合は拒否。API障害、回答不一致、危険の疑いでも拒否される。

ミッションが成功したときのログ自己整合性：

```
python scripts/audit_robot_run.py --record outputs/real_gazebo_run.json
```

ただしログを人手で編集することも可能であり、この検証に**実物証拠の真贋判定能力はない**。Gazebo画面、端末ログ、録画、取得したセンサデータの時刻を合わせて残す。

## デバッグ

1. Gazeboを再生しているか (`-r`)、GPU LiDAR/Cameraが生成されているかを確認。
2. `gz topic -l` のトピック名がSDF記載と一致しているかを確認。特定のディストリビューションではスコープ付きになり得る。
3. ブリッジ方向：`/cmd_vel`はROS→GZ `]`、`/odom` `/scan` `/camera`はGZ→ROS `[`。
4. 初期位置がワールド原点かを検査。2D目標座標はSDFから作成した仮値で、実動作の校正が必要。
5. `--motion-check` は障害物回避しない。衝突を検知しなければ即座に中止し、Nav2を使う。物理安全を保証しない。
6. `worlds/*.sdf` と `configs/gazebo_waypoints.json` を変更したら、再度両者の一致を試験する。

## 実証で使う言葉

- 成功したら「JevとQwenの走行前判断に基づき**物資拠点に接近し避難所まで到達する**」と記載。
- 「箱を実際に把持した」「実物資を輸送した」「Jevが障害物を物理座標として推定した」「安全性保証」などは記載しない。
