# RescueMind v3.0 — START HERE

**課題**: Physical AI応用1最終課題（10/8版）、4加点: 創造性・技術力・実用性・表現力。提出締切: **2026年11月2日 10:00 JST**。

## v3.0での主な修正

1. **正常拒否の録画を失わない**。誤物資・欠品でのJev＋Qwenの拒否はミッションの非ゼロ終了を伴う。v2.9ではその場合にROS bagの明示的な正常終了確認が抜けていた。v3.0は成功・拒否の両経路でSIGINT終了とデータ監査を行い、録画失敗を成功として扱わない。
2. **実行計画と実ログの一致**。dry-runでも独立オドメトリ収録器を表示し、`outputs/runs/<run_id>/stack_plan.json`に実行時の全子プロセス・保存パスを記録。
3. **実行を装わない**。450件の既存テスト＋新規統合テスト、外部OS子プロセスSIGINT試験、3シーンSDFをオフラインで確認。実Gazebo・実Jev/Qwenは未検証。

## まず行うこと

```bash
cd rescuemind_v30
python3 -m pip install -e .
bash scripts/v30_verify.sh
python3 scripts/v30_orchestration_campaign.py
python3 scripts/v30_orchestrate.py --plan --scenario motion-check --scene nominal --capture-rosbag
```

Ubuntu 24.04でROS 2 JazzyとGazebo Harmonicを導入済みなら：

```bash
bash scripts/check_ubuntu_ros.sh
bash scripts/setup_ubuntu_jazzy.sh
python3 scripts/v30_orchestrate.py --run --scenario motion-check --scene nominal --capture-rosbag
```

上記が正常動作した後、Jev 1.14.0とQwen3.8-Omni-Flashの本物のAPIキーを**環境変数にのみ**設定：`TYPESAFE_API_KEY`、`DASHSCOPE_API_KEY`、`DASHSCOPE_BASE_URL`。API契約・利用可能リージョンを実環境で検証。

```bash
python3 scripts/v30_orchestrate.py --run --scenario live --scene nominal --capture-rosbag --instruction '避難所Bに飲料水を届けて'
python3 scripts/v30_orchestrate.py --run --scenario live --scene swapped --capture-rosbag --instruction '避難所Bに飲料水を届けて'
python3 scripts/v30_orchestrate.py --run --scenario live --scene empty --capture-rosbag --instruction '避難所Bに飲料水を届けて'
```

結果: `COMPLETED`は名目上の正常到着（独立移動監査後）、`COMPLETED_EXPECTED_DENIAL`は現地AI拒否＋停止証拠＋録画最終化後の意図した拒否、`FAILED`は失敗。モデル・API異常を正しい拒否に算入しない。

**本作品は現地物資確認と避難所への接近であり、物資の把持・実運搬はしません**。未実測の推論精度や未撮影の動画をレポートに加えないでください。

## 提出チェック

- **PDF**（提出時に `説明資料_PAI最終課題_omnicampusアカウント名.pdf` に変更）、**public GitHub URL**、**1〜3分の本物のロボット動画MP4のYouTube URL**をOmniCampusへ提出。動画は最低限定公開（一般公開推奨）、倍速は明記。
- 氏名・所属・メール・認証情報をPDF・動画・コード・ログから除去。OmniCampusアカウント名は可。
- PDFドラフトは `docs/RescueMind_v30_REPORT_DRAFT_NOT_SUBMISSION.pdf`。提出可の完成動画や実API成果を保証しない。

詳細な研究・発表構成・一次資料は `docs/V30_AWARD_STRATEGY_PRIMARY_RESEARCH.md`。
