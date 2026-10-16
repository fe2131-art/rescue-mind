# RescueMind v2.7 — 優秀賞獲得戦略・一次資料・限界

2026-10-16 JST。**原文基準**: `Physical-AI応用1講座-最終課題.txt`（10/8版）。合格ラインはロボット実行動画と提出物の提出。加点は創造性・技術力・実用性・表現力。以下の戦略は作者側の考察であり、受賞を保証するものではない。

|課題評価基準|審査で示すべき内容|現時点の検証|
|---|---|---|
|創造性|同じ日本語物資指示で正配置・物資入替・欠品を切替。Jev＋Qwen一致で継続、否決で停止|3つのSDFシーンと制御モック、実画像推論は未実施|
|技術力|ROS/Gazebo、二重AI、カメラ向き合わせ、実測静止、2新規画像品質ゲート、独立速度ガード、ROS bagと因果時刻監査|Python単体・模擬ROS・SDF静的テスト済。実Gazeboは未検証|
|実用性|破損画像、通信途絶、誤物資、API失敗、障害物で「何の理由で止まったか」を分離し、無理な再発進をしない|人工故障注入は実施。実物での誤許可率/誤拒否率は未測定|
|表現力|1〜3分動画で到着→棚向き合わせ→静止→2フレーム検査→Jev/Qwen→許可・拒否を比較。AI応答・ROS動作のタイムラインを明示|PDFはドラフト。実映像・実測結果なし|

## 研究上の重要な定義

- 「物資を届ける」日本語命令は便宜的表現。実際に実装したロボット動作は**物資拠点の視覚検査と避難所への接近**。手先把持・積載・輸送は未実装。
- 完全な自律地図構築、Nav2動的リプラン、ハードウェア安全認証を主張しない。
- 二つのVLMの失敗は独立とは限らない。模擬拒否成功率から実際の認識精度を推定しない。
- v2.7は明度の極端な破損/単調画像とROS Image payload異常を弾く保守的なゲート。対象物が画角内にあり視認可能なことを証明しない。実Gazeboで閾値校正が必要。

## 実験・提出の段階的ゴール

**Gate A**: Ubuntu PCでGazebo nominalシーンを起動。`/clock`, `/odom`, `/scan`, `/camera`, `/cmd_vel`の連続受信、独立ガードとロボット実移動を確認する。

**Gate B**: 撮影イベントの画像を本人が目視確認する。水ボトルや救急箱が遮蔽・反射・背景に埋もれていないことを確認。画質ゲート不合格なら失敗証拠を保存して原因究明し、条件を事後変更したときは設定バージョンを記録する。

**Gate C**: Jev 1.14.0 + Qwen3.8-Omni-Flashの両方を**実際に**同じ撮影JPEGへ適用する。`nominal`, `swapped`, `empty` を同指示で比較。`experiments/v23_locked_protocol.json` の30試行は事前登録した**実行計画であり実測数ではない**。

**Gate D**: 1〜3分の実動画、確認済みGitHub publicリポジトリ、PDFを仕上げる。障害物/停止動画は別試行の映像として明示し、合成動画を実Gazeboと呼ばない。

## 一次資料と実装への対応（2026-10-16に閲覧）

- Gazebo Harmonic ROS 2 integration: https://gazebosim.org/docs/harmonic/ros2_integration/ — `ros_gz_bridge`、GZ_TO_ROS/ROS_TO_GZ通信方向、YAML対応。ブリッジ静的契約に使用。
- Gazebo Harmonic diff-drive movement: https://gazebosim.org/docs/harmonic/moving_robot/ — DiffDrive速度入力とオドメトリ。差動二輪の前提に使用。
- ros_gz_bridge README: https://github.com/gazebosim/ros_gz/blob/ros2/ros_gz_bridge/README.md — `/clock`の片方向中継に関する注意。Gazebo / ROS時刻を混用しない。
- ROS 2 Jazzy QoS: https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Quality-of-Service-Settings.html — センサーデータはbest-effort、小さいキューの用途。ROSサブスクリプションに使用。
- Alibaba Model Studio Qwen3.8: https://www.alibabacloud.com/help/en/model-studio/qwen3-8-omni-flash — 2026-09-28更新、画像を含む入力／テキスト出力に対応。APIキー・リージョンとモデルIDは実接続で確認する。
- Alibaba Model Studio Qwen Omni guide: https://www.alibabacloud.com/help/en/model-studio/qwen-omni — 画像の送信例と制約。
- TypeSafe Jev画像APIの文書入口: https://docs.typesafe.ai/images および https://docs.typesafe.ai/primitives/box — **一次資料本文の取得および実API互換性は未検証**。過去版コードのJev必須インターフェースを保持するが、実契約・提供地域・運用条件の確認が必要。

外部サービス仕様の詳細は変更され得る。ソフトウェア合格件数はAPIの保証・モデル評価結果ではない。

## 2分デモ構成例

0:00–0:18 課題設定と日本語指示／0:18–0:45 物資拠点へ移動／0:45–1:03 向き合わせ＋静止＋カメラ品質／1:03–1:22 Jev＋Qwen結果表示／1:22–1:43 nominal→避難所の移動／1:43–2:00 swapped/empty→拒否停止と結果比較。倍速使用時は明記。
