# v1.1一次資料調査と未実証事項（2026-10-16）

## 提出原文（一次資料）
同梱 `assignment/Physical-AI応用1講座-最終課題.txt`（10/8版）を最優先の出典とする。授業側の評価軸は**創造性、技術力、実用性、表現力**。合格要件はロボットが動く動画1〜3分、コード、簡単な説明レポート。OmniCampusへPDFと **public** GitHub URL、YouTube URLの双方を提出する。提出期限は **2026-11-02 10:00 JST**。個人情報は動画・レポート・コード・ログに含めない。ロボットが物理的に物資を運んだと主張するには把持・積載・移動を映像で示す必要がある。現状は物資拠点を訪問し確認後に避難所へ**接近**することまで。

## 公開一次資料（調査対象と何が確かか）
1. TypeSafe公式、Jev 1.14.0についての告知（画像・Boxは実験的）: https://typesafe.ai/blog/jev-1-14 。`TypeSafe-Danger-Zone-Images: true` による画像入力、`jev-1.14.0` 限定Boxを確認。モデルによる安全性の保証は示されていない。
2. TypeSafe API Swagger: https://api.typesafe.ai/docs 。`POST /v1/systemone` と `GET /v1/models` が公開されている。**v1.14画像・Boxまで含めた実行時スキーマ一致はAPIキーで実レスポンスを得るまで未確認**。
3. Alibaba Cloud公式 Qwen-Omni: https://www.alibabacloud.com/help/en/model-studio/qwen-omni 。クラウド側はリージョン・Workspace専用URL、画像入力、Chat Completions streamingなどの前提がある。モデルIDやAPI引数はサービス更新の可能性があるため接続試験が必要。
4. Gazebo HarmonicとROS 2の公式ブリッジ: https://gazebosim.org/docs/harmonic/ros2_integration/ 。`/topic@ROS_MSG]gz.msgs.Msg` のような方向指定、ROS/Gazeboの対応する型を公式に確認。
5. ros_gzの実例（カメラ、diff-drive）: https://github.com/gazebosim/ros_gz/blob/ros2/ros_gz_sim_demos/README.md 。`ros_gz_bridge`/`ros_gz_image` による画像ブリッジの例、車輪型移動の例。独自SDFの接地とメッセージがこの構成で動くという実験的証拠ではない。
6. ROS-Gazebo版組合せ: https://index.ros.org/r/ros_gz/ 。JazzyとHarmonicの組み合わせが提供されていることを確認。

## 適用上の注意
- **Jevは必須。** Jev API不通時にQwen単体で走行許可しない。JevとQwenの誤りは独立とは限らず、単純な一致は安全性の証明ではない。
- CLIP / Qwen3-VLは現行構成では使用しない。Qwen3.8-Omni-Flashを実測対象としてコードに残しているが、性能・速度は測定前に論じない。
- Box座標は「存在しないもの」にも返ることがあるため存在判断と必ず併用する。2次元矩形を危険区域のナビゲーション地図と誤認しない。
- 実装したロボット走行はNav2と独立した直接駆動。自律的な動的経路再計画、物資の物理搬送、実世界安全保証は**未実装**。
- v1.1のカメラ途絶監視はROS Headerの増加を要求するが、独立したハードウェア安全停止ではない。sim時間の停止/遅延時にフェイルストップすることを意図する。
- 2026年10月16日時点の一次資料調査に基づき、最新と断言する用途よりも**モデルID固定・実験ログ記録・再現性**を優先する。
