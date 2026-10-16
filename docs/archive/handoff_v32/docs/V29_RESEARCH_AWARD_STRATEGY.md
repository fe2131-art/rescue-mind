# RescueMind v2.9 — 課題評価基準、改善戦略、一次資料、限界

2026-10-16 / 課題ソース：`assignment/`内の講座最終課題（10/8版）および本プロジェクトで受領した課題テキスト。外部仕様の根拠は末尾URLを参照。

## 課題原文に忠実な要件

創造性・技術力・実用性・表現力が加点要素。AI必須、ロボット実行動画1〜3分、コード一式、簡単なレポート。提出はOmniCampusの説明資料PDF＋public GitHub URL、YouTubeへのMP4とURL。締切11/2 10:00。氏名・所属・メール等の個人情報を提出物に載せない。

## v2.9実装の本質的修正

### 修正1：収録中に収録完了を求める論理矛盾

**Before**：`scripts/v22_orchestrate.py` の成功ルートは`with Supervisor(...)` 内部のまま`audit_bag_metadata`を呼ぶ。`Supervisor.shutdown`は`with`終了後に録画プロセスへSIGINTを送るため、`metadata.yaml`がまだ確定しない可能性があった。

**After**：成功時、ミッション完了直後に`sup.stop_service('rosbag_recorder')`でSIGINT、プロセス終了を待ち、意図的終了をサービス監視から除外。その後にミッション監査・ROS軌跡監査・bag metadata監査を実行。猶予超過・異常終了なら失敗扱い。異常／AI拒否時は従来どおりcontext cleanupでbagを終了してから証拠検査する。

**検証**：実OSのPython子プロセスがSIGINT受信時にマーカーを保存する結合試験。マーカーが録画中にはなく停止後にのみ存在し、途中終了は正常扱いしない。**ROS2 rosbag2の実動作を検証したものではない**。

### 修正2：欠品シーンと実験的Boxの意味論

**Before**：物体が存在しないシーンでもJevへ実験的Box要求を送り、返答JSONの座標を必須にしていた。欠品を正しく判定しても座標が定義できないため、API挙動次第で正しい拒否ではなくAPIエラー扱いになり得る。

**After**：ライブミッションのJev 1.14.0には画像分類(`choice`)、見える物資の存在確率(`noul`)、危険度(`noul`)、シーンを要求。Box questionはライブの判定から分離し、別の研究用`jev.infer(..., include_box=True)`に残した。JevとQwen両方の画像分類が一致しなければ走行継続不可。no-objectを「成功認識」として扱うには、実APIからの有効な結果と2.5秒の独立停止観測が必要で、通信エラーは失敗扱い。

**注意**：TypeSafeの実API応答構造はこの実行環境から未確認。画像とBoxは実験的機能。ローカルに人工応答を注入して行うユニットテストは現実のAI精度を証明しない。

## 優秀賞への4項目の証拠設計

| 評価基準 | 見せるもの | 現時点の証拠 |
|---|---|---|
| 創造性 | 正しい物資なら次区間、誤物資/欠品なら停止。観測方向や静止もロボットが制御 | 実装済み。実Gazebo動画は未撮影 |
| 技術力 | Jev＋Qwen画像推論、ROS/Gazebo、静止・画像・時計ゲート、独立速度ガード、録画終了後の監査 | オフライン結合テスト成功。実ミドルウェア未検証 |
| 実用性 | 明示拒否と通信障害/センサー故障を区別、安全側停止と監査ログ | 人工欠陥試験。安全認証はない |
| 表現力 | 同じ初期条件の3シーン比較、1～3分の本物のGazebo実行動画、AI判断＋軌跡の証拠 | PDF原稿・試行計画は準備済み、実映像は未完成 |

## 実験プロトコル

既存 `experiments/v23_locked_protocol.json` は3シーン×2物資×5反復＝計30試行、順序と正解を固定。`nominal`は物資確認・避難所接近の許可、`swapped`と`empty`は拒否・独立停止観測を期待する。予定試行を**実測試行としては数えない**。未走行・API障害・証拠欠落は別カテゴリに分類する。人工条件の成功数は実モデルの認識率と区別。

## 技術的制限

- 実装タスクは**物資拠点での画像確認と避難所への接近**。物資を持たず、避難所への「配達完了」を証明しない。
- Nav2の動的経路再計画はこのGazebo走行では使用しない。
- rosbag metadataやROSトピックには暗号学的な出所保証がない。
- AIモデルAPIキーとGazebo/ROS/NVIDIA実行環境がなく、外部実行結果・実モデル性能は今回未検証。
- Jev APIの`Box`の実応答規約・欠品時挙動は実接続して確認すること。Box除外はモデル出力を偽造するものではなく、問い合わせ範囲を変える設計変更。

## 公式・一次資料（外部、2026-10-16調査）

- 課題原文：`Physical-AI応用1講座-最終課題.txt`、評価要件/提出/日時（本プロジェクト提供文書）。
- ROS2 rosbag2 公式GitHub README： https://github.com/ros2/rosbag2 — `ros2 bag record` の停止、`~/stop`で最終化・metadata書き出し。
- Gazebo Harmonic `ros_gz_bridge` 公式： https://gazebosim.org/docs/harmonic/ros2_integration/ — YAMLでのトピック/型/方向の設定。
- Alibaba Cloud `qwen3.8-omni-flash`： https://www.alibabacloud.com/help/en/model-studio/qwen3-8-omni-flash — 画像入力とテキスト出力。
- Alibaba Cloud Qwen Omni 呼出し例： https://www.alibabacloud.com/help/en/model-studio/qwen-omni — Base64とstreamingの例。
- TypeSafe公式ドキュメント（今回ページ本文を直接取得できず**契約の実接続確認が残る**）： https://docs.typesafe.ai/images 、 https://docs.typesafe.ai/primitives/box 。二次資料： https://jevwiki.ai/wiki/reference/http-api.md 。二次資料は公式仕様の代用と断定しない。

## 実走行の実施順序

`README_V29_START_HERE.md` の順でオフライン→`motion-check`→`nominal`→`swapped`→`empty`→30試行の実データ取得→1〜3分実走行動画編集。未検証ならその旨を報告し、完成を装わない。
