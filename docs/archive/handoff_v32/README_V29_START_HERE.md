# RescueMind v2.9 — まずここから (2026-10-16)

**目的**：Physical AI応用1講座 最終課題（10/8版）の4評価基準を念頭に、
自然言語指示→物資拠点→静止・現場画像→**必須Jev 1.14.0とQwen3.8-Omni-Flash**による二重確認→条件付き避難所接近を実装する。
物資の把持/物理輸送、Nav2動的再計画は含まない。

## 最重要のv2.9変更

1. **ROS bagの正常終了を先に実行**：成功走行後、`Supervisor.stop_service('rosbag_recorder')`でSIGINTを送り、終了を確認してから`metadata.yaml`を検査する。従来の「録画中に監査」という誤判定を修正。異常終了・タイムアウトは失敗として記録する。
2. **Jevの分類と実験的Box検出を分離**：実走行中のJevは画像の`choice`/`noul`による分類・可視性・危険度を必須とし、存在しない物資のBox座標は要求しない。`jev.infer`を個別に呼ぶことでBox研究機能は保持する。Qwenの一致がなければ走行継続不可。
3. **合格だけでなく拒否が正常に観測できるか**を人工の10条件で確認。別ROSオドメトリによる停止/移動監査と事前登録30試行は保持。

## この環境でも実行可能なオフライン検証

```bash
cd rescuemind_v29
python3 -m pip install -e .
bash scripts/v29_verify.sh
python3 scripts/v29_checkpoint_campaign.py
```

## Ubuntu 24.04 / ROS 2 Jazzy / Gazebo Harmonic

```bash
bash scripts/check_ubuntu_ros.sh
bash scripts/setup_ubuntu_jazzy.sh
python3 scripts/v29_orchestrate.py --plan --scenario motion-check --scene nominal --capture-rosbag
python3 scripts/v29_orchestrate.py --run --scenario motion-check --scene nominal --capture-rosbag
```

Gazebo上の車輪移動、`/clock`・`/camera`・`/odom`・`/scan`、速度ガード、ROS bag metadataを確認する。`outputs/runs/<run_id>/stack_result.json` の`COMPLETED`と`rosbag_finalization`/`rosbag_evidence`を確認。

Jevの`TYPESAFE_API_KEY`とQwenの`DASHSCOPE_API_KEY`・`DASHSCOPE_BASE_URL`は**シェル環境変数**で設定し、GitHub・動画・レポートに載せない。正しいAPI仕様・接続先は実利用前に確認する。

```bash
python3 scripts/v29_orchestrate.py --run --scenario live --scene nominal --capture-rosbag \
  --instruction "避難所Bに飲料水を届けて"
python3 scripts/v29_orchestrate.py --run --scenario live --scene swapped --capture-rosbag \
  --instruction "避難所Bに飲料水を届けて"
python3 scripts/v29_orchestrate.py --run --scenario live --scene empty --capture-rosbag \
  --instruction "避難所Bに飲料水を届けて"
```

**区別すべき成果**：正常scene=`COMPLETED`、入れ替え/欠品=`COMPLETED_EXPECTED_DENIAL`を目指す。通信障害やモデル不正による`FAILED`は「正しく拒否した」の根拠にしない。`--capture-rosbag`指定時はバグ修正により録画終了後のメタデータが必須になる。

## 提出条件のチェック

- 2026-11-02（月）10:00 JSTまでにOmniCampusへ **PDF**（`説明資料_PAI最終課題_omnicampusアカウント名.pdf`）、**public GitHub URL**、**YouTube URL**を提出。
- ロボット実走行の**1〜3分MP4**をYouTubeへ。最低「限定公開」、一般公開推奨。倍速は明記。
- 氏名、所属、メール、APIキーをレポート・映像・コードに載せない。スクリーンキャプチャにも注意。
- 現時点の `docs/RescueMind_v29_REPORT_DRAFT_NOT_SUBMISSION.pdf` は**未提出ドラフト**。実動画／実API／実Gazeboが未確認なので、虚偽の成功率は記載しない。

詳細：`docs/V29_RESEARCH_AWARD_STRATEGY.md`。オフライン検証：`verification/v29/verification.json`。
