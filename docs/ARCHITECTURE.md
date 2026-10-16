# RescueMind 全体アーキテクチャと処理フロー

このドキュメントは「何が・どの順で・どのプロセスで動き、何が証拠として残るか」を一枚で追えるようにまとめたもの。
改善の経緯は [`IMPROVEMENT_LOG.md`](IMPROVEMENT_LOG.md)、実行時に見つけた不具合は [`FINDINGS.md`](FINDINGS.md)。

## 1. システム構成（プロセスと通信）

```mermaid
flowchart LR
  subgraph Host["Ubuntu 22.04 ホスト（sudo不要）"]
    subgraph C["Docker: ROS 2 Jazzy + Gazebo Harmonic + PyTorch（V100）"]
      ORC["v32_orchestrate.py<br/>起動・準備確認・監査の統括"]
      GZ["Gazebo Harmonic<br/>EGLヘッドレス描画<br/>差動二輪＋LiDAR＋カメラ"]
      BR["ros_gz_bridge<br/>/clock /odom /scan /camera<br/>/cmd_vel /ground_truth/odom"]
      VLM["local_vlm_server.py<br/>Qwen3.5-9B（V100, FP16）<br/>/v1/classify /v1/describe /v1/intent"]
      MIS["gazebo_waypoint_mission.py<br/>ミッション制御"]
      GRD["guarded_cmd_relay.py<br/>独立速度ガード"]
      WAT["runtime_guard_graph_watch.py<br/>/cmd_vel 発行者監視"]
      REC["odom_evidence_recorder.py<br/>独立レコーダ（真値含む）"]
      BAG["ros2 bag record（MCAP）"]
    end
  end
  GZ <--> BR
  BR -- "/odom /scan /camera" --> MIS
  BR -- "/odom /scan /camera" --> GRD
  MIS -- "/rescuemind/cmd_vel_request" --> GRD
  GRD -- "/cmd_vel（唯一の発行者）" --> BR
  MIS -- "HTTP 127.0.0.1（画像・指示文）" --> VLM
  WAT -. "異常時 /rescuemind/estop" .-> GRD
  BR -- "/ground_truth/odom /odom /cmd_vel" --> REC
  BR --> BAG
  ORC -. "起動・停止（SIGINT→SIGTERM→SIGKILL）" .-> GZ & BR & VLM & MIS & GRD & WAT & REC & BAG
```

* ミッションは速度を**要求**するだけで、車輪への指令（`/cmd_vel`）を出せるのは独立した速度ガードだけ。
* VLM はループバック（127.0.0.1）だけで待ち受け、クラウドAPIは一切使わない。
* Gazebo の真値（`/ground_truth/odom`）はレコーダと監査だけが使い、制御には使わない。

## 2. 1回のミッションの流れ

```mermaid
sequenceDiagram
  autonumber
  participant O as Orchestrator
  participant M as Mission
  participant G as 速度ガード
  participant V as ローカルVLM
  participant A as 監査（実行後）
  O->>O: 孤立スタック検出（/cmd_vel 発行者・Gazeboが無いこと）
  O->>O: Gazebo・ブリッジ・ガード・VLM・監視・レコーダ・bag を起動
  O->>O: 準備確認（Gazebo Transport、センサー鮮度、シミュレーション時計、VLM health）
  O->>M: ミッション開始（指示文）
  M->>V: 指示文（選択式2問：物資は？届け先は？）
  V-->>M: 各選択肢の確率
  M->>M: 指示理解＋避難所名の規則ガード。曖昧・未対応は出発前に拒否
  M->>G: 物資拠点へ速度要求（ウェイポイント追従）
  M->>M: 到着 → 拠点中心へカメラを向ける → オドメトリで静止を確認
  M->>M: 静止後の新しいカメラフレーム2枚（画質・ROS時刻・Sim時計を検査）
  M->>V: 画像＋選択式2問（選択肢順を入替）＋危険Yes/No
  V-->>M: 各選択肢の確率
  M->>M: 判定（2問とも依頼物資が最大かつ0.50以上・危険なし）
  M->>V: 状況説明（日本語1文、判断には使わない）
  alt 許可
    M->>G: 避難所Bへ速度要求
  else 物資違い・欠品（危険なし、初回のみ）
    M->>M: 2.5秒停止保持 → もう一方の拠点で同じ確認（回復探索）
  else 危険 / 確信度不足 / 2回目の拒否
    M->>M: 2.5秒停止保持 → 停止して終了（人に委ねる）
  end
  O->>O: bag を SIGINT で確定 → スタック撤収
  O->>A: 監査
  A->>A: 判断の再計算（画像ハッシュ・モデル出力）・静止証拠・時刻整合
  A->>A: 独立レコーダの軌跡（Gazebo真値）で到着／停止・転倒・オドメトリ乖離
  A->>A: 許可より前に避難所へ近づいていないか（時系列）
  A-->>O: COMPLETED / COMPLETED_EXPECTED_DENIAL / FAILED
```

