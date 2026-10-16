# v1.4 改善・実行・検証の記録

## 問題 / 修正 / テスト / 限界

| 監査で判明した問題 | v1.4の修正 | 実際の検査 | まだ言えないこと |
|---|---|---|---|
| 5端末手動起動では起動順・終了処理・証拠の保存先を統一しにくい | `scripts/v14_orchestrate.py` と `rescuemind/stack_supervisor.py` を追加 | 起動コマンドの計画出力、実subprocessの完走・エラー処理・一括テスト | UbuntuでROS/Gazeboが走る保証 |
| ROS/Gazebo/速度ガードが起動していなくてもミッション実行を試みやすい | ROSを含む必要要件の事前確認、サービス生存監視、readiness待機 | サービス異常終了・準備待ち拒否のunit test | 実GazeboのDDS接続を現環境で確認すること |
| 実行ログ・画像が別フォルダに散逸し得る | `outputs/runs/<stack_id>/` にスタックログとmission.jsonとcheckpoint.jpgをまとめる | 計画内の命令引数とシェル引用符テスト | API呼び出しの真正性（要実API） |
| 二重判断の有用性を人工入力の許可率と混同しかねない | 手製12条件による反実仮想アブレーションを明確に`SYNTHETIC`と標識 | `scripts/v14_causal_ablation.py`、期待する12ケースの単体テスト | モデルの実際の認識精度、実現場での安全性 |
| ZIP内にバージョン履歴が混在する | `docs/V14_*`および最新検証JSONを正本とし、旧資料を履歴として維持 | クリーン展開・全テスト・ファイルハッシュ | 旧資料を最新成果として読まないこと |

## 見つかったテスト不具合

readiness期限超過のエラー文変更後、単体テストの期待する文字列が古いままだった。期待値を更新し、177件の全テストを再実行した。

## 検証レベル

- **実行済み**：オフラインの関数・模擬ROS・実subprocess lifecycle・人工故障条件・SDF静的検査・運動学積分・PDFレンダリング。
- **未実行**：ユーザーUbuntu上のROS 2 Jazzy、Gazebo Harmonic物理エンジン、Jev/Qwen実API、実画像の性能・提出MP4。

## 根拠と正本

- 課題原文：`assignment/Physical-AI応用1講座-最終課題.txt`
- 一次調査：`docs/V14_PRIMARY_RESEARCH_AND_RISKS.md`
- 最終戦略：`docs/V14_AWARD_STRATEGY_AND_EXECUTION.md`
- 最新検証記録：`outputs/release/v14_VERIFICATION.json`
- 実験結果：`outputs/release/v14_synthetic_ablation.csv` / `.json`
- 未提出PDF：`docs/RescueMind_v14_REPORT_DRAFT_NOT_SUBMISSION.pdf`
