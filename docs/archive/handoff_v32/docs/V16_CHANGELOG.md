# v1.6 改善→テスト→残課題

1. **速度ガード**：従来はオドメトリ到着時刻だけを監視。v1.6は位置・姿勢の有限性、クォータニオン、座標フレーム、ROSヘッダー時刻の重複・逆行を検査し、異常時に停止状態へラッチする。`rescuemind/odom_health.py`、`tests/test_v16_runtime_integrity.py`。
2. **Ubuntu起動時の障害**：ROSをsourceしていない親シェルのPATHだけで`ros2`をチェックすると誤拒否し得た。v16オーケストレータはROSセットアップをsourceしたサブシェルで確認する。
3. **成功判定の欠陥**：子プロセスexit 0だけでは「完了」とみなさない。実行IDとステージ順序、ライブ時のJev＋Qwen checkpointログを検証する。`rescuemind/run_completion.py`。
4. **記録の識別**：以前のスキーマは`version:1.2`固定でsupervisorとmissionのrun_idが別。v1.6では双方同じrun_idを使い、証拠バンドルは撮影時刻・画像hash・run_idを検査する。

オフラインPASSは「ロボットがGazeboで完走した」証拠ではない。現時点で`ros2`/`gz`コマンドは実行環境にない。認証済Jev/QwenとのリアルAPI通信も未試験。速度ガードは安全認証のないシミュレータ用実装。
