# RescueMind v1.5 - まずここから

このパッケージは「Physical AI応用1講座 最終課題（10/8版）」を基準にした**研究・開発用ソース**。Jev 1.14.0を必須としQwen3.8-Omni-Flashと組み合わせる。実Gazeboと実APIはこの配布環境では未検証。

1. `bash scripts/v15_verify.sh`（ROSなしでも実行）
2. `bash scripts/check_ubuntu_ros.sh`
3. `bash scripts/setup_ubuntu_jazzy.sh`
4. `python3 scripts/v15_orchestrate.py --plan --scenario motion-check`
5. `python3 scripts/v15_orchestrate.py --run --scenario motion-check`（Ubuntu実ROS/Gazeboが必要）
6. Jev/Qwen APIキーを手元で設定後、`--scenario live`を実行

**v1.5の本当の差分**：v1.4のtopic `echo --once` 中心のreadinessを、ROS実メッセージの時刻・エンコーディング・バッファ長・LiDAR範囲・オドメトリ姿勢を審査する`v15_live_readiness.sh`に交換。3回独立に更新された観測が揃わなければミッション開始しない。

最新: `docs/V15_UBUNTU_RUNBOOK.md`、`docs/V15_EVIDENCE_LEDGER_AND_AWARD_STRATEGY.md`、`docs/V15_PRIMARY_RESEARCH_AND_LIMITS.md`、`outputs/release/v15_VERIFICATION.json`。

物理的な物資の積み込み/搬送、Gazebo Nav2自動再計画、提出用動画の作成は未完成。`reports`に載せる成功率は実画像/実Gazebo試験だけから算出すること。
