# RescueMind v3.1 / 最初に読む手順（2026-10-16）

**課題根拠:** `assignment/Physical-AI応用1講座-最終課題.txt`（10/8版）。評価基準は創造性・技術力・実用性・表現力。AI必須。60〜180秒の実行動画、説明PDF、public GitHub URL、YouTube URLが必要。締切 **2026-11-02 10:00 JST**。

## v3.1で追加したもの

- **新規の実行中ROSグラフ監視** `ros/runtime_guard_graph_watch.py`: `/cmd_vel` と `/rescuemind/guard_ready` のPublisherが独立速度ガード `rescuemind_velocity_guard` 一つずつであることを0.2秒間隔で確認。異常時に `/rescuemind/estop` を発行し、非ゼロ終了。Supervisorが残りのスタック停止へ移行。
- ROS不要でテスト可能な監視ポリシー `rescuemind/runtime_guard_graph.py` と、結果ログの監査処理。
- `scripts/v31_orchestrate.py` の起動計画に監視ノードを追加。正常完走だけでなく**意図したAI拒否**も、監視証拠がなければ成功判定にならない。
- `scripts/v31_graph_fault_campaign.py`: 誤Publisher、Publisherの重複、消失、メッセージ型異常等の人工16条件。

**重要:** ROSグラフは認証機構ではありません。故意の悪意あるノードや、ROS-Gazeboブリッジに直接アクセスするGazebo Transportクライアント、物理的な制動距離を保証しません。**実Gazebo・実Jev/Qwen APIの動作はこのコンテナでは未検証です。**

## 1. オフライン再現（WindowsやMacは非推奨、Ubuntu 24.04を想定）

```bash
cd rescuemind_v31
python3 -m pip install -e .
bash scripts/v31_verify.sh
python3 scripts/v31_graph_fault_campaign.py
python3 scripts/v31_orchestrate.py --plan --scenario motion-check --scene nominal --capture-rosbag
```

`verification/v31/verification.json`、`verification/v31/graph_fault_campaign.json` と`verification/v31/plan_*.json` を確認してください。これは**実走行ではありません**。

## 2. Ubuntuで最初に確認すること

```bash
bash scripts/check_ubuntu_ros.sh
bash scripts/setup_ubuntu_jazzy.sh
python3 scripts/v31_orchestrate.py --run --scenario motion-check --scene nominal --capture-rosbag
```

`outputs/runs/<run_id>/stack_plan.json` と`stack_result.json`、`guard_graph_watch.jsonl`、独立ROS観測およびROS bagを確認。`state=COMPLETED` だけでは実走行の代替動画にはなりません。Gazeboの画面を確認し録画してください。

## 3. Jev必須＋Qwen3.8のライブミッション

認証情報を自分のUbuntuシェルでのみ環境変数に設定し、GitHubへ絶対に公開しないでください。

```bash
python3 scripts/v31_orchestrate.py --run --scenario live --scene nominal --capture-rosbag \
  --instruction '避難所Bに飲料水を届けて'
```

同じ指示で`--scene swapped` と`--scene empty`に変えて実行します。正しく拒否した場合のみ、独立ROS観測、AI判断ログ、画像品質、時計、監視ログ、必要ならROS bagの監査に通過し`COMPLETED_EXPECTED_DENIAL`と記録します。`FAILED`をAIの拒否成功と数えないでください。

## 4. 提出実験 / 受賞戦略

事前登録した30試行プロトコルは `experiments/v23_locked_protocol.json`。予定と実データを混同しない。各試行で同じ自然言語指示・ロボット・棚の色を維持し、物資配置だけを変更します。推論の誤許可率、誤拒否率、API障害、画像障害は別々に集計します。**30試行は未実施です。**

PDFは`docs/RescueMind_v31_REPORT_DRAFT_NOT_SUBMISSION.pdf`。本名やメールアドレスは絶対に含めず、最終的に `説明資料_PAI最終課題_omnicampusアカウント名.pdf`へリネーム。動画は1～3分、YouTube最低限定公開、GitHub public、OmniCampusに両URLを提出。ロボットは**物資を把持・運搬しません**。この実装は「物資の現地確認と避難所への接近」です。

研究資料の出典は `docs/V31_AWARD_STRATEGY_PRIMARY_RESEARCH.md`。旧READMEは開発履歴、**このREADMEが現行の実行入口**です。
