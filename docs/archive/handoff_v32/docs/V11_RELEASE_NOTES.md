# RescueMind v1.1 リリース監査

- 受賞戦略：講座原文の4評価基準に対して**実Gazebo映像・実VLMによる意思決定・ペア比較評価**が最大の不足。コードの追加だけを完成と見なさない。
- 改修：`CameraWatch`、run_id毎の出力、証拠パッケージの実行ID・ファイル名突合、500通りの人工故障キャンペーン。
- 自動試験：`bash scripts/v11_verify.sh`（単体/模擬ROS、SDF静的検査、ウェイポイント理想運動学、模擬故障条件、プライバシー簡易監査）。結果は `outputs/release/v11_verification.json`。
- 目視確認：`docs/RescueMind_v11_REPORT_DRAFT_NOT_SUBMISSION.pdf`を画像レンダリングして3ページの日本語テキストとレイアウト確認。
- 残る確認：外部Jev・Qwen API実行、実Gazeboカメラ/接地/走行、提出動画、GitHub public、YouTube可視性、公開情報の最終版。
- 実行ソースに含まれる古い`outputs/release/v06〜v10*`は**過去の履歴**。最新確認は`v11_`プレフィックス。
