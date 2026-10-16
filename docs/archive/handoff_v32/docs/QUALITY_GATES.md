# v0.6 検証レベルとリリース判定

- **PASS (offline Python)**: unittest、compileall、格子配送試験、異常入力648組。
- **PASS (contract/mock)**: Jev Noul/Choice/Box、Qwen local/クラウド、Qwen3.8 SSE、合意判定。
- **PASS (fake ROS)**: ダミーROSでNav2目標列とキャンセル呼出しを確認。本物のROSではない。
- **PASS (static SDF)**: XMLとして解釈可能、ロボット/センサー/対象物が定義されている。
- **PASS (package)**: ZIPに展開後、Pythonテスト・SHA-256・CRCが通るか最終実測する。
- **UNVERIFIED**: Jev/Qwen本API推論、データセットでの有意な優位性、Gazebo/Harmonic physics、ros_gz bridge、Nav2現物、映像1〜3分、GitHub/YouTube公開。

**「テスト78件通過」はモデル性能の実証ではない。** 安全ゲートは静止画2枚の事前確認、LiDAR走行中監視はソフトウェアの停止要求だけ。実災害救助のための認証・安全保証はない。

- **PASS (offline geometry)**: 2種類の理想運動ルート走行、静的矩形からの離隔の数理チェック。
- **UNVERIFIED (real Gazebo)**: ROS-Gazeboトピックブリッジ、Gazebo物理上の車輪・センサー動作。
