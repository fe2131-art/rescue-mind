# RescueMind v3.0 — 優秀賞へ向けた実装・実験・発表戦略

**課題根拠**: 配布「Physical AI応用1講座 最終課題（10/8版）」。下記の提出要件・評価基準・締切はこの原文に基づく。ROSやAPIの仕様については末尾の外部一次資料に分離して記載する。

## 1. 課題要件と客観的な達成状態

- AI利用が必須。タスクは受講者が自由設計。動画はロボットが実際にタスクを実行している**60〜180秒**のMP4。倍速利用は明記。
- 提出: 2026年**11月2日(月)10:00 JST**までにOmniCampusへ説明PDF `説明資料_PAI最終課題_omnicampusアカウント名.pdf`、public GitHub URL、YouTube URL。YouTubeは最低限定公開、一般公開は推奨。氏名・所属・メールアドレス等の個人情報は含めない。
- 加点は**創造性、技術力、実用性、表現力**。実動画とコード・レポートが合格ライン。優秀賞は予定で保証されない。
- 本実装のタスクは「自然言語指示 → 物資拠点への接近 → 棚向き合わせ/静止 → 現地カメラ2フレーム検査 → **Jev 1.14.0必須＋Qwen3.8**で許可/拒否 → 避難所への接近または停止」。ロボットは**水をつかまない/運ばない**。Nav2動的再計画も独自Gazebo実験ではない。

## 2. v3.0で実際に発見・修正した問題

### 欠陥A: 「正常なAI拒否」ルートだけROS bag最終化成功が検証されない

v2.9ではミッション正常終了後は `stop_service('rosbag_recorder')` でSIGINT/終了コードを明示確認。しかし、**誤物資・欠品で推論が正しく拒否するとミッションが非ゼロ終了**するため、`run_mission()` 例外で `stop_service()`を飛ばしていた。Supervisorの後始末でSIGINTは送っていたが、最終化に失敗したかを成功ルートと同じ強さで確認していなかった。

**修正**：厳密に想定シーン（swapped/empty）かつ `mission failed (exit=...)` に一致するときだけ非ゼロ終了を一時保留。ガード・Gazebo・独立ROSオドメトリ観測を生かしたままROS bagにSIGINTを送り、終了コード/メタデータを検査。その後、静止・両モデルの拒否・カメラ/時刻・独立観測に合格した場合のみ `COMPLETED_EXPECTED_DENIAL`。強制終了、記録欠落、タイムアウトは `FAILED`。

### 欠陥B: 証拠の `stack_plan.json` に仮の実行IDが残る

v2.9の出力は、`--plan`でbagなしのとき実行時に常駐する独立オドメトリ収録プロセスを省略。また本実行の保存記録はミッションだけ実IDで、他サービスの引数は仮の`<run_id>`のまま。**修正**：計画表示に独立記録器を常に記載し、本実行のサービス・readiness・missionを同一run_idを含む実コマンドに置き換えて保存。

**テスト**：実プロセスSIGINTテスト（前版より継続）に加え、フルorchestratorを偽サービスで駆動する10条件の自動試験を追加。正常完走、正常拒否、レコーダ終了失敗、bag証拠欠落、タイムアウト、誤シーン、bagなし、プラン完整性、実行ID整合。**実ROS/GazeboやJev/Qwen APIを実行した証拠ではない**。

## 3. 審査員への効果を最大化する実験・表現

| 評価 | 強調する実動作 | 必要な一次証拠 |
|---|---|---|
| **創造性** | 同一指示でnominalだけ続行、swapped/emptyは現地停止 | 同一カメラ位置からの3シーン比較映像 |
| **技術力** | 視線制御/静止/カメラ鮮度・画質/二重VLM/独立速度制限 | ROSカメラ、Jev+Qwen応答ID、トピックbag、独立オドメトリ |
| **実用性** | 誤物資・欠品・モデル障害の理由を別々に表示 | 誤許可・誤拒否・通信エラー率、停止前後の速度/位置 |
| **表現力** | 成功動画だけでなく“進まないこと”も見せる | 1〜3分内の正常シーン＋比較＋技術解説 |

