# v2.5 最初に読むガイド (Ubuntu 24.04 / NVIDIA GPU)

## オフライン検証（ROS未導入でも実行）

```bash
cd rescuemind_v25
python3 -m pip install -e .
bash scripts/v25_verify.sh
python3 scripts/v25_camera_audit.py
```

`verification/v25/verification.json` には本実行環境で実行できた検証結果を保存します。

## UbuntuでGazeboの実行を始める

```bash
bash scripts/check_ubuntu_ros.sh
bash scripts/setup_ubuntu_jazzy.sh
python3 scripts/v22_orchestrate.py --plan --scenario motion-check --scene nominal
python3 scripts/v22_orchestrate.py --run --scenario motion-check --scene nominal --capture-rosbag
```

このコマンドは **Gazebo実行成功の保証ではありません**。失敗すればログを確認し、ROS 2 Jazzy/Gazebo Harmonic/ros_gz_bridge/グラフィックス環境を整えます。AIなしのmotion-checkは最終AI作品の実証には使えません。

## Jev＋Qwenの現地判断 (API認証情報が必要)

キーをリポジトリ、ログ、動画に書かないこと。

```bash
export TYPESAFE_API_KEY='(自分の秘密鍵)'
export DASHSCOPE_API_KEY='(自分の秘密鍵)'
export DASHSCOPE_BASE_URL='https://(ワークスペース).ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1'
python3 scripts/v22_orchestrate.py --run --scenario live --scene nominal --capture-rosbag \
    --instruction '避難所Bに飲料水を届けて'
```

初回はnominalでロボット到着→カメラ方向合わせ→新フレーム撮影→Jev＋Qwen一致→避難所を検証。次にswapped/emptyで誤物資・欠品の拒否を確認。`--scene`だけを変更し、残りの条件を固定します。

**最新ログの目印:** `camera_aim_aligned` → `checkpoint_frame` → `checkpoint_decision`。これらはコード内イベントであり、実物画像は別途目視確認が必要です。

## 実画像を確認する（重要）

カメラ投影検査は簡易幾何のみです。実Gazeboの`/camera`画像、物資全体の見え方、棚による隠れ、画像の露出、赤十字表示の向き、RGB順序を実際に確認してください。物資が画角内でも認識できるとは限りません。

## 実験と提出

- 30試行事前登録: `experiments/v23_locked_protocol.json`。`nominal / swapped / empty` × 水/薬 ×5。
- `scripts/v24_register_trial.py` は実走行ログ＋Jev/Qwen出力とv2.5のカメラ時系列を検査します。
- 合格条件: 1〜3分のロボット実行MP4、GitHub publicコード、PDFレポート、OmniCampusとYouTube提出。
- 提出締切: 2026-11-02 10:00 JST。レポートと動画に氏名・所属・メール・APIキーを含めません。
- 真の評価指標: nominal到達率、swapped/emptyの誤許可率、正常拒否率、推論遅延、API失敗率。模擬テストの数字を流用しません。