## 3. 判定ロジック（VLMチェックポイント）

```mermaid
flowchart TD
  IMG["静止後の新しいカメラ画像"] --> Q1["質問1：台の上の物は？<br/>A 水 / B 救急箱 / C 何も無い・その他"]
  IMG --> Q2["質問2（選択肢順を入替）<br/>A どちらでもない / B 救急箱 / C 水"]
  IMG --> QH["危険：火・炎・煙が見えるか Yes/No"]
  Q1 & Q2 & QH --> D{"両方の質問で依頼物資が最大<br/>かつ p ≥ 0.50<br/>かつ p(危険) < 0.50 ?"}
  D -- はい --> ALLOW["許可：避難所Bへ"]
  D -- 危険 --> STOP["停止（探索しない）"]
  D -- 物資違い・欠品 --> REC{"回復探索は未実施？"}
  REC -- はい --> SEARCH["もう一方の拠点で再確認"]
  REC -- いいえ --> STOP
```

回答は文章を生成させず、次トークンの選択肢文字（A/B/C・Yes/No）の確率を1回の順伝播で読む（閉集合の対数確率スコアリング）。
解析不能な出力が起きず、判断に確信度が付く。閾値は開発用画像だけで決め、評価前に事前登録した。

## 4. 開発と評価の流れ（なぜ数値を信用できるか）

```mermaid
flowchart LR
  DEV1["開発セットv1<br/>48枚（視点ランダム）"] --> TUNE["プロンプト・閾値の比較"]
  DEV2["開発セットv2<br/>128枚（照明・妨害物・火災）"] --> TUNE
  TUNE --> PRE["事前登録<br/>PREREGISTRATION_*.md に固定"]
  PRE --> CAMP["閉ループ評価<br/>試行ごとにスタックを新規起動"]
  CAMP --> LEDGER["台帳 campaign_ledger.jsonl<br/>失敗・中断も削除しない"]
  LEDGER --> EVID["証拠 evidence/&lt;run_id&gt;/<br/>判断画像・mission.json・真値軌跡・bag情報"]
  EVID --> GEN["図・README・レポートPDF・動画を自動生成<br/>（数値の手入力なし）"]
```

## 5. 主なファイル

| 層 | ファイル |
|---|---|
| 実行環境 | `docker/Dockerfile`（`STACK` 引数でモデル実行系を切替）, `docker/run.sh`, `docker/build.sh` |
| 世界 | `worlds/rescuemind_test_arena.sdf` → `scripts/v22_generate_scenes.py` で3シーン生成、`rescuemind/robust_scenes.py` で照明・妨害物・火災の派生 |
| ロボット制御 | `ros/gazebo_waypoint_mission.py`, `rescuemind/waypoint.py`, `rescuemind/camera_aim.py`, `rescuemind/stationary_gate.py` |
| 安全 | `ros/guarded_cmd_relay.py`, `rescuemind/velocity_relay.py`, `ros/runtime_guard_graph_watch.py`, `scripts/stack_quiescence.py` |
| AI | `scripts/local_vlm_server.py`, `rescuemind/local_vision.py`, `rescuemind/intent.py`, `rescuemind/intent_llm.py` |
| 監査 | `rescuemind/ground_truth_evidence.py`, `rescuemind/causal_evidence.py`, `rescuemind/negative_evidence.py`, `rescuemind/recovery_evidence.py`, `rescuemind/run_completion.py` |
| 評価 | `experiments/*`（事前登録・プロトコル・開発セット・台帳・証拠）, `scripts/run_campaign.py`, `scripts/*_eval.py` |
| 成果物生成 | `scripts/make_figures.py`, `scripts/make_report.py`, `scripts/make_video_plan.py`, `scripts/make_demo_video.py` |
