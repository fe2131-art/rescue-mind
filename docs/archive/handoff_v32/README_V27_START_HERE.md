# RescueMind v2.7 — START HERE / 2026-10-16

**実Gazebo物理走行・Jev/Qwenの実API推論は未検証。** この配布物のPASSはオフラインPython・模擬ROS・人工画像・SDF静的検証である。

## 作品概要と課題準拠

作品タスクは、自然言語で指定した飲料水／医療物資の拠点へ差動二輪ロボットが接近し、棚に向き合わせて静止を確認したあと、**2枚の独立した新規ROSカメラフレームを検査**し、Jev 1.14.0とQwen3.8-Omni-Flashの両方が許可した場合だけ避難所Bへ接近する。物資の把持・運搬は実装していない。Nav2による経路再計画もこのカスタムワールドでは未実証。

**Jevを必須とする。** 資格情報がない場合はライブミッションを開始しない。誤った物資、欠品、VLM不一致、画像破損、センサー途絶では安全側に停止する。

## ここから開始

```bash
cd rescuemind_v27
python3 -m pip install -e .
bash scripts/v27_verify.sh
python3 scripts/v27_acquisition_campaign.py
bash scripts/check_ubuntu_ros.sh
```

Ubuntu 24.04 + ROS 2 Jazzy + Gazebo Harmonic と NVIDIA GPU が使える環境で初めて、以下を実行する。

```bash
bash scripts/setup_ubuntu_jazzy.sh
python3 scripts/v27_orchestrate.py --plan --scenario motion-check --scene nominal
python3 scripts/v27_orchestrate.py --run --scenario motion-check --scene nominal --capture-rosbag
```

上記成功後、JevとQwenのAPI認証情報を安全なシェル環境変数で設定し、**秘密情報をGitHubへ置かずに**実施する。

```bash
python3 scripts/v27_orchestrate.py --run --scenario live --scene nominal \
  --capture-rosbag --instruction '避難所Bに飲料水を届けて'
# 同じ指示で --scene swapped および --scene empty を比較する。
```

`--scene swapped` / `--scene empty` の正しい拒否は、単なる異常終了とは区別する。独立ROS観測を伴う拒否完了の場合のみ `COMPLETED_EXPECTED_DENIAL` とする。

## v2.7の追加

- `rescuemind/image_acquisition.py`: 黒つぶれ、白飛び、単色化、データ欠損を拒否。撮影停止確認後に異なるタイムスタンプの新規フレーム2枚を要求し、2枚目を採用する。画像品質は**物体が見えていることの保証ではない**。
- `ros/gazebo_waypoint_mission.py`: 正常な撮影時だけJPEGを保存し、その後でJevとQwenを推論。異常画像はモデルに渡さず停止する。
- `rescuemind/v27_image_evidence.py`: 静止検証→2フレーム取得→JPEG SHA-256→AI判定の順序と実ファイルの同一性を検証する。
- `scripts/v22_orchestrate.py`: 成功・期待された拒否の**双方**で新しい画像監査を必須化。
- `tests/test_v27_image_*`, `scripts/v27_acquisition_campaign.py`: 人工画像の故障試験。既存ROS擬似統合試験にも画質異常を追加。

## 提出の作業

1. **2026-10-19以降** omnicampusへレポートPDFとpublic GitHub URLを提出。PDF名は `説明資料_PAI最終課題_omnicampusアカウント名.pdf`。
2. 1〜3分の本物のロボット実行動画をMP4で作成しYouTubeへアップロード。公開は加点対象、限定公開も可。タイトルは `PAI最終課題_omnicampusアカウント名`。
3. 締切は **2026-11-02 10:00 JST**。倍速再生を用いた場合は明記する。氏名・所属・メールアドレス・API鍵など個人情報や秘密情報を載せない。
4. `docs/RescueMind_v27_REPORT_DRAFT_NOT_SUBMISSION.pdf` は**実測前ドラフト**であり、そのまま完成提出物にしない。

調査根拠・評価戦略 `docs/V27_AWARD_STRATEGY_AND_RESEARCH.md` ／試験条件 `docs/V27_ADVERSARIAL_EXPERIMENTS.md`／公開前監査 `docs/V27_SUBMISSION_CHECKLIST.md`。
