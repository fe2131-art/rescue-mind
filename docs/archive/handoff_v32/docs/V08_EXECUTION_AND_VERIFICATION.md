# RescueMind v0.8 — Ubuntu実行ランブック（2026-10-16）

## 0. 作品の正しいスコープ

Jev 1.14.0を**必須**としたQwen3.8-Omni-Flashとの現地物資二重認識。ROS 2/Jazzy＋Gazebo/Harmonic上の二輪ロボットは物資拠点を訪問し、ロボット自身のカメラ観測に基づくJevとQwenの合意があった場合のみ避難所B付近まで移動する。**搬送・把持・積み込みはしていない**。独自ワールドの直接駆動はNav2ではなく、動的再計画もできない。LiDARは停止のためのみ使用。API画像判断は安全認証を意味せず、実機に使わない。

## 1. 最初に実行（APIキー不要）

```bash
cd rescuemind_v08
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
bash scripts/v08_verify.sh
bash scripts/check_ubuntu_ros.sh
```

出力: `outputs/release/v08_verification.json`, `v08_static_scene_contract.json`, `v08_counterfactual_software.json`。`gazebo_present=false`なら、物理動作はまだ実証されていない。`validate_gazebo_world.py`の合格はXML/SDFの静的検査にすぎない。

## 2. Ubuntu 24.04 / Jazzy / Harmonic

公式ドキュメントに従ってUbuntu 24.04、ROS 2 Jazzy、Gazebo Harmonic、`ros-jazzy-ros-gz-bridge`をインストール。Ubuntu 22.04など別バージョンでは無理にJazzy/Harmonicのコマンドを流用しない。

```bash
# 端末A：Gazebo（本物の物理シミュレータが必要）
source /opt/ros/jazzy/setup.bash
gz sim -r -v 4 worlds/rescuemind_test_arena.sdf

# 端末B：トピック名を確認後にブリッジ
source /opt/ros/jazzy/setup.bash
gz topic -l
bash scripts/bridge_direct_gazebo.sh

# 端末C：通信と時刻・周波数
source /opt/ros/jazzy/setup.bash
ros2 topic list
ros2 topic echo /odom --once
ros2 topic echo /scan --once
ros2 topic echo /camera --once
ros2 topic hz /odom
ros2 topic hz /scan
```

`/camera`の画像は大きいのでフル出力を常時echoしない。トピックが出なければ `gz topic -l` で実際のtopic名を確認。必要ならbridge引数を合わせる。自律走行前に必ず空間・前方障害物・停止動作を目視。

## 3. JevとQwenの契約

```bash
# exportは現在のターミナルのみ。キーを撮影画面やログ、GitHubに映さない。
export TYPESAFE_API_KEY='...'
export DASHSCOPE_API_KEY='...'
export DASHSCOPE_BASE_URL='https://<actual-workspace>.<region>.maas.aliyuncs.com/compatible-mode/v1'
```

Jev APIは https://api.typesafe.ai/v1/systemone 、`jev-1.14.0`にピン留め。画像送信時は`TypeSafe-Danger-Zone-Images: true`、`assets`の画像参照、`choice`/`noul`/`box`を使う。TypeSafeは画像/Boxを実験的機能と明記。Boxのみで対象存在を判断しない。Qwen3.8はAlibaba Cloud API経由であり、ローカルGPUで動く重みモデルではない。リージョン一致のキーを使うこと。

## 4. 非AI車輪試験と、本命の現地AIミッション

```bash
# 端末D：最初は必ずAIなし。結果を最終課題のAI成果と混同しない。
source /opt/ros/jazzy/setup.bash
python ros/gazebo_waypoint_mission.py --motion-check --out outputs/motion_check.json

# NEW v0.8：事前画像をファイルで用意しなくてよい。移動後に実カメラを取得。
# JevとQwenの両方のキーがない／API失敗／不一致では避難所へ進まない。
python ros/gazebo_waypoint_mission.py \
  --run-live --instruction '避難所Bに飲料水を届けて' \
  --out outputs/real_gazebo_v08_water.json \
  --checkpoint-image outputs/on_site_water_v08.jpg

python scripts/audit_robot_run.py --record outputs/real_gazebo_v08_water.json \
  --out outputs/real_gazebo_v08_water_audit.json
```

**実行開始前に** `ros2 topic echo /odom --once`、`ros2 topic echo /scan --once`、`ros2 topic echo /camera --once`が有効であることを確かめる。水拠点画像が画角から外れた場合は「正しく不許可」になり得る。その場合、映像を保存して座標・向き・FOVを見直す。未知指示・複数物資指定・対応外避難所A/Cは走行開始前に拒否。

## 5. 既存v0.7互換モード

`--run --preflight-image a.jpg --corridor-image b.jpg` は残したが、**事前の独立画像2枚が必要**。実際の巡回画像と整合しない問題を避けるため本番動画には`--run-live`を推奨。ただし`--run-live`には出発前VLM判定がなく、出発後の現地カメラ判定のみという違いを明記すること。

## 6. 必ず失敗例も記録

成功、Qwen/Jev不一致、画像無し、通信切断、障害物停止、未知指示、APIタイムアウトなどを分離して、スクリーン録画とJSONを保全。モックの単体テストは実API性能ではない。真の危険物判定、安全性や物流能力を立証しない。

## 7. 提出前

- [ ] 本物のGazeboシミュレータでロボットが動く1〜3分のMP4を撮影（2倍速時は明記）
- [ ] 動画でJeVとQwenの決定を出すなら、APIキーなど秘密情報を完全に隠す
- [ ] 実際のモデル判定ログに、目視ラベル・画像ハッシュ・日時・利用モデル・失敗時理由を記録
- [ ] PDFを `説明資料_PAI最終課題_<omnicampusアカウント名>.pdf` に変更
- [ ] 公開GitHubの全ファイルの個人情報・秘密情報を確認
- [ ] YouTube 1〜3分、タイトル `PAI最終課題_<アカウント名>`、最低「限定公開」、子ども向け/年齢制限「いいえ」
- [ ] 11月2日 AM10:00より十分前に提出、削除・非公開にしない
