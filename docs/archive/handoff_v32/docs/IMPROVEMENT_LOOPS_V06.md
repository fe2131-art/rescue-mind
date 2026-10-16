# v0.5 → v0.6 実装改善ループ記録

基準：2026-10-16、添付 `assignment/Physical-AI応用1講座-最終課題.txt`（10/8版）。

| ループ | 発見した問題 | 実装改善 | 検証 | 未検証 |
|---|---|---|---|---|
| 1 | 独自Gazeboワールドに動くROS操縦ノードがなかった | `ros/gazebo_waypoint_mission.py` / `rescuemind/waypoint.py` / `scripts/bridge_direct_gazebo.sh` | 理想運動学の2ルート走行・ROS未導入時失敗・角度正規化のテスト | Gazebo実走・ROSブリッジ |
| 2 | SDFの物資が色のついた台しかなく物体が識別できない | ボトル形状と白い救急箱・赤十字をSDFに追加 | XML構造/見込み経路の2D矩形クリアランス | Gazeboレンダリング、実VLMでの認識 |
| 3 | 受賞向け比較で二重判定の「有効性」主張に統計的根拠が薄い | `paired_significance.py` / `paired_benchmark.py`、危険ケース上のMcNemar正確検定 | 人工ペアの数値検算・すべての先行モック試験 | Jev/Qwen本APIの比較データ |
| 4 | テストがPASSでもロボットの実行証拠がなかった | `audit_robot_run.py` と提出向け証拠要件を追加 | 不完全なdry-runは拒否、形式整合性ログのみ許可 | 第三者による録画・実環境の真正性 |

## 仮説・撤退条件

- 独立VLMモデルの合意は、認識単体より誤許可率を下げる可能性があるが、coverage/false denialを犠牲にする。**実測していないので結論未定**。
- APIが遅い場合、走行中の判断には使わず、走行前の高水準意味判断に限定。リアルタイム停止はNav2 Collision Monitorなど別系統へ。
- 10/23を越えて独自ワールド走行が未成功なら、講座の合格条件である実行動画を優先し、公式TurtleBot3+Nav2に移行する。
