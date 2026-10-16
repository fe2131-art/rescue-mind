# v0.7 調査ノート（2026-10-16 JST）

## 原文から確定した条件（外部推論ではない）
- 講座「Physical AI応用1講座-最終課題.txt」2026/10/8版：AI活用必須・動画1分～3分・コード一式・簡単なレポート。加点観点：創造性/技術力/実用性/表現力。2026/11/2 10:00締切。
- PDF指定名、GitHub **public**、YouTube（限定公開以上）のURL提出、個人情報とAPIキーの非公開、YouTube子供向け/年齢制限は「いいえ」。
- 審査点数や基準のウェイトは原文にない。提案しているランキングは作者の判断であり、公式点数ではない。

## 外部の一次資料（URLは調査時に参照した仕様ページ）
1. [Alibaba Cloud Model Studio Qwen-Omni](https://www.alibabacloud.com/help/en/model-studio/qwen-omni) — `qwen3.8-omni-flash` の画像/音声/動画入力・テキスト出力、Chat Completions、リージョン別workspace endpoint、ストリーミング形式とAPI利用例を確認（モデルの実際の認識成功を保証しない）。
2. [Alibaba Cloud 2026-10-12モデル一覧](https://www.alibabacloud.com/help/en/model-studio/omni) — 2026年10月時点のQwen3.8 Omniモデル掲載。新しい世代の登場は将来あり得るため絶対的な最新とは断定しない。
3. [Gazebo ros_gz_sim diff-drive demo](https://github.com/gazebosim/ros_gz/blob/ros2/ros_gz_sim_demos/README.md) — `cmd_vel`とOdometry bridge、およびQoSに関するサンプルを確認。
4. [ros_gz_bridge supported conversions](https://index.ros.org/p/ros_gz_bridge/) — Twist / Odometry / LaserScan / Imageの変換。Gazeboトピック名は実起動時に確認すること。
5. [Nav2 Simple Commander API](https://docs.nav2.org/jazzy/configuration_and_development/simple_commander_api/simple_commander_api/) — `goToPose`, `cancelTask`, `getResult` 等のAPI仕様（独自ワールド直接駆動にはNav2は使っていない）。
6. [TypeSafe Jev documentation](https://docs.typesafe.ai/images) — v0.6から継続したJe v1.14.0 画像・Noul・Boxの実験的な接続実装。**公式ドキュメントのオンライン本文を本セッションでは直接取得できなかった**。そのため実API応答のフィールド仕様は未確認のまま、依存している契約テストと実APIスモークを明確に区別する。API取得成功までは「実装済み／実推論未検証」と扱う。

## 重要なトレードオフと新しい改善
- v0.6は出発前のスナップショットを分類。v0.7は物資拠点に近づいたときに**ロボットのカメラが発した新規フレーム**を取得し、物資カテゴリについてJevとQwenで再確認する。
- ステーション画像には通路が写らない場合があるため、**現地チェックは物資カテゴリだけ**に限る。通路の地図/安全/衝突判定と混同しない。
- API呼び出し中は別スレッドでAI推論しROSノードはセンサ購読とゼロ速度送信を継続。実ROSでは未検証なのでデッドロックや停止距離を断言しない。
- Jevを必須とし、未接続時にQwenだけで次工程を許可しない。
- `real_model`フラグはクライアントが返す自己宣言であり、サーバー真正性を保証しない。実際のサービスレスポンスログと録画による照合が必要。

## オフラインで結論できないこと
- Jev/Qwenの正解率、校正確率、コスト、レイテンシー、リトライ成功率。
- Gazeboレンダリング・実車輪駆動・ROS-Gazeboブリッジの実動作。
- Nav2動的再計画、実物資の把持・積載・搬送、実環境での安全性。