**実動画110秒案**: 0-14秒：災害支援での現地物資確認という目的と運搬未実装の限界。14-51秒：nominalのGazebo走行、向き合わせ、静止、現地ROSカメラと両モデル許可、避難所接近。51-78秒：swappedとemptyで静止する対比。78-98秒：ROS bag・独立/odomと状態ログを同期表示。98-110秒：比較表・誤許可率/誤拒否率（**実測できた場合のみ**）と課題。

**30試行**: 既存固定プロトコル `experiments/v23_locked_protocol.json`、3シーン×2物資×5回。正答、誤許可、誤拒否、API通信不成立、画像不良、証拠欠落を別々に数える。反復は独立した未知画像分布の標本ではなく、95%信頼区間は参考値。実推論が一度も実行されない場合、精度の欄は**N/A**のままにする。

## 4. 実行順序（Ubuntu、必要な認証情報のみユーザー設定）

1. `bash scripts/v30_verify.sh`。これはオフラインテスト。
2. `python3 scripts/v30_orchestrate.py --plan --scenario motion-check --scene nominal --capture-rosbag` でプロセス/ディレクトリ/時計を確認。
3. `--run --scenario motion-check --scene nominal --capture-rosbag` で実Gazebo・車輪・時計・速度ガード・録画を確認。`stack_result.json`だけでなくGazebo画面とbagサイズを確認。
4. `--run --scenario live --scene nominal --capture-rosbag --instruction '避難所Bに飲料水を届けて'`。実APIのキーが必要。実際には配達ではなく接近。
5. 同じ命令で `swapped`, `empty` を実行。ここは非ゼロ終了しても静止+AI拒否+録画最終化を監査し、 `COMPLETED_EXPECTED_DENIAL`になれば期待成功。`FAILED`は成功例に数えない。
6. 30試行後、提出用MP4/PDFの個人情報とAPIキーの表示を目視確認。GitHubをpublic化し、YouTube限定公開以上で締切までにURL提出。

## 5. 技術調査・出典（外部一次資料と主張の区分）

- Gazebo Harmonic のROS 2連携と `ros_gz_bridge`: https://gazebosim.org/docs/harmonic/ros2_integration/ — ブリッジの型/トピック/方向。
- Gazebo HarmonicのDiffDrive: https://gazebosim.org/docs/harmonic/moving_robot/ — 差動二輪の駆動とコマンドトピック。
- ros_gz_bridge公式launchソース: https://github.com/gazebosim/ros_gz/blob/ros2/ros_gz_bridge/launch/ros_gz_bridge.launch.py — `bridge_name`、`config_file`引数。
- rosbag2公式: https://github.com/ros2/rosbag2 — `--use-sim-time`は最初の`/clock`が届くまで録画しないことがある。SIGINTの実子プロセス停止試験は**ROS bag実機確認ではない**。
- rosbag2 QoS公式: https://github.com/ros2/ros2_documentation/blob/rolling/source/Developer-Tools/Debugging/Testing/Overriding-QoS-Policies-For-Recording-And-Playback.rst — QoS設定不一致でsensor record 0件が起こり得るのでtopic countを確認。
- Alibaba Cloud `qwen3.8-omni-flash`公式: https://www.alibabacloud.com/help/en/model-studio/qwen3-8-omni-flash — 画像入力/テキスト出力。
- TypeSafe Jev画像・Box一次資料URL: https://docs.typesafe.ai/images 、 https://docs.typesafe.ai/primitives/box 。**今回これらの本文全文・実API応答契約を直接検証できていない。公式に認証されたAPI動作保証とは書かない**。

## 6. 結論と厳格な限界

v3.0は**コード・ユニット/モック統合・外部子プロセスSIGINT・SDF静的構成**を検証する配布物。ここまでの全版を通じて、このコンテナにはROS 2 Jazzy・Gazebo Harmonic・Jev/Qwenキーがなく、**Gazebo実走行、実VLM性能、実rosbag、提出MP4は未実施**。安全認証でもない。ログ内の`real_model=true`も暗号学的なAPI出所証明ではない。コンテスト優秀賞の選出は保証されない。
