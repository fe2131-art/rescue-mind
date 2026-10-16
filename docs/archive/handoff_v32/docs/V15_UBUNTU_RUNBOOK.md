# RescueMind v1.5 Ubuntu 24.04で今すぐ動かす手順

前提：Ubuntu 24.04、NVIDIA GPU、ROS 2 Jazzy、Gazebo Harmonic、Python 3。詳細なapt導入は公式ROS/Gazeboに従う。

```bash
cd rescuemind_v15
bash scripts/check_ubuntu_ros.sh
bash scripts/setup_ubuntu_jazzy.sh
bash scripts/v15_verify.sh
python3 scripts/v15_orchestrate.py --plan --scenario motion-check
```

最初に必ず**AIなしの走行テスト**を行う（この結果は提出用のAI成功証拠ではない）。

```bash
python3 scripts/v15_orchestrate.py --run --scenario motion-check
```

- `v15_orchestrate` は Gazebo・ROS/Gazebo bridge・独立速度ガードを順に起動する。
- `scripts/v15_live_readiness.sh` は**ガード単独publisher**を確認し、Camera/LiDAR/Odomがそれぞれ3件以上、異なる取得タイムスタンプを持ち基本的に妥当であることを検証する。失敗時は `outputs/local_runtime_diagnostics/v15_sensor_probe.json` と `outputs/runs/*/readiness_last.txt` を確認。
- SDF独自worldで実Gazebo駆動が成功するかはUbuntu上で初めて判明する。初回は物理的な移動・センサ値を画面上で確認。
- センサーが未着の場合は `gz topic -l`、`ros2 topic list -t` を比較し、必要なら `scripts/bridge_direct_gazebo.sh` を見直す。GazeboをPlay状態にする。
- 画面録画前にsource tree、APIキー等の個人情報が画面に映っていないことを確認。

`TYPESAFE_API_KEY`、`DASHSCOPE_API_KEY`、`DASHSCOPE_BASE_URL`を**手元の環境変数**に設定した後だけ、以下を実施する。パッケージやGitHubに秘密情報を同梱しない。

```bash
python3 scripts/v15_orchestrate.py --run --scenario live \
  --instruction '避難所Bに飲料水を届けて'
```

判定の通過/拒否を両方撮影し、`outputs/runs/<id>/`内のJSON・JPEG・各プロセスログを保存する。ファイルを公開する前に個人情報と認証文字列を点検する。

## 完成条件

- [ ] Gazebo実画面で二輪ロボットが走行した（実測、未完了）
- [ ] 現地ROSカメラ画像が目視で物資を捉える（実測、未完了）
- [ ] Jev実API + Qwen実APIによる、正物資→続行と誤物資→停止を再現（実測、未完了）
- [ ] 少なくとも3種類の認識条件と反復試験で、誤許可/誤拒否を算出（未完了）
- [ ] 元のロボット実動作から60〜180秒MP4作成（未完了）
- [ ] レポートPDF名、public GitHub、YouTube題名/公開状態、非個人情報を確認（未完了）
