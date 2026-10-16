# RescueMind v1.6 — Start here

## Off-line verification (no ROS/Gazebo/API credentials)

```bash
cd rescuemind_v16
bash scripts/v16_verify.sh
python3 scripts/v16_orchestrate.py --plan --scenario live
```

`outputs/release/v16_VERIFICATION.json` はオフラインのテスト結果です。実際のGazebo成功率、AIの認識率、動画要件の合否とは区別してください。

## Ubuntu 24.04 + NVIDIA GPU + ROS 2 Jazzy + Gazebo Harmonic

```bash
bash scripts/check_ubuntu_ros.sh
bash scripts/setup_ubuntu_jazzy.sh
python3 scripts/v16_orchestrate.py --run --scenario motion-check
```

実Gazeboで車輪が動いた後にJeVとQwenのAPI設定を手元の環境変数で指定します（ZIP/公開GitHubにキーを記録しない）。

```bash
export TYPESAFE_API_KEY='YOUR_SECRET'
export DASHSCOPE_API_KEY='YOUR_SECRET'
export DASHSCOPE_BASE_URL='YOUR_OFFICIAL_HTTPS_WORKSPACE_ENDPOINT'
python3 scripts/v16_orchestrate.py --run --scenario live --instruction '避難所Bに飲料水を届けて'
```

`outputs/runs/<run_id>/` に現地撮影画像、イベントJSON、子プロセスログを残します。ログが実行ID・到着順序・Jev/Qwen二重判定の検査を通過するまで、`COMPLETED`にはなりません。これは証拠の**構造整合性**であり、Gazebo映像やAPI応答の真正性そのものを証明しません。

評価戦略: `docs/V16_AWARD_STRATEGY.md`、調査と根拠: `docs/V16_PRIMARY_SOURCES.md`、修正履歴: `docs/V16_CHANGELOG.md`。

タスクは物資拠点の視覚確認と避難所への接近です。物資の把持・物理配送、Nav2経路再計画は未実装です。
