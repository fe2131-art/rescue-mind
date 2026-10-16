# 技術調査・一次情報（参照基準日：2026-10-16）

この文書は最終課題の10/8版に対する**追加調査**。モデル提供元が公開しているAPI機能と、RescueMindでの**実測成果**は区別する。URLやAPI仕様は将来変わるため、実機PCから起動前に再確認。

| 技術 | 提供元の資料 | 採用根拠 | リスクと現時点の検証 |
|---|---|---|---|
| Jev 1.14.0 | https://docs.typesafe.ai/images ・ https://docs.typesafe.ai/primitives/box ・ https://www.jevtypesafeai.com/clerk_1790100707857/docs | 画像 input、Noul/Choice/Box、画像利用ヘッダ `TypeSafe-Danger-Zone-Images`、`/v1/systemone` | 新機能はexperimental。こちらで外部接続/実モデル評価は未実施 |
| TypeSafe Boxの不在対応 | https://www.jevtypesafeai.com/clerk_1790100707857/docs | Boxは検出対象の有無に関係なく矩形を返すためNoulを併用 | v0.4から存在判定チェック、v0.5では非有限数を拒否 |
| Qwen3.8-Omni-Flash | https://www.alibabacloud.com/help/en/model-studio/qwen-omni ・ https://www.alibabacloud.com/help/ja/model-studio/qwen3-8-omni-flash | 画像入力、テキスト応答、OpenAI互換Chat Completions/Responses、ワークスペース・リージョンごとのエンドポイント | `stream=true` によるSSE収集・`reasoning_effort=low`。モックで契約テスト済、実クラウド応答未検証 |
| Qwen代替（ローカル） | https://huggingface.co/Qwen/Qwen3.5-4B | NVIDIA GPUで独立したVLMサーバを立てた場合の代替 | 重み・VRAM・実行時間はGPU仕様未確認、未実測 |
| ROS2 Jazzy | https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html | Ubuntu 24.04 Noble のapt利用 | この作業環境にROSなし |
| Gazebo Harmonic | https://gazebosim.org/docs/harmonic/ros_installation/ ・ https://gazebosim.org/docs/harmonic/ | Jazzyとの対応、world/SDFの運用 | SDFはXML構造テストのみ、Gazebo実行環境なし |
| Nav2 Simple Commander | https://docs.nav2.org/jazzy/configuration_and_development/simple_commander_api/simple_commander_api/ | Pythonから`getPath`, `goToPose`, `cancelTask`等 | ダミーROSで命令・取消を検証、本ROSで未実施 |
| Nav2 Gazebo導入 | https://docs.nav2.org/jazzy/configuration_and_development/first_time_robot_setup_guide/gazebo/ | TF, odom, localization, sensors, Nav2の各調整が必要 | 独自ワールドをNav2統合済みとは扱わない |
| ROS↔Gazebo bridge | https://gazebosim.org/docs/harmonic/ros2_integration/ | ROS-Gazebo間のメッセージ変換 | v0.5独自worldでは設定が別途必要 |

## 調査からの重要な修正

1. Qwen3.8は非同期的にSSEで返ることがあるため、v0.4の非ストリーミングのみの前提を解消（v0.5 `streaming.py`）。契約上の不備を減らしたが、現場でAPI仕様テストが必要。
2. Jev Boxのみの位置情報は物体の存在証明でもマップ座標でもない。Noul存在チェックの後に限り、映像上での位置を参考表示する。
3. `real_model: true`だけでモデル実測を証明したとみなさない。APIログと画像、タイムスタンプ、正解ラベルの監査が必要。
4. Nav2の再経路計画はNav2の機能であり、Jev/Qwen独自の「AIで自動迂回」と誤認させない。
5. 遠隔APIは危険検知時のリアルタイム停止を保証しない。v0.5のLiDAR監視も研究用ソフトウェアであり、機能安全装置ではない。
