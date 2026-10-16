# Ubuntu NVIDIA GPU PC ハンズオン手順

## 0. 環境スナップショット

```
bash scripts/check_ubuntu_ros.sh | tee outputs/local_environment.txt
python3 --version
nvidia-smi
```

Ubuntu24.04以外なら最初に版を確認。ROS/JazzyはUbuntu24.04の公式deb配布に合わせる。CUDA/PyTorch GPU必要なのはローカルQwen3.5の場合だけで、クラウドQwen3.8/Jevでは必須ではない。

## 1. Pythonのみ

```
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install -e .
bash scripts/verify_all.sh
```

## 2. Nav2公式サンプル

```
source /opt/ros/jazzy/setup.bash
ros2 launch nav2_bringup tb3_simulation_launch.py headless:=False
```

別端末で: `ros2 topic list`、`ros2 action list`、`ros2 node list`。Nav2利用中に指定ゴール到達を手動操作で確認。`/clock`配信とTFの`map→odom→base_link`の整合性を確認。

## 3. カメラ実装

標準tb3_simulationにカメラが保証されない。`ros2 topic list -t`に画像トピックが無ければ、Gazeboカメラプラグインと`ros_gz_bridge`を組み込んだモデルまたは既存カメラ付きロボットを使い、まず1枚保存。RGB/BGR画像が対応。`sensor_msgs/msg/CompressedImage`は未対応。

## 4. ゴール校正

`configs/poses.example.json`を現地マップ座標に変更。`initial`, `water`, `medicine`, `A`, `B`をRVizで検証。`ros/nav2_mission.py`は目標指示のみで把持操作は行わない。

## 5. 実モデル

キーはシェル履歴に残さない方法を推奨（ローカル.env管理、GitHubには絶対に追加しない）。API利用規約・データ送信先を確認。カメラ画像に顔・氏名・メール・住所等を入れない。Jev画像は実験段階なので公開用に偽の成功率を作らない。

## 6. よくあるエラー

- `TYPESAFE_API_KEY missing` → **仕様通り拒否**。実APIキー設定が必要。
- `DASHSCOPE_BASE_URL` → 利用リージョンのworkspace URLを管理画面から設定。
- `No camera image received` → 画像トピック/bridge/ROS_DOMAIN_ID/QoS設定を確認。
- `Nav2 cannot plan` → 地図と座標の整合性・コストマップ/初期位置を確認。
- `Jev ... Danger-Zone` → experimental headerと画像サイズ、プロバイダ側の仕様変更を確認。
- `Model output JSON invalid` → ガードは拒否。モデルの出力形式を記録し、パーサ変更は新たなテストを追加してから。
