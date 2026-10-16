# 継続改善ログ：RescueMind v0.4 → v0.5

検証の種類：**OFFLINE**（本コンテナの実行）、**CONTRACT**（模擬API）、**FAKE ROS**（ダミーROS）、**UNVERIFIED**（外部環境要）を混同しない。

| サイクル | 発見した欠陥 / リスク | 修正対象 | 実施した確認 | まだ不足する確認 |
|---|---|---|---|---|
| 1: 外部AI接続 | Qwen Omniのストリーム応答を非ストリームJSONと仮定 | `streaming.py`, `qwen35.py` | SSE断片、切断、モデルID不一致、容量上限のテスト | 実API署名/応答形式とコスト実測 |
| 2: 走行中監視 | 事前静止画のみで走行中の急変に対応しない | `watchdog.py`, `ros/nav2_mission.py` | 距離しきい値、heartbeat、E-stop、ダミーROS経由のNav2キャンセル | ROS 2現物/シミュレータ上の監視タイミング、ブレーキ距離 |
| 3: 統計・監査 | 単一の率からの性能断定、重複ケース混入 | `experiment_stats.py`,`benchmark_vision.py` | Wilson 95%区間と重複ケース拒否をユニットテスト | 複数シード・独立シーンの実画像60+組 |
| 4: 再現可能な3D環境 | v0.4はNav2公式デモに依存し独自Gazeboワールド不在 | `worlds/rescuemind_test_arena.sdf` | XMLとセンサー・ジョイント・対象物構造をテスト | Gazebo Harmonic上の物理挙動、ros_gz橋渡し、map/TF |
| 5: 提出漏れ防止 | PDF名、1〜3分MP4、公表URLの確認が手作業 | `submission_preflight.py`, `ASSIGNMENT_REQUIREMENTS.md` | 模擬不足入力が不合格となるテスト | 目視による動画内容/個人情報とGitHub/YouTube公開設定 |
| 6: バグ耐性 | APIのNaN/Infが安全判定をすり抜ける可能性 | `jev.py`, `safety.py` | NaNを拒否するテスト | API生応答での境界値測定 |

## 受賞戦略の更新

- 「最新版モデルの名前」をアピールするだけでなく、**失敗条件を定量化する研究ストーリー**にする。
- シミュレーション環境での目的地到達は **P0**。現状は未達のため、次のGPU Ubuntu PC作業で最優先。
- Jevは必須。画像推論が不安定な場合も無断で外すのでなく、失敗率と制約を報告。
- 格子経路探索結果をGazeboの性能値として流用しない。
- Jev単独・Qwen単独・融合の比較では安全側の誤許可率だけでなく配送可能率（coverage）も報告。
- 11/2 10:00 JSTの締切までに最低限の実ロボット動画・PDF・public GitHubとYouTube URLを優先。
